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
from datetime import datetime
from typing import List
from pathlib import Path

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
        self.processed_engagement_files = set()
        self.last_scan_time = None
        self.import_count = 0
        self.error_count = 0

        # Check if proximity is enabled
        self.enabled = getattr(bot.config, 'proximity_enabled', False)
        self.debug_log = getattr(bot.config, 'proximity_debug_log', False)

        if not PROXIMITY_AVAILABLE:
            logger.warning("⚠️ Proximity cog loaded but parser not available")
            self.enabled = False

        if self.enabled:
            logger.info("🎯 Proximity Tracker cog initialized (ENABLED)")
            self.scan_engagement_files.start()
        else:
            logger.info("🎯 Proximity Tracker cog initialized (DISABLED)")

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

    @tasks.loop(minutes=5)
    async def scan_engagement_files(self):
        """Periodically scan for new engagement files and import them"""
        if not self.enabled:
            return

        try:
            self.last_scan_time = datetime.now()

            # Find all engagement files
            stats_path = Path(self.stats_dir)
            if not stats_path.exists():
                if self.debug_log:
                    logger.debug(f"Stats directory not found: {stats_path}")
                return

            engagement_files = list(stats_path.glob("*_engagements.txt"))

            new_files = [
                f for f in engagement_files
                if str(f) not in self.processed_engagement_files
            ]

            if new_files and self.debug_log:
                logger.info(f"🎯 Found {len(new_files)} new engagement files")

            for filepath in new_files:
                await self._import_engagement_file(filepath)

        except Exception as e:
            self.error_count += 1
            logger.error(f"Error in engagement scan: {e}", exc_info=True)

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
                self.processed_engagement_files.add(str(filepath))
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

    @commands.command(name='proximity_scan')
    @commands.has_permissions(administrator=True)
    async def proximity_scan(self, ctx):
        """Force scan for new engagement files (admin only)"""
        if not self.enabled:
            await ctx.send("❌ Proximity tracker is disabled. Set PROXIMITY_ENABLED=true in .env")
            return

        await ctx.send("🔍 Scanning for engagement files...")

        # Run the scan manually
        await self.scan_engagement_files()

        await ctx.send(
            f"✅ Scan complete.\n"
            f"• Files processed this session: {self.import_count}\n"
            f"• Files in memory: {len(self.processed_engagement_files)}"
        )

    @commands.command(name='proximity_import')
    @commands.has_permissions(administrator=True)
    async def proximity_import(self, ctx, filename: str = None):
        """Manually import an engagement file (admin only)"""
        if not PROXIMITY_AVAILABLE:
            await ctx.send("❌ Proximity parser not available")
            return

        if not filename:
            await ctx.send("Usage: `!proximity_import <filename>`")
            return

        filepath = Path(self.stats_dir) / filename
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
