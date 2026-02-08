"""
Proximity Tracker Cog
ISOLATED cog for processing engagement data from proximity_tracker.lua

This cog runs its own background task to watch for engagement files
and import them independently of the main stats pipeline.

Features:
- Background task to scan for new engagement files
- Admin commands for status and manual import
- Completely isolated - errors here won't crash main bot
"""

import discord
from discord.ext import commands, tasks
import os
import sys
import logging
import re
from datetime import datetime
from typing import List
from pathlib import Path
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

logger = logging.getLogger(__name__)

# Try to import the proximity parser
try:
    from proximity.parser import ProximityParserV3
    PROXIMITY_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ ProximityParserV3 not available: {e}")
    PROXIMITY_AVAILABLE = False


class ProximityCog(commands.Cog, name="Proximity"):
    """
    Proximity Tracker - Combat engagement analytics

    ISOLATED COG - errors here won't affect main bot functionality

    Admin Commands:
    - !proximity_status - Show tracker status
    - !proximity_import [file] - Manual file import
    - !proximity_scan - Force scan for new files
    """

    def __init__(self, bot):
        self.bot = bot
        self.stats_dir = getattr(bot.config, 'stats_directory', 'local_stats')
        self.local_dir = getattr(bot.config, 'proximity_local_path', self.stats_dir)
        self.remote_path = getattr(bot.config, 'proximity_remote_path', '')
        self.lookback_hours = getattr(
            bot.config, 'proximity_startup_lookback_hours', 24
        )
        self.ssh_enabled = getattr(bot.config, 'ssh_enabled', False)
        self.processed_engagement_files = set()
        self.processed_remote_files = set()
        self.last_scan_time = None
        self.import_count = 0
        self.error_count = 0
        self._startup_scan_completed = False

        # Check if proximity is enabled
        self.enabled = getattr(bot.config, 'proximity_enabled', False)
        self.debug_log = getattr(bot.config, 'proximity_debug_log', False)
        self.commands_enabled = getattr(bot.config, 'proximity_discord_commands', False)

        if not PROXIMITY_AVAILABLE:
            logger.warning("⚠️ Proximity cog loaded but parser not available")
            self.enabled = False

        if self.enabled:
            logger.info("🎯 Proximity Tracker cog initialized (ENABLED)")
            self.scan_engagement_files.start()
        else:
            logger.info("🎯 Proximity Tracker cog initialized (DISABLED)")

        # Ensure local directory exists
        try:
            os.makedirs(self.local_dir, exist_ok=True)
        except Exception as e:
            logger.warning(f"⚠️ Could not create proximity local dir {self.local_dir}: {e}")

        # Load processed remote index (best-effort)
        self._load_remote_index()
        self._load_local_index()

    def _remote_index_path(self) -> str:
        return os.path.join(self.local_dir, ".processed_proximity.txt")

    def _local_index_path(self) -> str:
        return os.path.join(self.local_dir, ".processed_proximity_local.txt")

    def _load_remote_index(self) -> None:
        index_path = self._remote_index_path()
        if not os.path.exists(index_path):
            return
        try:
            with open(index_path, "r", encoding="utf-8") as handle:
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
            with open(index_path, "r", encoding="utf-8") as handle:
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

    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if self.scan_engagement_files.is_running():
            self.scan_engagement_files.cancel()

    async def cog_command_error(self, ctx, error):
        """Handle errors without crashing bot"""
        logger.error(f"Error in ProximityCog: {error}", exc_info=True)
        await ctx.send(
            "⚠️ An error occurred in proximity tracker.\n"
            "Main bot functionality is unaffected."
        )

    # =========================================================================
    # BACKGROUND TASK - Scan for new engagement files
    # =========================================================================

    async def _scan_and_import(self, force: bool = False) -> None:
        if not self.enabled:
            return
        if not force and not self.bot.config.proximity_auto_import:
            return

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

    @tasks.loop(minutes=5)
    async def scan_engagement_files(self):
        """Periodically scan for new engagement files and import them"""
        await self._scan_and_import(force=False)

    @scan_engagement_files.before_loop
    async def before_scan(self):
        """Wait for bot to be ready before starting scan task"""
        await self.bot.wait_until_ready()

    # =========================================================================
    # IMPORT LOGIC
    # =========================================================================

    async def _import_engagement_file(self, filepath: Path) -> bool:
        """Import a single engagement file"""
        try:
            if self.debug_log:
                logger.info(f"🎯 Importing: {filepath.name}")

            # Extract session date from filename
            # Format: YYYY-MM-DD-HHMMSS-mapname-round-N_engagements.txt
            filename = filepath.name
            parts = filename.split('-')
            if len(parts) >= 3:
                session_date = f"{parts[0]}-{parts[1]}-{parts[2]}"
            else:
                session_date = datetime.now().strftime("%Y-%m-%d")

            # Create parser with database adapter
            parser = ProximityParserV3(
                db_adapter=self.bot.db_adapter,
                output_dir=str(filepath.parent)
            )

            # Import the file
            success = await parser.import_file(str(filepath), session_date)

            if success:
                self._mark_local_processed(filepath.name)
                self.import_count += 1

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

    # =========================================================================
    # ADMIN COMMANDS
    # =========================================================================

    @commands.command(name='proximity_status')
    @commands.has_permissions(administrator=True)
    async def proximity_status(self, ctx):
        """Show proximity tracker status (admin only)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("⚠️ Proximity commands are disabled.")
            return

        embed = discord.Embed(
            title="🎯 Proximity Tracker Status",
            color=0x00FF00 if self.enabled else 0xFF0000
        )

        embed.add_field(
            name="Status",
            value="✅ ENABLED" if self.enabled else "❌ DISABLED",
            inline=True
        )

        embed.add_field(
            name="Parser Available",
            value="✅ Yes" if PROXIMITY_AVAILABLE else "❌ No",
            inline=True
        )

        embed.add_field(
            name="Files Imported",
            value=str(self.import_count),
            inline=True
        )

        embed.add_field(
            name="Local Path",
            value=self.local_dir,
            inline=False
        )

        if self.remote_path:
            embed.add_field(
                name="Remote Path",
                value=self.remote_path,
                inline=False
            )

        embed.add_field(
            name="Errors",
            value=str(self.error_count),
            inline=True
        )

        if self.last_scan_time:
            embed.add_field(
                name="Last Scan",
                value=self.last_scan_time.strftime("%H:%M:%S"),
                inline=True
            )

        # Get database stats if enabled
        if self.enabled and PROXIMITY_AVAILABLE:
            try:
                result = await self.bot.db_adapter.fetch_one(
                    "SELECT COUNT(*) FROM combat_engagement"
                )
                engagement_count = result[0] if result else 0

                result = await self.bot.db_adapter.fetch_one(
                    "SELECT COUNT(*) FROM crossfire_pairs"
                )
                pair_count = result[0] if result else 0

                embed.add_field(
                    name="📊 Database",
                    value=f"Engagements: {engagement_count:,}\nCrossfire pairs: {pair_count}",
                    inline=False
                )
            except Exception as e:
                embed.add_field(
                    name="📊 Database",
                    value=f"Error: {e}",
                    inline=False
                )

        embed.set_footer(text="Proximity tracker runs independently of main stats")

        await ctx.send(embed=embed)

    @commands.command(name='proximity_objectives')
    @commands.has_permissions(administrator=True)
    async def proximity_objectives(self, ctx):
        """Show which maps have objective coordinates configured"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("⚠️ Proximity commands are disabled.")
            return

        data = self._load_objective_coords()
        maps = data.get("maps", {})
        if not maps:
            await ctx.send("⚠️ No objective coord data found.")
            return

        configured = []
        missing = []
        for map_name, entries in maps.items():
            has_coords = False
            for entry in entries or []:
                if entry.get("x") is not None and entry.get("y") is not None and entry.get("z") is not None:
                    has_coords = True
                    break
            if has_coords:
                configured.append(map_name)
            else:
                missing.append(map_name)

        configured.sort()
        missing.sort()

        header = f"Objective coords: {len(configured)}/{len(configured) + len(missing)} maps configured"
        parts = [header]
        if configured:
            parts.append("Configured: " + ", ".join(configured))
        if missing:
            parts.append("Missing: " + ", ".join(missing))

        message = "\n".join(parts)
        if len(message) <= 1900:
            await ctx.send(message)
            return

        # Split into multiple messages if too long
        await ctx.send(header)
        if configured:
            await ctx.send("Configured: " + ", ".join(configured))
        if missing:
            await ctx.send("Missing: " + ", ".join(missing))

    @commands.command(name='proximity_scan')
    @commands.has_permissions(administrator=True)
    async def proximity_scan(self, ctx):
        """Force scan for new engagement files (admin only)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("⚠️ Proximity commands are disabled.")
            return

        await ctx.send("🔍 Scanning for engagement files...")

        # Run the scan manually
        await self._scan_and_import(force=True)

        await ctx.send(
            f"✅ Scan complete.\n"
            f"• Files processed this session: {self.import_count}\n"
            f"• Files in memory: {len(self.processed_engagement_files)}"
        )

    @commands.command(name='proximity_import')
    @commands.has_permissions(administrator=True)
    async def proximity_import(self, ctx, filename: str = None):
        """Manually import an engagement file (admin only)"""
        if not self.commands_enabled and not self.enabled:
            await ctx.send("⚠️ Proximity commands are disabled.")
            return

        if not PROXIMITY_AVAILABLE:
            await ctx.send("❌ Proximity parser not available")
            return

        if not filename:
            await ctx.send("Usage: `!proximity_import <filename>`")
            return

        filepath = Path(self.local_dir) / filename
        if not filepath.exists():
            await ctx.send(f"❌ File not found: {filepath}")
            return

        await ctx.send(f"📥 Importing {filename}...")

        success = await self._import_engagement_file(filepath)

        if success:
            await ctx.send(f"✅ Successfully imported {filename}")
        else:
            await ctx.send(f"❌ Failed to import {filename}")


async def setup(bot):
    """Setup function for cog loading"""
    await bot.add_cog(ProximityCog(bot))
