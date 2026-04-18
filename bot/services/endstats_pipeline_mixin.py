"""UltimateETLegacyBot mixin: endstats pipeline methods.

Extracted from ultimate_bot.py in P3e Sprint 7 / C.2.

Contains the full endstats file processing flow:
- STATS_READY webhook → fetch + import
- Endstats round resolution (filename-based + DB matching)
- Retry scheduler + quality guards
- Post-stats proximity trigger

All methods live on UltimateETLegacyBot via mixin inheritance, so
``self.db``, ``self.config``, ``self.processed_files`` references
resolve as before.
"""
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime

import discord

from bot.logging_config import get_logger

logger = get_logger("bot.core")
webhook_logger = get_logger("bot.webhook")


class _EndstatsPipelineMixin:
    """Endstats pipeline methods for UltimateETLegacyBot."""

    async def _fetch_latest_stats_file(self, round_metadata: dict, trigger_message):
        """
        Fetch the latest stats file from game server after receiving STATS_READY.

        Uses the metadata to find the correct file and applies accurate timing data.
        """
        added_processing_marker = False
        try:
            from bot.automation.ssh_handler import SSHHandler

            # Build SSH config
            ssh_config = {
                "host": self.config.ssh_host,
                "port": self.config.ssh_port,
                "user": self.config.ssh_user,
                "key_path": self.config.ssh_key_path,
                "remote_path": self.config.ssh_remote_path,
            }

            # Find files matching the map and round (with retry for file not yet written)
            map_name = round_metadata['map_name']
            round_num = self._normalize_lua_round_for_metadata_paths(
                round_metadata.get('round_number')
            )
            target_time = round_metadata['round_end_unix']

            # Only consider files from the same day to avoid picking old files
            date_prefix = None
            if target_time:
                date_prefix = datetime.fromtimestamp(target_time).strftime('%Y-%m-%d')

            matching_files = []
            for attempt in range(4):
                files = await SSHHandler.list_remote_files(ssh_config)
                if not files:
                    webhook_logger.warning("No files found on server")
                    if attempt < 3:
                        await asyncio.sleep(5)
                        continue
                    return

                matching_files = []
                for f in files:
                    if map_name in f and f'-round-{round_num}.txt' in f and not f.endswith('-endstats.txt'):
                        # Filter to same-day files only
                        if date_prefix and not f.startswith(date_prefix):
                            continue
                        matching_files.append(f)

                if matching_files:
                    break
                if attempt < 3:
                    webhook_logger.info(
                        f"⏳ Stats file not yet on server for {map_name} R{round_num}, "
                        f"retry {attempt + 1}/3 in 5s..."
                    )
                    await asyncio.sleep(5)

            if not matching_files:
                webhook_logger.warning(f"No matching file found for {map_name} R{round_num} (after retries)")
                return

            def _extract_timestamp(filename: str) -> int | None:
                # Expect: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
                match = re.match(r'^(\d{4}-\d{2}-\d{2})-(\d{6})-.*-round-\d+\.txt$', filename)
                if not match:
                    return None
                date_str, time_str = match.groups()
                try:
                    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H%M%S")
                    return int(dt.timestamp())
                except ValueError:
                    return None

            # Choose the closest file to the Lua round_end_unix time if available
            best_file = None
            best_diff = None
            if target_time:
                for f in matching_files:
                    file_ts = _extract_timestamp(f)
                    if file_ts is None:
                        continue
                    diff = abs(file_ts - target_time)
                    if best_diff is None or diff < best_diff:
                        best_diff = diff
                        best_file = f

            if best_file:
                filename = best_file
                webhook_logger.info(
                    f"📥 Selected closest file: {filename} (Δ {best_diff}s)"
                )
                if best_diff is not None and best_diff > 1800:
                    webhook_logger.warning(
                        f"⚠️ Closest file is >30 minutes away from webhook timestamp (Δ {best_diff}s)"
                    )
            else:
                # Fallback: use most recent matching file
                matching_files.sort(reverse=True)  # Newest first (by filename timestamp)
                filename = matching_files[0]
                webhook_logger.info(f"📥 Selected newest file (fallback): {filename}")

            webhook_logger.info(f"📥 Found matching file: {filename}")

            # Check if already processed
            if not await self.file_tracker.should_process_file(filename):
                webhook_logger.debug(f"⏭️ File already processed: {filename}")
                return

            # Mark as processing
            self.file_tracker.processed_files.add(filename)
            added_processing_marker = True

            # Download the file
            local_path = await SSHHandler.download_file(
                ssh_config, filename, self.config.stats_directory
            )

            if not local_path:
                webhook_logger.error(f"❌ Failed to download: {filename}")
                if added_processing_marker:
                    self.file_tracker.processed_files.discard(filename)
                return

            webhook_logger.info(f"✅ Downloaded: {local_path}")
            await asyncio.sleep(1)  # Brief wait for file write

            # Process the file, passing the accurate metadata
            result = await self.process_gamestats_file(
                local_path, filename,
                override_metadata=round_metadata  # NEW: Pass Lua-provided metadata
            )

            if result and result.get('success'):
                webhook_logger.info("📊 Posting stats with accurate timing data")
                try:
                    await self.round_publisher.publish_round_stats(filename, result)
                    webhook_logger.info(f"✅ Successfully processed: {filename}")
                    # Trigger proximity scan after stats creates the round in DB
                    self._safe_create_task(
                        self._trigger_proximity_scan_after_stats(),
                        name="proximity_post_stats_scan"
                    )
                except Exception as post_err:
                    webhook_logger.error(f"❌ Discord post FAILED for {filename}: {post_err}", exc_info=True)
                    await self.track_error("discord_posting", f"Failed to post {filename}: {post_err}", max_consecutive=2)
            else:
                error_msg = result.get('error', 'Unknown') if result else 'No result'
                webhook_logger.warning(f"⚠️ Processing failed: {error_msg}")
                if added_processing_marker:
                    self.file_tracker.processed_files.discard(filename)

        except Exception as e:
            if added_processing_marker:
                self.file_tracker.processed_files.discard(filename)
            webhook_logger.error(f"❌ Error fetching stats file: {e}", exc_info=True)

    async def _trigger_proximity_scan_after_stats(self, round_id: int = None, delay_seconds: int = 5, max_retries: int = 3):
        """Trigger proximity import after stats creates the round in DB.

        Polls until the Proximity cog is available rather than sleeping a fixed duration.
        """
        for attempt in range(max_retries):
            try:
                await asyncio.sleep(delay_seconds)
                proximity_cog = self.get_cog("Proximity")
                if proximity_cog and hasattr(proximity_cog, '_scan_and_import'):
                    webhook_logger.info(
                        "🎯 Triggering proximity scan after stats import (attempt %d/%d, round_id=%s)",
                        attempt + 1, max_retries, round_id,
                    )
                    await proximity_cog._scan_and_import(force=True)
                    return
                webhook_logger.debug(
                    "Proximity cog not available (attempt %d/%d); retrying",
                    attempt + 1, max_retries,
                )
            except Exception as e:
                webhook_logger.warning(
                    "Post-stats proximity scan failed on attempt %d/%d (non-fatal): %s",
                    attempt + 1, max_retries, e,
                )
        webhook_logger.warning(
            "Proximity scan: gave up after %d attempts (round_id=%s)", max_retries, round_id
        )

    def _log_endstats_transition(
        self,
        log,
        source: str,
        state: str,
        filename: str,
        round_id: int | None = None,
        detail: str = "-",
        level: str = "info",
    ) -> None:
        round_value = round_id if round_id is not None else "null"
        log_fn = getattr(log, level, log.info)
        log_fn(
            "event=endstats_pipeline source=%s state=%s filename=%s round_id=%s detail=%s",
            source,
            state,
            filename,
            round_value,
            detail,
        )

    def _summarize_endstats_quality(self, endstats_data: dict | None) -> tuple[int, int]:
        if not isinstance(endstats_data, dict):
            return (0, 0)
        awards = endstats_data.get("awards")
        vs_stats = endstats_data.get("vs_stats")
        awards_count = len(awards) if isinstance(awards, list) else 0
        vs_count = len(vs_stats) if isinstance(vs_stats, list) else 0
        return (awards_count, vs_count)

    @staticmethod
    def _parse_endstats_filename_timestamp(filename: str) -> datetime | None:
        """Extract datetime from endstats filename (YYYY-MM-DD-HHMMSS-...)."""
        try:
            return datetime.strptime(filename[:17], "%Y-%m-%d-%H%M%S")
        except (ValueError, IndexError):
            return None

    def _are_endstats_from_same_match(
        self, filename_a: str, filename_b: str, max_minutes: int = 45
    ) -> bool:
        """Check if two endstats filenames are from the same match.

        Compares timestamps embedded in filenames. If the gap exceeds
        max_minutes, they are from different plays of the same map and
        must NOT supersede each other.
        Returns True (assume same match) when either timestamp is unparseable.
        """
        ts_a = self._parse_endstats_filename_timestamp(filename_a)
        ts_b = self._parse_endstats_filename_timestamp(filename_b)
        if ts_a is None or ts_b is None:
            return True  # Can't determine — safe default
        return abs((ts_a - ts_b).total_seconds()) <= max_minutes * 60

    def _select_richest_endstats(
        self,
        endstats_data: dict,
        local_path: str,
        filename: str,
        parse_fn,
        log,
    ) -> tuple:
        """When split endstats files exist, select the richer file by awards, vs_stats, then size."""
        import glob as globmod

        local_dir = os.path.dirname(local_path)
        base = filename.replace("-endstats.txt", "-endstats")
        candidates = globmod.glob(os.path.join(local_dir, base + "*.txt"))

        if len(candidates) <= 1:
            return endstats_data, local_path, filename

        best_data = endstats_data
        best_path = local_path
        best_filename = filename
        best_quality = self._summarize_endstats_quality(endstats_data)
        best_size = os.path.getsize(local_path) if os.path.exists(local_path) else 0

        for candidate_path in candidates:
            if candidate_path == local_path:
                continue
            try:
                candidate_data = parse_fn(candidate_path)
                if not candidate_data:
                    continue
                candidate_quality = self._summarize_endstats_quality(candidate_data)
                candidate_size = os.path.getsize(candidate_path)
                if (candidate_quality, candidate_size) > (best_quality, best_size):
                    best_data = candidate_data
                    best_path = candidate_path
                    best_filename = os.path.basename(candidate_path)
                    best_quality = candidate_quality
                    best_size = candidate_size
            except Exception as e:
                log.debug(f"Could not evaluate candidate endstats {candidate_path}: {e}")

        if best_path != local_path:
            log.info(
                f"Selecting richer endstats: {best_filename} "
                f"({best_size}b, {best_quality[0]} awards)"
            )
            self.processed_endstats_files.add(best_filename)

        return best_data, best_path, best_filename

    def _is_endstats_quality_better(
        self,
        incoming_quality: tuple[int, int],
        existing_quality: tuple[int, int],
    ) -> bool:
        return incoming_quality > existing_quality

    def _is_endstats_round_unique_violation(self, exc: Exception) -> bool:
        text = str(exc)
        return (
            "uq_processed_endstats_round_id" in text
            and "duplicate key value violates unique constraint" in text
        )

    async def _mark_endstats_filename_handled(
        self,
        filename: str,
        reason: str,
    ) -> None:
        """
        Persist filename-level dedupe so polling does not re-emit the same skip after restart.

        Store as success=TRUE with round_id=NULL to avoid round_id unique-index conflicts.
        """
        try:
            await self.db_adapter.execute(
                """
                INSERT INTO processed_endstats_files (filename, round_id, success, error_message, processed_at)
                VALUES ($1, NULL, TRUE, $2, CURRENT_TIMESTAMP)
                ON CONFLICT (filename) DO UPDATE SET
                    round_id = NULL,
                    success = TRUE,
                    error_message = EXCLUDED.error_message,
                    processed_at = CURRENT_TIMESTAMP
                """,
                (filename, reason),
            )
        except Exception as e:
            logger.debug(
                "Failed to persist endstats filename dedupe marker for %s: %s",
                filename,
                e,
            )

    async def _get_round_endstats_quality(self, round_id: int) -> tuple[int, int]:
        row = await self.db_adapter.fetch_one(
            """
            SELECT
                (SELECT COUNT(*) FROM round_awards WHERE round_id = $1) AS awards_count,
                (SELECT COUNT(*) FROM round_vs_stats WHERE round_id = $1) AS vs_count
            """,
            (round_id,),
        )
        if not row:
            return (0, 0)
        try:
            return (int(row[0] or 0), int(row[1] or 0))
        except (TypeError, ValueError, IndexError):
            return (0, 0)

    @staticmethod
    def _hhmmss_to_seconds(t: str) -> int | None:
        """Convert HHMMSS string to total seconds."""
        if not t or len(t) < 6:
            return None
        try:
            return int(t[:2]) * 3600 + int(t[2:4]) * 60 + int(t[4:6])
        except (ValueError, TypeError):
            return None

    async def _resolve_endstats_round_id(
        self,
        round_date: str | None,
        round_time: str | None,
        map_name: str | None,
        round_number: int | None,
        stats_filename: str,
        round_meta: dict,
    ) -> tuple:
        """
        Resolve round_id for an endstats file.

        Uses narrow time window (30s) to match endstats to the correct round,
        handling replayed maps (same map played multiple times in a session).
        Falls back to fuzzy round_linker if narrow match fails.

        Returns (round_id, resolve_method).
        """
        # Narrow time match: endstats timestamp is within ~2s of stats timestamp,
        # but we use 30s window for safety. This prevents matching against a
        # different play of the same map (which would be 5+ minutes apart).
        if round_date and round_time and map_name and round_number:
            target_secs = self._hhmmss_to_seconds(round_time)
            if target_secs is not None:
                rows = await self.db_adapter.fetch_all(
                    "SELECT id, round_time FROM rounds "
                    "WHERE round_date = ? AND map_name = ? AND round_number = ?",
                    (round_date, map_name, round_number),
                )
                if rows:
                    best_id = None
                    best_diff = 31  # 30-second max window
                    for row in rows:
                        row_secs = self._hhmmss_to_seconds(row[1])
                        if row_secs is not None:
                            diff = abs(row_secs - target_secs)
                            if diff < best_diff:
                                best_diff = diff
                                best_id = row[0]
                    if best_id is not None:
                        return best_id, "narrow_time_match"

        # Fallback: fuzzy round_linker (45min window, for edge cases)
        round_id = await self._resolve_round_id_for_metadata(stats_filename, round_meta)
        return round_id, "round_linker"

    async def _is_endstats_round_already_processed(
        self,
        round_id: int,
        filename: str,
        source: str,
        log,
        endstats_data: dict | None = None,
    ) -> bool:
        existing = await self.db_adapter.fetch_one(
            """
            SELECT filename, processed_at
            FROM processed_endstats_files
            WHERE round_id = $1
              AND success = TRUE
            ORDER BY processed_at DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (round_id,),
        )
        if not existing:
            return False

        existing_filename = existing[0]
        processed_at = existing[1]

        if existing_filename == filename:
            self._log_endstats_transition(
                log,
                source,
                "duplicate_round_skip",
                filename,
                round_id=round_id,
                detail=f"existing_filename={existing_filename} processed_at={processed_at}",
                level="warning",
            )
            return True

        # Timestamp guard: prevent supersede across different plays of the same map.
        # If the incoming file's timestamp is >45 min from the existing file,
        # they belong to different matches — do NOT allow supersede.
        if not self._are_endstats_from_same_match(filename, existing_filename):
            self._log_endstats_transition(
                log,
                source,
                "cross_match_supersede_blocked",
                filename,
                round_id=round_id,
                detail=(
                    f"existing_filename={existing_filename} "
                    f"timestamps_too_far_apart_for_same_match"
                ),
                level="warning",
            )
            await self._mark_endstats_filename_handled(
                filename,
                f"cross_match_supersede_blocked_existing:{existing_filename}",
            )
            return True

        incoming_quality = self._summarize_endstats_quality(endstats_data)
        existing_quality = await self._get_round_endstats_quality(round_id)
        if self._is_endstats_quality_better(incoming_quality, existing_quality):
            self._log_endstats_transition(
                log,
                source,
                "duplicate_round_upgrade_candidate",
                filename,
                round_id=round_id,
                detail=(
                    f"existing_filename={existing_filename} existing_quality={existing_quality} "
                    f"incoming_quality={incoming_quality}"
                ),
                level="warning",
            )
            return False

        self._log_endstats_transition(
            log,
            source,
            "duplicate_round_skip",
            filename,
            round_id=round_id,
            detail=(
                f"existing_filename={existing_filename} processed_at={processed_at} "
                f"existing_quality={existing_quality} incoming_quality={incoming_quality}"
            ),
            level="warning",
        )
        await self._mark_endstats_filename_handled(
            filename,
            (
                f"duplicate_round_skip_existing:{existing_filename} "
                f"existing_quality={existing_quality} incoming_quality={incoming_quality}"
            ),
        )
        return True

    async def _is_endstats_round_ready(
        self,
        round_id: int,
        filename: str,
        source: str,
        log,
    ) -> bool:
        row = await self.db_adapter.fetch_one(
            """
            SELECT r.round_status, COUNT(p.id) AS player_stats_rows
            FROM rounds r
            LEFT JOIN player_comprehensive_stats p ON p.round_id = r.id
            WHERE r.id = $1
            GROUP BY r.round_status
            """,
            (round_id,),
        )

        if not row:
            self._log_endstats_transition(
                log,
                source,
                "not_ready_round_missing",
                filename,
                round_id=round_id,
                detail="round_id_not_found",
                level="warning",
            )
            return False

        round_status = row[0]
        player_stats_rows = int(row[1] or 0)
        normalized_status = None
        if isinstance(round_status, str):
            normalized_status = round_status.strip().lower()

        status_allowed = (
            round_status is None
            or normalized_status in {"completed", "cancelled", "canceled", "substitution"}
        )
        if not status_allowed:
            self._log_endstats_transition(
                log,
                source,
                "not_ready_round_status",
                filename,
                round_id=round_id,
                detail=f"round_status={round_status}",
                level="warning",
            )
            return False

        if player_stats_rows <= 0:
            self._log_endstats_transition(
                log,
                source,
                "not_ready_missing_player_stats",
                filename,
                round_id=round_id,
                detail=f"player_stats_rows={player_stats_rows}",
                level="warning",
            )
            return False

        self._log_endstats_transition(
            log,
            source,
            "ready_to_publish",
            filename,
            round_id=round_id,
            detail=f"round_status={round_status} player_stats_rows={player_stats_rows}",
        )
        return True

    def _get_endstats_retry_delay(self, attempt: int) -> int:
        delay = self.endstats_retry_base_delay * (2 ** (attempt - 1))
        return min(delay, self.endstats_retry_max_delay)

    def _clear_endstats_retry_state(self, filename: str) -> None:
        self.endstats_retry_counts.pop(filename, None)
        task = self.endstats_retry_tasks.pop(filename, None)
        current_task = asyncio.current_task()
        if task and not task.done() and task is not current_task:
            task.cancel()

    async def _schedule_endstats_retry(
        self,
        filename: str,
        local_path: str,
        endstats_data: dict,
        trigger_message,
    ) -> None:
        existing = self.endstats_retry_tasks.get(filename)
        if existing and not existing.done():
            current_task = asyncio.current_task()
            if existing is current_task:
                # Called from inside the active retry task; allow scheduling the next attempt.
                self.endstats_retry_tasks.pop(filename, None)
            else:
                webhook_logger.debug(f"⏳ Retry already scheduled for endstats: {filename}")
                return
        else:
            # Clear stale/done task reference so it doesn't block future scheduling
            self.endstats_retry_tasks.pop(filename, None)

        attempt = self.endstats_retry_counts.get(filename, 0) + 1
        self.endstats_retry_counts[filename] = attempt

        if attempt > self.endstats_retry_max_attempts:
            webhook_logger.error(
                f"❌ Endstats retry limit reached ({self.endstats_retry_max_attempts}) for {filename}"
            )
            self.processed_endstats_files.discard(filename)
            self._clear_endstats_retry_state(filename)
            try:
                if trigger_message:
                    await trigger_message.add_reaction('⚠️')
            except discord.DiscordException:
                pass
            return

        delay = self._get_endstats_retry_delay(attempt)
        webhook_logger.warning(
            f"⏳ Scheduling endstats retry {attempt}/{self.endstats_retry_max_attempts} "
            f"in {delay}s for {filename}"
        )

        async def _retry():
            await asyncio.sleep(delay)
            await self._retry_webhook_endstats_link(
                filename, local_path, endstats_data, trigger_message
            )

        self.endstats_retry_tasks[filename] = self._safe_create_task(_retry(), name=f"endstats_retry_{filename}")

    async def _retry_webhook_endstats_link(
        self,
        filename: str,
        local_path: str,
        endstats_data: dict,
        trigger_message,
    ) -> None:
        source = "webhook_retry"
        try:
            attempt = self.endstats_retry_counts.get(filename, 0)
            self._log_endstats_transition(
                webhook_logger,
                source,
                "retry_attempt",
                filename,
                detail=f"attempt={attempt}/{self.endstats_retry_max_attempts}",
            )
            webhook_logger.info(
                f"🔄 Endstats retry attempt {attempt}/{self.endstats_retry_max_attempts} for {filename}"
            )
            # If already processed in DB, stop retrying
            check_query = "SELECT 1 FROM processed_endstats_files WHERE filename = $1"
            result = await self.db_adapter.fetch_one(check_query, (filename,))
            if result:
                self._log_endstats_transition(
                    webhook_logger,
                    source,
                    "already_processed_filename",
                    filename,
                )
                self._clear_endstats_retry_state(filename)
                return

            metadata = endstats_data.get('metadata') or {}
            round_date = metadata.get('date')
            map_name = metadata.get('map_name')
            round_number = metadata.get('round_number')
            round_time = metadata.get('time')

            if not (round_date and map_name and round_number):
                webhook_logger.error(f"❌ Missing metadata for endstats retry: {filename}")
                self.processed_endstats_files.discard(filename)
                self._clear_endstats_retry_state(filename)
                return

            round_meta = {
                'map_name': map_name,
                'round_number': round_number,
                'round_date': round_date,
                'round_time': round_time,
            }
            stats_filename = filename.replace("-endstats.txt", ".txt")
            round_id, resolve_method = await self._resolve_endstats_round_id(
                round_date, round_time, map_name, round_number,
                stats_filename, round_meta,
            )

            if not round_id:
                self._log_endstats_transition(
                    webhook_logger,
                    source,
                    "waiting_round_id",
                    filename,
                    detail="round_id_unresolved",
                    level="warning",
                )
                await self._schedule_endstats_retry(
                    filename, local_path, endstats_data, trigger_message
                )
                return

            self._log_endstats_transition(
                webhook_logger,
                source,
                "round_id_resolved",
                filename,
                round_id=round_id,
                detail=f"resolve_method={resolve_method}",
            )

            if await self._is_endstats_round_already_processed(
                round_id, filename, source, webhook_logger, endstats_data
            ):
                self._clear_endstats_retry_state(filename)
                return

            if not await self._is_endstats_round_ready(
                round_id, filename, source, webhook_logger
            ):
                await self._schedule_endstats_retry(
                    filename, local_path, endstats_data, trigger_message
                )
                return

            published = await self._store_endstats_and_publish(
                filename,
                endstats_data,
                round_id,
                round_date,
                map_name,
                round_number,
                webhook_logger,
                source=source,
            )
            if not published:
                await self._schedule_endstats_retry(
                    filename, local_path, endstats_data, trigger_message
                )
                return

            self._clear_endstats_retry_state(filename)

            try:
                if trigger_message:
                    await trigger_message.delete()
                    webhook_logger.debug("🗑️ Deleted endstats trigger message (retry)")
            except Exception as e:
                webhook_logger.debug(f"Could not delete trigger message: {e}")

        except Exception as e:
            webhook_logger.error(f"❌ Error during endstats retry: {e}", exc_info=True)
            # Only clear task reference, preserve retry count so next attempt increments correctly
            self.endstats_retry_tasks.pop(filename, None)

    async def _store_endstats_and_publish(
        self,
        filename: str,
        endstats_data: dict,
        round_id: int,
        round_date: str,
        map_name: str,
        round_number: int,
        log,
        source: str = "unknown",
    ) -> bool:
        awards = endstats_data.get('awards', [])
        vs_stats = endstats_data.get('vs_stats', [])
        incoming_quality = self._summarize_endstats_quality(endstats_data)
        should_publish = True

        async with self.db_adapter.transaction():
            # If this round already has a successful endstats post, skip.
            existing_success = await self.db_adapter.fetch_one(
                """
                SELECT filename, processed_at
                FROM processed_endstats_files
                WHERE round_id = $1
                  AND success = TRUE
                ORDER BY processed_at DESC NULLS LAST, id DESC
                LIMIT 1
                """,
                (round_id,),
            )
            if existing_success:
                existing_filename = existing_success[0]
                processed_at = existing_success[1]
                if existing_filename == filename:
                    self._log_endstats_transition(
                        log,
                        source,
                        "claim_conflict_skip",
                        filename,
                        round_id=round_id,
                        detail=f"existing_filename={existing_filename} processed_at={processed_at}",
                        level="warning",
                    )
                    return True

                # Timestamp guard: block supersede across different plays of the same map.
                if not self._are_endstats_from_same_match(filename, existing_filename):
                    self._log_endstats_transition(
                        log,
                        source,
                        "cross_match_supersede_blocked",
                        filename,
                        round_id=round_id,
                        detail=(
                            f"existing_filename={existing_filename} "
                            f"timestamps_too_far_apart_for_same_match"
                        ),
                        level="warning",
                    )
                    await self._mark_endstats_filename_handled(
                        filename,
                        f"cross_match_supersede_blocked_existing:{existing_filename}",
                    )
                    return True

                existing_quality = await self._get_round_endstats_quality(round_id)
                if not self._is_endstats_quality_better(incoming_quality, existing_quality):
                    self._log_endstats_transition(
                        log,
                        source,
                        "duplicate_poorer_skip",
                        filename,
                        round_id=round_id,
                        detail=(
                            f"existing_filename={existing_filename} processed_at={processed_at} "
                            f"existing_quality={existing_quality} incoming_quality={incoming_quality}"
                        ),
                        level="warning",
                    )
                    await self._mark_endstats_filename_handled(
                        filename,
                        (
                            f"duplicate_poorer_skip_existing:{existing_filename} "
                            f"existing_quality={existing_quality} incoming_quality={incoming_quality}"
                        ),
                    )
                    return True

                should_publish = False
                await self.db_adapter.execute(
                    """
                    UPDATE processed_endstats_files
                    SET success = FALSE,
                        error_message = $2,
                        processed_at = CURRENT_TIMESTAMP
                    WHERE round_id = $1
                      AND success = TRUE
                    """,
                    (round_id, f"superseded_by_richer_payload:{filename}"),
                )
                self._log_endstats_transition(
                    log,
                    source,
                    "duplicate_richer_selected",
                    filename,
                    round_id=round_id,
                    detail=(
                        f"replacing_filename={existing_filename} "
                        f"existing_quality={existing_quality} incoming_quality={incoming_quality}"
                    ),
                    level="warning",
                )

            # Claim processing slot first so duplicate filenames/round_ids short-circuit.
            claim_row = await self.db_adapter.fetch_one(
                """
                INSERT INTO processed_endstats_files (filename, round_id, success, error_message, processed_at)
                VALUES ($1, $2, FALSE, NULL, CURRENT_TIMESTAMP)
                ON CONFLICT (filename) DO UPDATE SET
                    round_id = EXCLUDED.round_id,
                    success = FALSE,
                    error_message = NULL,
                    processed_at = CURRENT_TIMESTAMP
                RETURNING id
                """,
                (filename, round_id),
            )

            if not claim_row:
                self._log_endstats_transition(
                    log,
                    source,
                    "claim_conflict_skip",
                    filename,
                    round_id=round_id,
                    detail="claim_upsert_failed",
                    level="warning",
                )
                return True

            self._log_endstats_transition(
                log,
                source,
                "claim_acquired",
                filename,
                round_id=round_id,
                detail=f"claim_id={claim_row[0]}",
            )

            # Keep endstats rows idempotent across retries.
            await self.db_adapter.execute(
                "DELETE FROM round_awards WHERE round_id = $1",
                (round_id,),
            )
            await self.db_adapter.execute(
                "DELETE FROM round_vs_stats WHERE round_id = $1",
                (round_id,),
            )

            # Store awards in database
            for award in awards:
                player_guid = None
                alias_query = """
                    SELECT guid FROM player_aliases
                    WHERE alias = $1
                    ORDER BY last_seen DESC LIMIT 1
                """
                alias_result = await self.db_adapter.fetch_one(alias_query, (award['player'],))
                if alias_result:
                    player_guid = alias_result[0]

                insert_query = """
                    INSERT INTO round_awards
                    (round_id, round_date, map_name, round_number, award_name,
                     player_name, player_guid, award_value, award_value_numeric)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """
                await self.db_adapter.execute(insert_query, (
                    round_id, round_date, map_name, round_number,
                    award['name'], award['player'], player_guid,
                    award['value'], award.get('numeric')
                ))

            log.info(f"✅ Stored {len(awards)} awards")

            # Store VS stats in database (with subject context from VS_HEADER)
            for vs in vs_stats:
                # Resolve opponent GUID
                opponent_guid = None
                alias_query = """
                    SELECT guid FROM player_aliases
                    WHERE alias = $1
                    ORDER BY last_seen DESC LIMIT 1
                """
                alias_result = await self.db_adapter.fetch_one(alias_query, (vs['player'],))
                if alias_result:
                    opponent_guid = alias_result[0]

                # Subject (the player whose stats these are) from VS_HEADER
                subject_name = vs.get('subject')
                subject_guid = vs.get('subject_guid')
                # If parser didn't provide GUID, try to resolve from alias
                if subject_name and not subject_guid:
                    subj_result = await self.db_adapter.fetch_one(alias_query, (subject_name,))
                    if subj_result:
                        subject_guid = subj_result[0]

                insert_query = """
                    INSERT INTO round_vs_stats
                    (round_id, round_date, map_name, round_number,
                     player_name, player_guid, kills, deaths,
                     subject_name, subject_guid)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """
                await self.db_adapter.execute(insert_query, (
                    round_id, round_date, map_name, round_number,
                    vs['player'], opponent_guid, vs['kills'], vs['deaths'],
                    subject_name, subject_guid
                ))

            log.info(f"✅ Stored {len(vs_stats)} VS stats")

        self._log_endstats_transition(
            log,
            source,
            "db_persisted",
            filename,
            round_id=round_id,
            detail=f"awards={len(awards)} vs_rows={len(vs_stats)}",
        )

        # 🔗 CORRELATION: notify of endstats arrival
        if hasattr(self, 'correlation_service') and self.correlation_service:
            try:
                mid_row = await self.db_adapter.fetch_one(
                    "SELECT match_id FROM rounds WHERE id = $1", (round_id,)
                )
                if mid_row and mid_row[0]:
                    await self.correlation_service.on_endstats_processed(
                        match_id=mid_row[0],
                        round_number=round_number,
                        map_name=map_name,
                    )
            except Exception as corr_err:
                log.warning(f"[CORRELATION] endstats hook error (non-fatal): {corr_err}")

        published = True
        if should_publish:
            published = await self.round_publisher.publish_endstats(
                filename, endstats_data, round_id, map_name, round_number
            )
        else:
            self._log_endstats_transition(
                log,
                source,
                "publish_skipped_round_already_posted",
                filename,
                round_id=round_id,
                detail="richer_payload_applied_db_only",
                level="warning",
            )

        if not published:
            await self.db_adapter.execute(
                """
                UPDATE processed_endstats_files
                SET round_id = $2,
                    success = FALSE,
                    error_message = $3,
                    processed_at = CURRENT_TIMESTAMP
                WHERE filename = $1
                """,
                (filename, round_id, "publish_failed"),
            )
            self._log_endstats_transition(
                log,
                source,
                "publish_failed",
                filename,
                round_id=round_id,
                detail="publish_endstats returned false",
                level="warning",
            )
            return False

        try:
            await self.db_adapter.execute(
                """
                UPDATE processed_endstats_files
                SET round_id = $2,
                    success = TRUE,
                    error_message = NULL,
                    processed_at = CURRENT_TIMESTAMP
                WHERE filename = $1
                """,
                (filename, round_id),
            )
        except Exception as e:
            if not self._is_endstats_round_unique_violation(e):
                raise

            existing_success = await self.db_adapter.fetch_one(
                """
                SELECT filename, processed_at
                FROM processed_endstats_files
                WHERE round_id = $1
                  AND success = TRUE
                ORDER BY processed_at DESC NULLS LAST, id DESC
                LIMIT 1
                """,
                (round_id,),
            )
            existing_filename = existing_success[0] if existing_success else "unknown"
            processed_at = existing_success[1] if existing_success else "unknown"

            await self.db_adapter.execute(
                """
                UPDATE processed_endstats_files
                SET round_id = $2,
                    success = FALSE,
                    error_message = $3,
                    processed_at = CURRENT_TIMESTAMP
                WHERE filename = $1
                """,
                (
                    filename,
                    round_id,
                    f"duplicate_round_conflict_existing_success:{existing_filename}",
                ),
            )

            self._log_endstats_transition(
                log,
                source,
                "race_conflict_skip",
                filename,
                round_id=round_id,
                detail=f"existing_filename={existing_filename} processed_at={processed_at}",
                level="warning",
            )
            await self._mark_endstats_filename_handled(
                filename,
                f"duplicate_round_conflict_existing_success:{existing_filename}",
            )
            return True

        self._log_endstats_transition(
            log,
            source,
            "published",
            filename,
            round_id=round_id,
        )
        return True

    async def _process_endstats_file(self, local_path: str, filename: str):
        """
        Process an endstats file downloaded via SSH monitoring.

        This is the non-webhook version - file is already downloaded.
        Parses awards/VS stats, stores in DB, posts embed.
        Endstats file: YYYY-MM-DD-HHMMSS-mapname-round-N-endstats.txt
        """
        source = "polling"
        try:
            self._log_endstats_transition(
                logger,
                source,
                "received",
                filename,
                detail=f"local_path={local_path}",
            )

            # Import parser
            from bot.endstats_parser import parse_endstats_file

            # Check if already processed (prevent duplicates)
            # First check in-memory set (fast, prevents race with webhook)
            if filename in self.processed_endstats_files:
                self._log_endstats_transition(
                    logger,
                    source,
                    "in_memory_skip",
                    filename,
                    detail="already_in_memory_set",
                )
                return

            # Then check database table
            check_query = "SELECT 1 FROM processed_endstats_files WHERE filename = $1"
            result = await self.db_adapter.fetch_one(check_query, (filename,))
            if result:
                self._log_endstats_transition(
                    logger,
                    source,
                    "db_filename_skip",
                    filename,
                    detail="already_processed_filename",
                )
                self.processed_endstats_files.add(filename)  # Sync to memory
                return

            # IMMEDIATELY mark as being processed to prevent race with webhook
            self.processed_endstats_files.add(filename)

            # Parse the endstats file
            endstats_data = parse_endstats_file(local_path)

            if not endstats_data:
                logger.error(f"❌ Failed to parse endstats: {filename}")
                return

            # Select richest endstats when split files exist
            endstats_data, local_path, filename = self._select_richest_endstats(
                endstats_data, local_path, filename, parse_endstats_file, logger
            )

            metadata = endstats_data['metadata']
            awards = endstats_data['awards']
            vs_stats = endstats_data['vs_stats']

            logger.info(
                f"📊 Parsed endstats: {len(awards)} awards, {len(vs_stats)} VS stats"
            )

            # Find matching round using shared resolver (avoids timestamp mismatch)
            round_date = metadata.get('date')
            map_name = metadata.get('map_name')
            round_number = metadata.get('round_number')
            round_time = metadata.get('time')

            round_meta = {
                'map_name': map_name,
                'round_number': round_number,
                'round_date': round_date,
                'round_time': round_time,
            }

            stats_filename = filename.replace("-endstats.txt", ".txt")
            round_id, resolve_method = await self._resolve_endstats_round_id(
                round_date, round_time, map_name, round_number,
                stats_filename, round_meta,
            )

            if not round_id:
                # Track retry attempts to prevent infinite loop
                attempt = self.endstats_retry_counts.get(filename, 0) + 1
                self.endstats_retry_counts[filename] = attempt

                if attempt > self.endstats_retry_max_attempts:
                    logger.error(
                        f"❌ Endstats polling retry limit reached ({self.endstats_retry_max_attempts}) "
                        f"for {filename} — marking as failed"
                    )
                    try:
                        await self.db_adapter.execute(
                            "INSERT INTO processed_endstats_files (filename, success, error_message) "
                            "VALUES ($1, FALSE, $2) ON CONFLICT (filename) DO NOTHING",
                            (filename, f"round_id_unresolved_after_{self.endstats_retry_max_attempts}_attempts"),
                        )
                    except Exception as mark_err:
                        logger.debug(f"Failed to mark endstats as failed: {mark_err}")
                    self.endstats_retry_counts.pop(filename, None)
                    # Keep in processed set so it won't be retried
                    return

                self._log_endstats_transition(
                    logger,
                    source,
                    "waiting_round_id",
                    filename,
                    detail=f"round_id_unresolved_poll_attempt_{attempt}/{self.endstats_retry_max_attempts}",
                    level="warning",
                )
                # Remove from in-memory set to allow retry on next polling cycle
                self.processed_endstats_files.discard(filename)
                return

            self._log_endstats_transition(
                logger,
                source,
                "round_id_resolved",
                filename,
                round_id=round_id,
                detail=f"resolve_method={resolve_method}",
            )

            if await self._is_endstats_round_already_processed(
                round_id, filename, source, logger, endstats_data
            ):
                return

            if not await self._is_endstats_round_ready(
                round_id, filename, source, logger
            ):
                # Not ready in polling path: release in-memory marker and retry next cycle.
                self.processed_endstats_files.discard(filename)
                return

            published = await self._store_endstats_and_publish(
                filename,
                endstats_data,
                round_id,
                round_date,
                map_name,
                round_number,
                logger,
                source=source,
            )
            if not published:
                # Release in-memory marker so polling can retry later.
                self.processed_endstats_files.discard(filename)

        except Exception as e:
            logger.error(f"❌ Error processing endstats file: {e}", exc_info=True)
            await self.track_error("endstats_processing", str(e), max_consecutive=3)

    async def _process_webhook_triggered_endstats(self, filename: str, trigger_message):
        """
        Process an endstats file triggered by webhook notification.

        Downloads file via SSH, parses awards/VS stats, stores in DB, posts embed.
        Endstats file: YYYY-MM-DD-HHMMSS-mapname-round-N-endstats.txt
        """
        source = "webhook"
        try:
            self._log_endstats_transition(
                webhook_logger,
                source,
                "received",
                filename,
            )

            # Import parser
            from bot.endstats_parser import parse_endstats_file

            # Check if already processed (prevent duplicates)
            # First check in-memory set (fast, prevents race with polling)
            if filename in self.processed_endstats_files:
                self._log_endstats_transition(
                    webhook_logger,
                    source,
                    "in_memory_skip",
                    filename,
                    detail="already_in_memory_set",
                )
                try:
                    await trigger_message.delete()
                except discord.DiscordException:
                    logger.debug("Discord notification failed (non-critical)")
                return

            # Then check database table
            check_query = "SELECT 1 FROM processed_endstats_files WHERE filename = $1"
            result = await self.db_adapter.fetch_one(check_query, (filename,))
            if result:
                self._log_endstats_transition(
                    webhook_logger,
                    source,
                    "db_filename_skip",
                    filename,
                    detail="already_processed_filename",
                )
                self.processed_endstats_files.add(filename)  # Sync to memory
                try:
                    await trigger_message.delete()
                except discord.DiscordException:
                    logger.debug("Discord notification failed (non-critical)")
                return

            # IMMEDIATELY mark as being processed to prevent race with polling
            self.processed_endstats_files.add(filename)

            # Build SSH config
            ssh_config = {
                "host": self.config.ssh_host,
                "port": self.config.ssh_port,
                "user": self.config.ssh_user,
                "key_path": self.config.ssh_key_path,
                "remote_path": self.config.ssh_remote_path,
            }

            # Download file via SSH
            from bot.automation.ssh_handler import SSHHandler
            local_path = await SSHHandler.download_file(
                ssh_config, filename, self.config.stats_directory
            )

            if not local_path:
                webhook_logger.error(f"❌ Failed to download endstats: {filename}")
                try:
                    await trigger_message.add_reaction('❌')
                    await trigger_message.reply(f"⚠️ Failed to download `{filename}` from server.")
                except discord.DiscordException:
                    logger.debug("Discord notification failed (non-critical)")
                return

            webhook_logger.info(f"✅ Downloaded endstats: {local_path}")

            # Wait for file to fully write
            await asyncio.sleep(1)

            # Parse the endstats file
            endstats_data = parse_endstats_file(local_path)

            if not endstats_data:
                webhook_logger.error(f"❌ Failed to parse endstats: {filename}")
                try:
                    await trigger_message.add_reaction('⚠️')
                except discord.DiscordException:
                    logger.debug("Discord notification failed (non-critical)")
                return

            # Select richest endstats when split files exist
            endstats_data, local_path, filename = self._select_richest_endstats(
                endstats_data, local_path, filename, parse_endstats_file, webhook_logger
            )

            metadata = endstats_data['metadata']
            awards = endstats_data['awards']
            vs_stats = endstats_data['vs_stats']

            webhook_logger.info(
                f"📊 Parsed endstats: {len(awards)} awards, {len(vs_stats)} VS stats"
            )

            # Find matching round using shared resolver (avoids timestamp mismatch)
            round_date = metadata.get('date')
            map_name = metadata.get('map_name')
            round_number = metadata.get('round_number')
            round_time = metadata.get('time')

            round_meta = {
                'map_name': map_name,
                'round_number': round_number,
                'round_date': round_date,
                'round_time': round_time,
            }
            stats_filename = filename.replace("-endstats.txt", ".txt")
            round_id, resolve_method = await self._resolve_endstats_round_id(
                round_date, round_time, map_name, round_number,
                stats_filename, round_meta,
            )

            if not round_id:
                self._log_endstats_transition(
                    webhook_logger,
                    source,
                    "waiting_round_id",
                    filename,
                    detail="round_id_unresolved_schedule_retry",
                    level="warning",
                )
                try:
                    await trigger_message.add_reaction('⏳')
                except discord.DiscordException:
                    logger.debug("Discord notification failed (non-critical)")
                await self._schedule_endstats_retry(
                    filename, local_path, endstats_data, trigger_message
                )
                return

            self._log_endstats_transition(
                webhook_logger,
                source,
                "round_id_resolved",
                filename,
                round_id=round_id,
                detail=f"resolve_method={resolve_method}",
            )

            if await self._is_endstats_round_already_processed(
                round_id, filename, source, webhook_logger, endstats_data
            ):
                try:
                    await trigger_message.delete()
                except discord.DiscordException:
                    logger.debug("Discord notification failed (non-critical)")
                return

            if not await self._is_endstats_round_ready(
                round_id, filename, source, webhook_logger
            ):
                try:
                    await trigger_message.add_reaction('⏳')
                except discord.DiscordException:
                    logger.debug("Discord notification failed (non-critical)")
                await self._schedule_endstats_retry(
                    filename, local_path, endstats_data, trigger_message
                )
                return

            published = await self._store_endstats_and_publish(
                filename,
                endstats_data,
                round_id,
                round_date,
                map_name,
                round_number,
                webhook_logger,
                source=source,
            )
            if not published:
                try:
                    await trigger_message.add_reaction('⏳')
                except discord.DiscordException:
                    logger.debug("Discord notification failed (non-critical)")
                await self._schedule_endstats_retry(
                    filename, local_path, endstats_data, trigger_message
                )
                return

            # Delete the trigger message
            try:
                await trigger_message.delete()
                webhook_logger.debug("🗑️ Deleted endstats trigger message")
            except Exception as e:
                webhook_logger.debug(f"Could not delete trigger message: {e}")

        except Exception as e:
            webhook_logger.error(f"❌ Error processing endstats file: {e}", exc_info=True)
            try:
                await trigger_message.add_reaction('🚨')
                await trigger_message.reply(f"🚨 Error processing endstats `{filename}`. Check logs.")
            except discord.DiscordException:
                pass
            await self.track_error("endstats_processing", str(e), max_consecutive=3)
