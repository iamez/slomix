"""ProximityCog mixin: Engagement file scanning, SSH fetch, import pipeline.

Extracted from bot/cogs/proximity_cog.py in Mega Audit v4 / Sprint 3.

All methods live on ProximityCog via mixin inheritance.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from discord.ext import tasks

try:
    from proximity.parser import ProximityParserV4
    _PARSER_AVAILABLE = True
except ImportError:
    ProximityParserV4 = None
    _PARSER_AVAILABLE = False

logger = logging.getLogger("bot.cogs.proximity")


class _ProximityIngestionMixin:
    """Engagement file scanning, SSH fetch, import pipeline for ProximityCog."""

    def _remote_index_path(self) -> str:
        return os.path.join(self.local_dir, ".processed_proximity.txt")

    def _local_index_path(self) -> str:
        return os.path.join(self.local_dir, ".processed_proximity_local.txt")

    def _load_remote_index(self) -> None:
        index_path = self._remote_index_path()
        if not os.path.exists(index_path):
            return
        try:
            with open(index_path, encoding="utf-8") as handle:
                for line in handle:
                    filename = line.strip()
                    if filename:
                        self.processed_remote_files.add(filename)
        except Exception as e:
            logger.debug(f"Proximity index load failed: {e}")

    def _mark_remote_processed(self, filename: str) -> None:
        if not filename or filename in self.processed_remote_files:
            return
        self.processed_remote_files.add(filename)
        try:
            with open(self._remote_index_path(), "a", encoding="utf-8") as handle:
                handle.write(f"{filename}\n")
        except Exception as e:
            logger.debug(f"Proximity index update failed: {e}")

    def _load_local_index(self) -> None:
        index_path = self._local_index_path()
        if not os.path.exists(index_path):
            return
        try:
            with open(index_path, encoding="utf-8") as handle:
                for line in handle:
                    filename = line.strip()
                    if filename:
                        self.processed_engagement_files.add(filename)
        except Exception as e:
            logger.debug(f"Proximity local index load failed: {e}")

    def _mark_local_processed(self, filename: str) -> None:
        if not filename or filename in self.processed_engagement_files:
            return
        self.processed_engagement_files.add(filename)
        try:
            with open(self._local_index_path(), "a", encoding="utf-8") as handle:
                handle.write(f"{filename}\n")
        except Exception as e:
            logger.debug(f"Proximity local index update failed: {e}")

    def _extract_timestamp(self, filename: str) -> int | None:
        match = re.match(r"^(\d{4}-\d{2}-\d{2})-(\d{6})-.*_engagements\.txt$", filename)
        if not match:
            return None
        date_str, time_str = match.groups()
        try:
            from datetime import datetime
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H%M%S")
            return int(dt.timestamp())
        except ValueError:
            return None

    async def _notify_correlation(self, filename: str) -> None:
        """Notify the correlation service that proximity data arrived for a round."""
        try:
            correlation_svc = getattr(self.bot, 'correlation_service', None)
            if not correlation_svc:
                return

            # Parse filename: 2026-04-02-220403-etl_adlernest-round-1_engagements.txt
            match = re.match(
                r'^(\d{4}-\d{2}-\d{2}-\d{6})-(.+)-round-(\d+)_engagements\.txt$',
                filename,
            )
            if not match:
                return

            match_id = match.group(1)    # 2026-04-02-220403
            map_name = match.group(2)    # etl_adlernest
            round_number = int(match.group(3))  # 1

            await correlation_svc.on_proximity_imported(match_id, round_number, map_name)
        except Exception as e:
            logger.warning(f"Correlation notify failed (non-fatal): {e}")

    def _load_objective_coords(self) -> dict:
        template_path = Path("proximity/objective_coords_template.json")
        if not template_path.exists():
            return {}
        try:
            return json.loads(template_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"⚠️ Failed to read objective coords template: {e}")
            return {}

    async def _fetch_remote_files(self) -> None:
        if not self.ssh_enabled or not self.remote_path or not self.enabled:
            return
        try:
            from bot.automation.ssh_handler import SSHHandler
        except Exception as e:
            logger.warning(f"⚠️ Proximity SSH handler unavailable: {e}")
            return

        ssh_config = {
            "host": self.bot.config.ssh_host,
            "port": self.bot.config.ssh_port,
            "user": self.bot.config.ssh_user,
            "key_path": self.bot.config.ssh_key_path,
            "remote_path": self.remote_path,
        }

        if not all([ssh_config["host"], ssh_config["user"], ssh_config["key_path"], ssh_config["remote_path"]]):
            if self.debug_log:
                logger.debug("Proximity SSH config incomplete")
            return

        remote_files = await SSHHandler.list_remote_files(
            ssh_config,
            extensions=[".txt"],
            exclude_suffixes=None,
        )
        if not remote_files:
            return

        proximity_files = [f for f in remote_files if f.endswith("_engagements.txt")]
        if not proximity_files:
            return

        cutoff = None
        if self.lookback_hours and self.lookback_hours > 0:
            cutoff = (datetime.now().timestamp() - (self.lookback_hours * 3600))

        for filename in sorted(proximity_files):
            if filename in self.processed_remote_files:
                continue
            ts = self._extract_timestamp(filename)
            if cutoff and ts and ts < cutoff:
                self._mark_remote_processed(filename)
                continue

            if self.debug_log:
                logger.info(f"📥 Downloading proximity file: {filename}")

            local_path = await SSHHandler.download_file(
                ssh_config,
                filename,
                self.local_dir,
            )
            if not local_path:
                logger.warning(f"⚠️ Failed to download proximity file: {filename}")
                continue

            self._mark_remote_processed(filename)

    async def _scan_and_import(self, force: bool = False) -> None:
        if not self.enabled:
            return
        if not force and not self.bot.config.proximity_auto_import:
            return

        if self._scan_lock.locked():
            logger.debug("Proximity scan already in progress, skipping")
            return

        async with self._scan_lock:
            try:
                self.last_scan_time = datetime.now()

                # Fetch new files from remote server if configured
                await self._fetch_remote_files()

                # Find all engagement files
                stats_path = Path(self.local_dir)
                if not stats_path.exists():
                    if self.debug_log:
                        logger.debug(f"Stats directory not found: {stats_path}")
                    return

                engagement_files = list(stats_path.glob("*_engagements.txt"))

                # On startup, respect lookback to avoid replaying stale local files.
                startup_cutoff = None
                if (
                    not force
                    and not self._startup_scan_completed
                    and self.lookback_hours
                    and self.lookback_hours > 0
                ):
                    startup_cutoff = int(datetime.now().timestamp() - (self.lookback_hours * 3600))

                new_files = [
                    f for f in engagement_files
                    if f.name not in self.processed_engagement_files
                ]

                if new_files and self.debug_log:
                    logger.info(f"🎯 Found {len(new_files)} new engagement files")

                for filepath in sorted(new_files, key=lambda p: p.name):
                    if startup_cutoff is not None:
                        ts = self._extract_timestamp(filepath.name)
                        if ts and ts < startup_cutoff:
                            self._mark_local_processed(filepath.name)
                            continue
                    await self._import_engagement_file(filepath)

            except Exception as e:
                self.error_count += 1
                logger.error(f"Error in engagement scan: {e}", exc_info=True)
            finally:
                if not self._startup_scan_completed:
                    self._startup_scan_completed = True

    @tasks.loop(minutes=2)
    async def scan_engagement_files(self):
        """Periodically scan for new engagement files and import them"""
        await self._scan_and_import(force=False)

    @scan_engagement_files.before_loop
    async def before_scan(self):
        """Wait for bot to be ready before starting scan task"""
        await self.bot.wait_until_ready()

    async def _resolve_session_date(
        self, file_date: str, file_time: str, parts: list, filename: str
    ) -> str:
        """Resolve the correct session date, handling midnight crossovers.

        If a round starts before midnight (23:xx) on day N but the proximity
        file is written after midnight on day N+1, we need to link it to
        the session on day N. Strategy:
        1. Check if a matching round exists on the file's date
        2. If not and time is in the early hours (00:00-05:00), check previous date
        3. Fall back to file date
        """
        # Extract map name from filename parts
        # Format: YYYY-MM-DD-HHMMSS-mapname-round-N_engagements.txt
        # parts[4:-1] could be mapname pieces, last part is "N_engagements.txt"
        try:
            # Find round number from the part containing "_engagements"
            for p in parts:
                if '_engagements' in p or '_proximity' in p:
                    break

            map_parts = parts[4:]
            # Remove the "round" keyword and everything after
            map_name_parts = []
            for i, p in enumerate(map_parts):
                if p == 'round':
                    break
                map_name_parts.append(p)
            map_name = '-'.join(map_name_parts) if map_name_parts else None

            if not map_name:
                return file_date

            # Step 1: Check for round on same date
            query = """
                SELECT round_date FROM rounds
                WHERE SUBSTR(round_date, 1, 10) = ?
                AND map_name = ?
                LIMIT 1
            """
            result = await self.bot.db_adapter.fetch_one(query, (file_date, map_name))
            if result:
                return file_date

            # Step 2: If file time is early morning (00:00-05:00), check previous date
            hour = int(file_time[:2]) if len(file_time) >= 2 else 99
            if hour < 5:
                prev_date = (
                    datetime.strptime(file_date, '%Y-%m-%d') - timedelta(days=1)
                ).strftime('%Y-%m-%d')

                result = await self.bot.db_adapter.fetch_one(query, (prev_date, map_name))
                if result:
                    logger.info(
                        f"🌙 Midnight crossing: linking {filename} to previous date {prev_date}"
                    )
                    return prev_date

        except Exception as e:
            logger.debug(f"Session date resolution failed for {filename}: {e}")

        return file_date

    async def _import_engagement_file(self, filepath: Path) -> bool:
        """Import a single engagement file"""
        try:
            if self.debug_log:
                logger.info(f"🎯 Importing: {filepath.name}")

            # Extract session date from filename, with midnight-crossing support
            # Format: YYYY-MM-DD-HHMMSS-mapname-round-N_engagements.txt
            filename = filepath.name
            parts = filename.split('-')
            if len(parts) >= 4:
                file_date = f"{parts[0]}-{parts[1]}-{parts[2]}"
                file_time = parts[3]  # HHMMSS
                session_date = await self._resolve_session_date(
                    file_date, file_time, parts, filename
                )
            else:
                session_date = datetime.now().strftime("%Y-%m-%d")

            # Create parser with database adapter
            parser = ProximityParserV4(
                db_adapter=self.bot.db_adapter,
                output_dir=str(filepath.parent),
                gametimes_dir=getattr(self.bot.config, "gametimes_local_path", "local_gametimes"),
            )

            # Import the file
            success = await parser.import_file(str(filepath), session_date)

            if success:
                self._mark_local_processed(filepath.name)
                self.import_count += 1

                # Notify correlation service that proximity data arrived
                await self._notify_correlation(filepath.name)

                stats = parser.get_stats()
                if self.debug_log:
                    logger.info(
                        f"✅ Imported {filepath.name}: "
                        f"{stats['total_engagements']} engagements, "
                        f"{stats['crossfire_engagements']} crossfires"
                    )
                return True
            else:
                self.error_count += 1
                logger.warning(f"⚠️ Failed to import {filepath.name}")
                return False

        except Exception as e:
            self.error_count += 1
            logger.error(f"Error importing {filepath}: {e}", exc_info=True)
            return False
