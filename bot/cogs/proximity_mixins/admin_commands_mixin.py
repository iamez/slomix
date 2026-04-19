"""ProximityCog mixin: Admin ops: status, objectives, scan, import.

Extracted from bot/cogs/proximity_cog.py in Mega Audit v4 / Sprint 3.

All methods live on ProximityCog via mixin inheritance.
"""
from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord.ext import commands

try:
    from proximity.parser import ProximityParserV4 as _check_parser  # noqa: F401
    PROXIMITY_AVAILABLE = True
except ImportError:
    PROXIMITY_AVAILABLE = False

logger = logging.getLogger("bot.cogs.proximity")


class _ProximityAdminCommandsMixin:
    """Admin ops: status, objectives, scan, import for ProximityCog."""

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

        # v5 teamplay table counts
        try:
            v5_tables = {
                'proximity_spawn_timing': 'Spawn Timing',
                'proximity_team_cohesion': 'Team Cohesion',
                'proximity_crossfire_opportunity': 'Crossfire Opps',
                'proximity_team_push': 'Team Pushes',
                'proximity_lua_trade_kill': 'Lua Trade Kills',
            }
            v5_parts = []
            for table, label in v5_tables.items():
                count_row = await self.bot.db_adapter.fetch_one(
                    f"SELECT COUNT(*) FROM {table}"
                )
                count = int(count_row[0]) if count_row else 0
                v5_parts.append(f"{label}: {count:,}")
            embed.add_field(
                name="v5 Teamplay Data",
                value="\n".join(v5_parts),
                inline=False
            )
        except Exception as e:
            logger.debug("v5 teamplay data unavailable: %s", e)

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
