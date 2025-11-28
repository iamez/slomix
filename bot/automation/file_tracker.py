"""
File Tracker - Deduplication and processing status tracking

Handles:
- Checking if files should be processed (deduplication)
- Tracking processed files in database
- Syncing local files with database records
- Age-based filtering (ignore old files on bot restart)
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional, Set

from bot.automation.ssh_handler import SSHHandler

logger = logging.getLogger("bot.automation.file_tracker")


class FileTracker:
    """Tracks processed stats files to avoid duplicate imports"""

    def __init__(self, db_adapter, config, bot_startup_time: datetime, processed_files: Set[str]):
        """
        Initialize file tracker

        Args:
            db_adapter: Database adapter (PostgreSQL or SQLite)
            config: Bot configuration object
            bot_startup_time: When the bot started (for age filtering)
            processed_files: In-memory set of processed filenames
        """
        self.db_adapter = db_adapter
        self.config = config
        self.bot_startup_time = bot_startup_time
        self.processed_files = processed_files  # Reference to bot's set
        self._process_lock = asyncio.Lock()  # Prevent race conditions

    async def should_process_file(
        self, filename: str, ignore_startup_time: bool = False, check_db_only: bool = False
    ) -> bool:
        """
        Smart file processing decision (Hybrid Approach)

        Checks multiple sources to avoid re-processing:
        1. File age (prevent importing old files) - SKIPPED if ignore_startup_time=True
        2. In-memory cache (fastest)
        3. Local file exists (fast) - SKIPPED if check_db_only=True
        4. Processed files table (fast, persistent)
        5. Sessions table (slower, definitive)

        Args:
            filename: Name of the file to check
            ignore_startup_time: If True, skip the bot startup time check (used by manual sync commands)
            check_db_only: If True, only check database, not local files (used to find files needing import)

        Returns:
            bool: True if file should be processed, False if already done
        """
        async with self._process_lock:  # Prevent race conditions
            return await self._should_process_file_impl(filename, ignore_startup_time, check_db_only)

    async def _should_process_file_impl(
        self, filename: str, ignore_startup_time: bool, check_db_only: bool
    ) -> bool:
        """Internal implementation of should_process_file (called under lock)"""
        try:
            # 1. Check file age - only import files created AFTER bot startup
            # This prevents importing old files on bot restart while allowing live updates
            # SKIP this check if ignore_startup_time=True (manual sync commands)
            if not ignore_startup_time:
                try:
                    # Parse datetime from filename: YYYY-MM-DD-HHMMSS-...
                    datetime_str = filename[:17]  # Get YYYY-MM-DD-HHMMSS
                    file_datetime = datetime.strptime(datetime_str, "%Y-%m-%d-%H%M%S")

                    # Skip files created before bot started
                    if file_datetime < self.bot_startup_time:
                        time_diff = (
                            self.bot_startup_time - file_datetime
                        ).total_seconds() / 3600
                        logger.debug(
                            f"⏭️ {filename} created {time_diff:.1f}h before bot startup (skip old files)"
                        )
                        self.processed_files.add(filename)
                        await self.mark_processed(filename, success=True)
                        return False
                    else:
                        time_diff = (
                            file_datetime - self.bot_startup_time
                        ).total_seconds() / 60
                        logger.debug(
                            f"✅ {filename} created {time_diff:.1f}m after bot startup (process as new file)"
                        )
                except ValueError:
                    # If datetime parsing fails, continue with other checks
                    logger.warning(f"⚠️ Could not parse datetime from filename: {filename}")

            # 2. Check in-memory cache (only if not checking DB only)
            if not check_db_only and filename in self.processed_files:
                return False

            # 3. Check if local file exists (SKIP if check_db_only=True)
            if not check_db_only:
                local_path = os.path.join("local_stats", filename)
                if os.path.exists(local_path):
                    logger.debug(f"⏭️ {filename} exists locally, marking processed")
                    self.processed_files.add(filename)
                    await self.mark_processed(filename, success=True)
                    return False

            # 4. Check processed_files table
            if await self._is_in_processed_files_table(filename):
                logger.debug(f"⏭️ {filename} in processed_files table")
                self.processed_files.add(filename)
                return False

            # 5. Check if session exists in database
            if await self._session_exists_in_db(filename):
                logger.debug(f"⏭️ {filename} session exists in DB")
                self.processed_files.add(filename)
                await self.mark_processed(filename, success=True)
                return False

            # File is truly new!
            return True

        except Exception as e:
            logger.error(f"Error checking if should process {filename}: {e}")
            return False  # Skip on error to be safe

    async def _is_in_processed_files_table(self, filename: str) -> bool:
        """Check if filename exists in processed_files table"""
        try:
            if self.config.database_type == "sqlite":
                query = """SELECT 1 FROM processed_files
                           WHERE filename = ? AND success = 1"""
            else:  # PostgreSQL
                query = """SELECT 1 FROM processed_files
                           WHERE filename = $1 AND success = true"""

            result = await self.db_adapter.fetch_one(query, (filename,))
            return result is not None
        except Exception as e:
            logger.debug(f"Error checking processed_files table: {e}")
            return False

    async def _session_exists_in_db(self, filename: str) -> bool:
        """
        Check if session exists in database by parsing filename

        Filename format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
        """
        try:
            file_info = SSHHandler.parse_gamestats_filename(filename)
            if not file_info:
                return False

            # Use full timestamp for unique identification
            timestamp = "-".join(filename.split("-")[:4])

            if self.config.database_type == "sqlite":
                query = """
                    SELECT 1 FROM rounds
                    WHERE round_date = ?
                      AND map_name = ?
                      AND round_number = ?
                    LIMIT 1
                """
            else:  # PostgreSQL
                query = """
                    SELECT 1 FROM rounds
                    WHERE round_date = $1
                      AND map_name = $2
                      AND round_number = $3
                    LIMIT 1
                """

            result = await self.db_adapter.fetch_one(
                query,
                (
                    timestamp,
                    file_info["map_name"],
                    file_info["round_number"],
                ),
            )

            return result is not None

        except Exception as e:
            logger.debug(f"Error checking session in DB: {e}")
            return False

    async def mark_processed(
        self, filename: str, success: bool = True, error_msg: Optional[str] = None
    ) -> None:
        """
        Mark a file as processed in the processed_files table

        Args:
            filename: Name of the processed file
            success: Whether processing was successful
            error_msg: Error message if processing failed
        """
        try:
            # Database-specific syntax for INSERT OR REPLACE
            if self.config.database_type == "sqlite":
                query = """
                    INSERT OR REPLACE INTO processed_files
                    (filename, success, error_message, processed_at)
                    VALUES (?, ?, ?, ?)
                """
                await self.db_adapter.execute(
                    query,
                    (
                        filename,
                        1 if success else 0,
                        error_msg,
                        datetime.now().isoformat(),
                    ),
                )
            else:  # PostgreSQL
                query = """
                    INSERT INTO processed_files
                    (filename, success, error_message, processed_at)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (filename) DO UPDATE SET
                        success = EXCLUDED.success,
                        error_message = EXCLUDED.error_message,
                        processed_at = EXCLUDED.processed_at
                """
                await self.db_adapter.execute(
                    query,
                    (
                        filename,
                        success,  # PostgreSQL uses boolean directly
                        error_msg,
                        datetime.now(),
                    ),
                )

        except Exception as e:
            logger.debug(f"Error marking file as processed: {e}")

    async def sync_local_files_to_processed_table(self) -> None:
        """
        🔍 DIAGNOSTIC TOOL: Check for unimported files in local_stats/

        This scans local_stats/ and alerts if there are files that haven't been
        imported to the database yet. Does NOT mark them as processed - just reports.

        Files should be imported via:
        - SSH monitor automatic download + import
        - Manual !import command
        - postgresql_database_manager.py bulk import
        """
        try:
            local_dir = "local_stats"
            if not os.path.exists(local_dir):
                return

            files = [f for f in os.listdir(local_dir) if f.endswith(".txt")]

            if not files:
                return

            # Check which files are NOT in processed_files table
            unimported = []
            for filename in files:
                if self.config.database_type == "sqlite":
                    check_query = "SELECT 1 FROM processed_files WHERE filename = ?"
                else:  # PostgreSQL
                    check_query = "SELECT 1 FROM processed_files WHERE filename = $1"

                existing = await self.db_adapter.fetch_one(check_query, (filename,))

                if not existing:
                    unimported.append(filename)

            # Report findings
            if unimported:
                logger.warning(
                    f"⚠️  Found {len(unimported)} unimported files in local_stats/ "
                    f"(total: {len(files)} files)"
                )
                if self.config.database_type == "postgresql":
                    logger.warning(
                        f"💡 To import them, use: python postgresql_database_manager.py "
                        f"or !import command"
                    )
                else:
                    logger.warning(
                        f"💡 To import them, use the !import command"
                    )
                # Show a few examples (don't spam log)
                if len(unimported) <= 5:
                    for f in unimported:
                        logger.info(f"   📄 {f}")
                else:
                    for f in unimported[:3]:
                        logger.info(f"   📄 {f}")
                    logger.info(f"   ... and {len(unimported) - 3} more")
            else:
                logger.info(f"✅ All {len(files)} local files are tracked in database")

        except Exception as e:
            logger.error(f"Error checking local files: {e}")
