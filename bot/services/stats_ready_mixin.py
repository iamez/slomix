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
        Process STATS_READY webhook from Lua script with embedded metadata.

        The Lua script on the game server sends accurate timing data including:
        - Winner team
        - Actual duration (correct even on surrender)
        - Pause tracking
        - Start/end unix timestamps
        - Team composition (Axis/Allies player lists)

        This metadata is used to override potentially incorrect values in stats files.
        Team data is stored separately in lua_round_teams table for analysis.
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

            # Human-readable team names (for logging)
            axis_names = metadata.get('axis', '(none)')
            allies_names = metadata.get('allies', '(none)')
            if (axis_names in {"(none)", ""}) and round_metadata.get("axis_players"):
                axis_names = ", ".join(
                    p.get("name", "") for p in round_metadata.get("axis_players", []) if p.get("name")
                )
            if (allies_names in {"(none)", ""}) and round_metadata.get("allies_players"):
                allies_names = ", ".join(
                    p.get("name", "") for p in round_metadata.get("allies_players", []) if p.get("name")
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
            webhook_logger.info(f"   Axis: {axis_names}")
            webhook_logger.info(f"   Allies: {allies_names}")

            # Order matters: fetch stats FIRST so the `rounds` row exists by
            # the time we try to resolve a round_id in `_store_lua_round_teams`.
            # The old order (Lua store → stats fetch) always raced because the
            # rounds row was created as a side-effect of the stats parse that
            # only runs in step 2, producing a predictable "no_rows_for_map_round"
            # WARN pair on every live match.
            #
            # Parse spawn stats now so we still have them if the fetch fails
            # (spawn stats don't depend on the stats file).
            spawn_stats = self._parse_spawn_stats_from_metadata(metadata)

            # Keep metadata queued for the filename-triggered SSH-poll path
            # as a safety net — if the immediate fetch below fails, the next
            # polling cycle will pick up the file and still apply our overrides.
            self._queue_pending_metadata(round_metadata, source="stats_ready")

            # Trigger immediate SSH fetch for the actual stats file.
            # `_fetch_latest_stats_file` is internally resilient (4× retry with
            # 5 s backoff, catches per-attempt errors) so a fetch miss does
            # not raise here.
            from datetime import datetime
            timestamp = datetime.fromtimestamp(round_metadata['round_end_unix'])
            date_prefix = timestamp.strftime('%Y-%m-%d')
            webhook_logger.info(f"🔍 Looking for stats file from {date_prefix} for {round_metadata['map_name']}")
            await self._fetch_latest_stats_file(round_metadata, message)

            # Now store Lua team + spawn data. The rounds row created above
            # means `_store_lua_round_teams` can resolve round_id directly
            # (no WARN). If the fetch failed, resolve falls back to NULL
            # and the relinker cron picks it up later — same behaviour as
            # before, just without the noisy WARN on the happy path.
            await self._store_lua_round_teams(round_metadata)
            if spawn_stats:
                await self._store_lua_spawn_stats(round_metadata, spawn_stats)

            # Delete the webhook message to keep channel clean
            try:
                await message.delete()
                webhook_logger.debug("🗑️ Deleted STATS_READY webhook message")
            except Exception as e:
                webhook_logger.debug(f"Could not delete webhook message: {e}")

        except Exception as e:
            webhook_logger.error(f"❌ Error processing STATS_READY webhook: {e}", exc_info=True)
            await self.track_error("stats_ready_webhook", str(e), max_consecutive=3)
