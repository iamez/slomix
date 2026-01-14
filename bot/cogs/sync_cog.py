"""
🔄 Sync Cog - Stats Synchronization Commands
Handles manual stats file synchronization from remote server.

Commands:
- sync_stats: Manual sync with time period filtering
- sync_today: Quick sync for last 24 hours
- sync_week: Quick sync for last 7 days
- sync_month: Quick sync for last 30 days
- sync_all: Sync all unprocessed files

This cog requires SSH to be enabled in the bot configuration.
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from bot.core.checks import is_admin
from bot.core.utils import sanitize_error_message

logger = logging.getLogger("UltimateBot.SyncCog")


class SyncCog(commands.Cog, name="Sync Commands"):
    """🔄 Stats synchronization commands"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("🔄 SyncCog initializing...")

    def parse_time_period(self, period_str: str | None):
        """Parse a human-friendly period string into days.

        Returns:
            int days or None for 'all' (no limit)
        Examples accepted: '1day', '2weeks', '1month', '30', 'all'
        """
        if not period_str:
            return 14

        s = period_str.strip().lower()
        if s in ("all", "any", "everything"):
            return None

        # Full-word matches
        m = re.match(r"^(\d+)\s*(day|days|d)$", s)
        if m:
            return int(m.group(1))

        m = re.match(r"^(\d+)\s*(week|weeks|w)$", s)
        if m:
            return int(m.group(1)) * 7

        m = re.match(r"^(\d+)\s*(month|months|m)$", s)
        if m:
            return int(m.group(1)) * 30

        m = re.match(r"^(\d+)\s*(year|years|y)$", s)
        if m:
            return int(m.group(1)) * 365

        # Short shorthand like '1d', '2w', '3m', '1y'
        m = re.match(r"^(\d+)([dwmy])$", s)
        if m:
            n = int(m.group(1))
            u = m.group(2)
            return n if u == "d" else n * 7 if u == "w" else n * 30 if u == "m" else n * 365

        # Numeric-only -> days
        if s.isdigit():
            return int(s)

        # Unknown -> default None (caller may treat as all)
        return None

    def _should_include_file(self, filename: str, days_back: int | None):
        """Return True if the filename falls within days_back (None = include all)."""
        if days_back is None:
            return True
        try:
            parts = filename.split("-")
            if len(parts) < 3:
                return True
            date_str = "-".join(parts[:3])
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            cutoff_date = datetime.now() - timedelta(days=days_back)
            return file_date >= cutoff_date
        except Exception:
            return True

    @is_admin()
    @commands.command(name="sync_stats", aliases=["syncstats", "sync_logs"])
    async def sync_stats(self, ctx, period: str = None):
        """🔄 Manually sync and process stats files from server

        Usage: !sync_stats [period]  (period examples: 1day, 2weeks, 1month, all)
        """
        try:
            if not self.bot.ssh_enabled:
                await ctx.send(
                    "❌ SSH monitoring is not enabled. "
                    "Set `SSH_ENABLED=true` in .env file."
                )
                return

            # Parse time period (default 2 weeks)
            days_back = self.parse_time_period(period) if period else 14

            # Friendly period display
            if days_back:
                period_display = f"last {days_back} days"
                if days_back == 1:
                    period_display = "last 24 hours"
                elif days_back == 7:
                    period_display = "last week"
                elif days_back == 14:
                    period_display = "last 2 weeks"
                elif days_back == 30:
                    period_display = "last month"
                elif days_back == 365:
                    period_display = "last year"
            else:
                period_display = "all time (no filter)"

            # Send initial message
            status_msg = await ctx.send(
                f"🔄 Checking remote server for new stats files...\n📅 Time period: **{period_display}**"
            )

            # Build SSH config
            ssh_config = {
                "host": os.getenv("SSH_HOST"),
                "port": int(os.getenv("SSH_PORT", 22)),
                "user": os.getenv("SSH_USER"),
                "key_path": os.getenv("SSH_KEY_PATH", ""),
                "remote_path": os.getenv("REMOTE_STATS_PATH"),
            }

            # List remote files
            remote_files = await self.bot.ssh_list_remote_files(ssh_config)

            if not remote_files:
                await status_msg.edit(
                    content="❌ Could not connect to server or no files found."
                )
                return

            # Filter files by time period if requested
            if days_back:
                filtered = [f for f in remote_files if self._should_include_file(f, days_back)]
                excluded_count = len(remote_files) - len(filtered)
                remote_files = filtered
                if excluded_count > 0:
                    await status_msg.edit(
                        content=(
                            f"🔄 Checking remote server...\n📅 Time period: **{period_display}**\n"
                            f"📊 Found **{len(remote_files)}** files in period ({excluded_count} older files excluded)"
                        )
                    )

            # Check which files need processing
            # Use ignore_startup_time=True to allow historical files
            # Use check_db_only=True to check ONLY database, not local files
            # This allows re-importing local files that were wiped from DB
            files_to_process = []
            for filename in remote_files:
                if await self.bot.file_tracker.should_process_file(filename, ignore_startup_time=True, check_db_only=True):
                    files_to_process.append(filename)

            if not files_to_process:
                await status_msg.edit(
                    content="✅ All files are already processed! Nothing new to sync."
                )
                return

            # Sort files: Round 1 before Round 2, chronologically
            # Format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
            def sort_key(filename):
                parts = filename.split("-")
                if len(parts) >= 7:
                    date = "-".join(parts[:3])  # YYYY-MM-DD
                    time = parts[3]  # HHMMSS
                    round_num = parts[-1].replace(".txt", "")  # N from round-N
                    return (
                        date,
                        time,
                        round_num,
                    )  # Sort by date, time, then round
                return (filename, "", "99")  # Fallback

            files_to_process.sort(key=sort_key)

            # Phase 1: Download ALL files first
            await status_msg.edit(
                content=f"📥 Downloading {len(files_to_process)} file(s)..."
            )

            downloaded_files = []
            download_failed = 0

            for i, filename in enumerate(files_to_process):
                try:
                    # Download file
                    local_path = await self.bot.ssh_download_file(
                        ssh_config, filename, "local_stats"
                    )

                    if local_path:
                        downloaded_files.append((filename, local_path))

                        # Update progress every 50 files
                        if (i + 1) % 50 == 0:
                            await status_msg.edit(
                                content=f"📥 Downloading... {i + 1}/{len(files_to_process)}"
                            )
                    else:
                        download_failed += 1
                        logger.warning(f"Failed to download {filename}")

                except Exception as e:
                    logger.error(f"Download error for {filename}: {e}")
                    download_failed += 1

            # Phase 2: Verify downloads
            await status_msg.edit(
                content=f"🔍 Verifying downloads... {len(downloaded_files)} files"
            )

            local_files = set(os.listdir("local_stats"))
            verified_files = []

            for filename, local_path in downloaded_files:
                if os.path.basename(local_path) in local_files:
                    verified_files.append((filename, local_path))
                else:
                    logger.error(f"Downloaded file missing: {filename}")
                    download_failed += 1

            logger.info(
                f"✅ Downloaded {len(verified_files)} files, "
                f"{download_failed} failed"
            )

            if not verified_files:
                await status_msg.edit(
                    content="❌ No files were successfully downloaded."
                )
                return

            # Phase 3: Process/parse files for database import
            await status_msg.edit(
                content=f"⚙️ Processing {len(verified_files)} file(s) for database import..."
            )

            processed = 0
            process_failed = 0

            for i, (filename, local_path) in enumerate(verified_files):
                try:
                    # Process the file (parse + import)
                    result = await self.bot.process_gamestats_file(
                        local_path, filename
                    )

                    if result.get("success"):
                        processed += 1
                    else:
                        process_failed += 1
                        logger.error(
                            f"Processing failed for {filename}: {result.get('error')}"
                        )

                    # Update progress every 50 files
                    if (i + 1) % 50 == 0:
                        await status_msg.edit(
                            content=f"⚙️ Processing... {i + 1}/{len(verified_files)}"
                        )

                except Exception as e:
                    logger.error(f"Failed to process {filename}: {e}")
                    process_failed += 1

            # Final status
            embed = discord.Embed(
                title="✅ Stats Sync Complete!",
                color=0x00FF00,
                timestamp=datetime.now(),
            )
            embed.add_field(
                name="📥 Download Phase",
                value=(
                    f"✅ Downloaded: **{len(verified_files)}** file(s)\n"
                    f"❌ Failed: **{download_failed}** file(s)"
                ),
                inline=False,
            )
            embed.add_field(
                name="⚙️ Processing Phase",
                value=(
                    f"✅ Processed: **{processed}** file(s)\n"
                    f"❌ Failed: **{process_failed}** file(s)"
                ),
                inline=False,
            )

            if processed > 0:
                embed.add_field(
                    name="💡 What's Next?",
                    value=(
                        "Round summaries have been posted above!\n"
                        "Use `!last_session` to see full session details."
                    ),
                    inline=False,
                )

            await status_msg.edit(content=None, embed=embed)
            logger.info(
                f"✅ Manual sync complete: {len(verified_files)} downloaded, "
                f"{processed} processed, {process_failed} failed"
            )

        except Exception as e:
            logger.error(f"Error in sync_stats: {e}")
            await ctx.send(f"❌ Sync error: {sanitize_error_message(e)}")

    @is_admin()
    @commands.command(name="sync_today", aliases=["sync1day"])
    async def sync_today(self, ctx):
        """🔄 Quick sync: Today's matches only (last 24 hours)"""
        await self.sync_stats(ctx, period="1day")

    @is_admin()
    @commands.command(name="sync_week", aliases=["sync1week"])
    async def sync_week(self, ctx):
        """🔄 Quick sync: This week's matches (last 7 days)"""
        await self.sync_stats(ctx, period="1week")

    @is_admin()
    @commands.command(name="sync_month", aliases=["sync1month"])
    async def sync_month(self, ctx):
        """🔄 Quick sync: This month's matches (last 30 days)"""
        await self.sync_stats(ctx, period="1month")

    @is_admin()
    @commands.command(name="sync_all")
    async def sync_all(self, ctx):
        """🔄 Quick sync: ALL unprocessed files (no time filter)"""
        await self.sync_stats(ctx, period="all")

    @is_admin()
    @commands.command(name="sync_historical", aliases=["sync_missing", "backfill"])
    async def sync_historical(self, ctx, days: int = None):
        """📥 Download missing files from game server to local_stats/

        Compares game server files with local_stats/ directory and downloads
        any missing files. Does NOT import to database - just ensures local_stats/
        is a complete mirror of the game server.

        Usage:
            !sync_historical        - Check all files (complete mirror)
            !sync_historical 90     - Check last 90 days only
            !sync_historical 365    - Check last year

        Use this after bot downtime to recover missing historical files.
        """
        try:
            if not self.bot.ssh_enabled:
                await ctx.send(
                    "❌ SSH monitoring is not enabled. "
                    "Set `SSH_ENABLED=true` in .env file."
                )
                return

            # Build SSH config
            ssh_config = {
                "host": os.getenv("SSH_HOST"),
                "port": int(os.getenv("SSH_PORT", 22)),
                "user": os.getenv("SSH_USER"),
                "key_path": os.getenv("SSH_KEY_PATH", ""),
                "remote_path": os.getenv("REMOTE_STATS_PATH"),
            }

            # Send initial message
            period_display = f"last {days} days" if days else "all time"
            status_msg = await ctx.send(
                f"🔍 Checking game server for missing files...\n📅 Time period: **{period_display}**"
            )

            # List remote files
            logger.info("📋 Listing remote files from game server...")
            remote_files = await self.bot.ssh_list_remote_files(ssh_config)

            if not remote_files:
                await status_msg.edit(
                    content="❌ Could not connect to game server or no files found."
                )
                return

            # Filter by time period if requested
            if days:
                filtered = [f for f in remote_files if self._should_include_file(f, days)]
                excluded_count = len(remote_files) - len(filtered)
                remote_files = filtered
                if excluded_count > 0:
                    await status_msg.edit(
                        content=(
                            f"🔍 Checking game server...\n📅 Time period: **{period_display}**\n"
                            f"📊 Found **{len(remote_files)}** files in period ({excluded_count} older files excluded)"
                        )
                    )

            # Check which files are missing from local_stats/
            local_dir = "local_stats"
            os.makedirs(local_dir, exist_ok=True)
            local_files = set(os.listdir(local_dir))

            missing_files = [f for f in remote_files if f not in local_files]

            if not missing_files:
                await status_msg.edit(
                    content=(
                        f"✅ **local_stats/ is complete!**\n\n"
                        f"📊 Remote files: {len(remote_files)}\n"
                        f"📁 Local files: {len(local_files)}\n"
                        f"📥 Missing: 0\n\n"
                        f"💡 Your local_stats/ directory is a complete mirror of the game server."
                    )
                )
                return

            # Sort files chronologically
            def sort_key(filename):
                parts = filename.split("-")
                if len(parts) >= 7:
                    date = "-".join(parts[:3])  # YYYY-MM-DD
                    time = parts[3]  # HHMMSS
                    round_num = parts[-1].replace(".txt", "")  # N from round-N
                    return (date, time, round_num)
                return (filename, "", "99")

            missing_files.sort(key=sort_key)

            # Show summary before downloading
            earliest_missing = missing_files[0] if missing_files else "N/A"
            latest_missing = missing_files[-1] if missing_files else "N/A"

            await status_msg.edit(
                content=(
                    f"📥 **Found {len(missing_files)} missing files**\n\n"
                    f"📊 Remote files: {len(remote_files)}\n"
                    f"📁 Local files: {len(local_files)}\n"
                    f"📥 Missing: {len(missing_files)}\n\n"
                    f"📅 Earliest: `{earliest_missing[:17]}`\n"
                    f"📅 Latest: `{latest_missing[:17]}`\n\n"
                    f"⏳ Downloading missing files..."
                )
            )

            # Download missing files
            downloaded = 0
            failed = 0

            for i, filename in enumerate(missing_files):
                try:
                    local_path = await self.bot.ssh_download_file(
                        ssh_config, filename, local_dir
                    )

                    if local_path:
                        downloaded += 1
                    else:
                        failed += 1
                        logger.warning(f"Failed to download {filename}")

                    # Update progress every 50 files
                    if (i + 1) % 50 == 0 or (i + 1) == len(missing_files):
                        await status_msg.edit(
                            content=f"📥 Downloading... {i + 1}/{len(missing_files)}"
                        )

                except Exception as e:
                    logger.error(f"Download error for {filename}: {e}")
                    failed += 1

            # Final report
            embed = discord.Embed(
                title="✅ Historical Sync Complete!",
                color=0x00FF00 if failed == 0 else 0xFFA500,
                timestamp=datetime.now(),
            )
            embed.add_field(
                name="📊 Summary",
                value=(
                    f"📥 Downloaded: **{downloaded}** files\n"
                    f"❌ Failed: **{failed}** files\n"
                    f"📁 Total local files: **{len(local_files) + downloaded}**"
                ),
                inline=False,
            )
            embed.add_field(
                name="💡 What's Next?",
                value=(
                    "Files are now in `local_stats/` directory.\n"
                    "Use `postgresql_database_manager.py` to import them to the database,\n"
                    "or use `!sync_all` to process unimported files."
                ),
                inline=False,
            )

            if downloaded > 0:
                embed.add_field(
                    name="🔍 File Range",
                    value=(
                        f"📅 Earliest: `{earliest_missing[:17]}`\n"
                        f"📅 Latest: `{latest_missing[:17]}`"
                    ),
                    inline=False,
                )

            await status_msg.edit(content=None, embed=embed)
            logger.info(
                f"✅ Historical sync complete: {downloaded} downloaded, {failed} failed"
            )

        except Exception as e:
            logger.error(f"Error in sync_historical: {e}", exc_info=True)
            await ctx.send(f"❌ Sync error: {sanitize_error_message(e)}")


async def setup(bot):
    """Load the Sync Cog"""
    await bot.add_cog(SyncCog(bot))
