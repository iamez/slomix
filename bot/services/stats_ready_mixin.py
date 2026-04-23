"""UltimateETLegacyBot mixin: STATS_READY webhook parsing + dispatch.

Extracted from ultimate_bot.py in P3e Sprint 7 / C.5.

All methods live on UltimateETLegacyBot via mixin inheritance.
"""
from __future__ import annotations

from bot.logging_config import get_logger

logger = get_logger("bot.core")
webhook_logger = get_logger("bot.webhook")


class _StatsReadyMixin:
    """STATS_READY webhook parsing + dispatch for UltimateETLegacyBot."""

    def _fields_to_metadata_map(self, fields) -> dict:
        return self.webhook_round_metadata_service.fields_to_metadata_map(fields)

    def _parse_spawn_stats_from_metadata(self, metadata: dict) -> list:
        return self.webhook_round_metadata_service.parse_spawn_stats_from_metadata(metadata)

    def _parse_lua_version_from_footer(self, footer_text: str | None) -> str | None:
        return self.webhook_round_metadata_service.parse_lua_version_from_footer(footer_text)

    def _build_round_metadata_from_map(
        self,
        metadata: dict,
        footer_text: str | None = None,
    ) -> dict:
        return self.webhook_round_metadata_service.build_round_metadata_from_map(
            metadata,
            footer_text=footer_text,
            normalize_round_number=self._normalize_lua_round_for_metadata_paths,
            warn=webhook_logger.warning,
        )

    async def _process_stats_ready_webhook(self, message):
        """
        Process STATS_READY webhook: parse embed, validate, enqueue for the
        worker. Returns after ~10 ms so bursts of webhooks don't fan out
        into N concurrent SSH fetches.

        The queue (`self.webhook_event_queue`) calls
        `_process_stats_ready_round()` below, which does the actual fetch
        + store work sequentially.
        """
        try:
            embed = message.embeds[0]

            metadata = self._fields_to_metadata_map(embed.fields)
            footer_text = None
            if embed.footer and embed.footer.text:
                footer_text = embed.footer.text
            round_metadata = self._build_round_metadata_from_map(metadata, footer_text=footer_text)

            if round_metadata.get("map_name") == "unknown" or round_metadata.get("round_number", 0) <= 0:
                webhook_logger.warning("STATS_READY webhook missing map/round metadata; skipping")
                return

            # Filter ghost rounds (< 30 seconds) — MED-TIMING-002
            actual_duration = round_metadata.get('lua_playtime_seconds', 0)
            if actual_duration is not None and 0 < actual_duration < 30:
                webhook_logger.info(
                    f"⏭️ Skipping ghost round: {round_metadata['map_name']} R{round_metadata['round_number']} "
                    f"(duration {actual_duration}s < 30s minimum)"
                )
                return

            # Pre-parse spawn stats and display names so the worker does not
            # need the original embed.fields shape — attach them to the
            # metadata payload so the queued dict is the single source of
            # truth for the worker.
            round_metadata['_spawn_stats'] = self._parse_spawn_stats_from_metadata(metadata)
            round_metadata['_axis_names_log'] = self._resolve_team_display_names(
                metadata.get('axis', '(none)'), round_metadata.get('axis_players', []),
            )
            round_metadata['_allies_names_log'] = self._resolve_team_display_names(
                metadata.get('allies', '(none)'), round_metadata.get('allies_players', []),
            )

            # Log summary including surrender info (v1.4.0)
            surrender_info = ""
            if round_metadata['surrender_team'] > 0:
                team_name = "Axis" if round_metadata['surrender_team'] == 1 else "Allies"
                caller = round_metadata.get('surrender_caller_name', 'unknown')
                surrender_info = f", surrender={team_name} (by {caller})"

            webhook_logger.info(
                f"📊 STATS_READY: {round_metadata['map_name']} R{round_metadata['round_number']} "
                f"(winner={round_metadata['winner_team']}, playtime={round_metadata['lua_playtime_seconds']}s, "
                f"warmup={round_metadata['lua_warmup_seconds']}s, pauses={round_metadata['lua_pause_count']}"
                f"{surrender_info}, score={round_metadata['axis_score']}-{round_metadata['allies_score']})"
            )
            webhook_logger.info(f"   Axis: {round_metadata['_axis_names_log']}")
            webhook_logger.info(f"   Allies: {round_metadata['_allies_names_log']}")

            # Queue the pending metadata NOW (on the receive side), before
            # enqueueing for the worker. If the worker is backed up and the
            # stats file lands via the filename/SSH-poll path first, the
            # poll can still `_pop_pending_metadata(filename)` and apply
            # Lua overrides correctly. The worker also runs fetch + store
            # but the queue_pending_metadata call is idempotent (list-append
            # keyed by map+round with dedup within the queue helper).
            self._queue_pending_metadata(round_metadata, source="stats_ready")

            # Enqueue for the worker — fast path. Dedup on
            # (map, round_number, round_end_unix) so Lua retries after a
            # Discord blip don't double-fetch the same round.
            queue = getattr(self, 'webhook_event_queue', None)
            if queue is None:
                # Fallback for tests / partial setups that don't wire the queue.
                # Awaits inline — callers that need fire-and-forget should
                # wrap the webhook handler in _safe_create_task themselves.
                await self._process_stats_ready_round(round_metadata, message)
                return
            accepted, reason = queue.enqueue(round_metadata, message)
            if not accepted:
                if reason == "duplicate":
                    webhook_logger.info(
                        "↪️ STATS_READY duplicate skipped (dedup): %s R%s",
                        round_metadata['map_name'], round_metadata['round_number'],
                    )
                else:
                    webhook_logger.warning(
                        "⚠️ STATS_READY dropped (%s): %s R%s — consider raising queue size",
                        reason, round_metadata['map_name'], round_metadata['round_number'],
                    )

        except Exception as e:
            webhook_logger.error(f"❌ Error processing STATS_READY webhook: {e}", exc_info=True)
            await self.track_error("stats_ready_webhook", str(e), max_consecutive=3)

    @staticmethod
    def _resolve_team_display_names(primary: str, players: list) -> str:
        if primary and primary not in {"(none)", ""}:
            return primary
        if players:
            return ", ".join(p.get("name", "") for p in players if p.get("name"))
        return "(none)"

    async def _process_stats_ready_round(self, round_metadata: dict, message) -> None:
        """Worker-side: fetch stats file, then store Lua team/spawn data.

        Order matters — fetch first so the `rounds` row exists when
        `_store_lua_round_teams` resolves round_id. The old inverted
        order produced a deterministic `no_rows_for_map_round` WARN
        on every live match.

        The receive-side handler is responsible for queueing pending
        metadata before enqueueing this work, so the SSH-poll fallback
        can apply Lua overrides immediately even if the worker is
        backed up.
        """
        try:
            from datetime import datetime
            timestamp = datetime.fromtimestamp(round_metadata['round_end_unix'])
            date_prefix = timestamp.strftime('%Y-%m-%d')
            webhook_logger.info(
                f"🔍 Looking for stats file from {date_prefix} for {round_metadata['map_name']}"
            )

            # _fetch_latest_stats_file is internally resilient but returns
            # False on soft failure (file missing, download failed, parser
            # rejected). We capture the result but DO NOT early-return:
            # the Lua team/spawn data below is authoritative capture that
            # must be persisted even on fetch miss, so the relinker cron
            # can pair it with the rounds row whenever SSH poll finally
            # imports the stats file.
            fetched = await self._fetch_latest_stats_file(round_metadata, message)

            # Persist Lua team composition (always). If rounds row
            # doesn't exist yet (fetch soft-fail), round_id resolves to
            # NULL and `_link_lua_round_teams` pairs it later during
            # stats import.
            await self._store_lua_round_teams(round_metadata)
            spawn_stats = round_metadata.get('_spawn_stats')
            if spawn_stats:
                await self._store_lua_spawn_stats(round_metadata, spawn_stats)

            # Delete the webhook message to keep channel clean — Lua
            # doesn't retry automatically once Discord has acked, and
            # the SSH-poll path will pick up the stats file via the
            # metadata we already queued above.
            try:
                await message.delete()
                webhook_logger.debug("🗑️ Deleted STATS_READY webhook message")
            except Exception as e:
                webhook_logger.debug(f"Could not delete webhook message: {e}")

            # Soft-fail signal AFTER all capture work is persisted.
            # Raising here lets `WebhookEventQueue._worker_loop` clear
            # the dedup key so a Lua retry within the TTL (if any) can
            # re-enter and potentially catch the stats file on a fresh
            # fetch attempt.
            if not fetched:
                raise RuntimeError(
                    f"stats fetch soft-fail for "
                    f"{round_metadata.get('map_name')} R{round_metadata.get('round_number')} "
                    f"— Lua capture persisted, SSH poll will retry via queued metadata"
                )

        except Exception as e:
            # Log + alert admin BEFORE re-raising so track_error gets the
            # context. Re-raising is critical: WebhookEventQueue's worker
            # loop uses the exception as a signal to clear the dedup key
            # so a Lua retry for the same round can be accepted within
            # the TTL. Swallowing here would turn a transient SSH/DB blip
            # into a 10-minute lockout.
            webhook_logger.error(
                f"❌ Error in STATS_READY worker: {e}", exc_info=True
            )
            await self.track_error("stats_ready_worker", str(e), max_consecutive=3)
            raise
