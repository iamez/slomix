"""
Admin Cog - Database Administration & Diagnostics
==================================================
Extraction Date: 2025-11-01
Updated: 2025-11-01 - Cleaned to only admin/diagnostic commands

Administrative commands for bot operators.
Other commands moved to specialized cogs.

Commands:
- !cache_clear - Clear query cache (admin only)
- !weapon_diag - Diagnostic weapon stats viewer

NOTE: Other commands moved to specialized cogs:
- Session Management Cog: session_start, session_end
- Sync Cog: sync_stats, sync_today, sync_week, sync_month, sync_all
- Team Management Cog: set_teams, assign_player
"""

import logging
from typing import Optional

import discord
import aiosqlite
from discord.ext import commands

logger = logging.getLogger(__name__)


class AdminCog(commands.Cog, name="Admin"):
    """🔧 Server Administration & Diagnostics"""

    def __init__(self, bot):
        """Initialize the Admin Cog."""
        self.bot = bot
        logger.info("🔧 AdminCog loaded (cache_clear, weapon_diag)")

    @commands.command(name="cache_clear")
    async def cache_clear(self, ctx):
        """🗑️ Clear query cache (Admin only)."""
        try:
            if not ctx.author.guild_permissions.manage_guild:
                await ctx.send("❌ You don't have permission to clear cache. **Required:** Manage Server")
                return

            if hasattr(self.bot, 'get_cog'):
                main_cog = self.bot.get_cog('ETLegacyCommands')
                if main_cog and hasattr(main_cog, 'stats_cache'):
                    stats = main_cog.stats_cache.stats()
                    main_cog.stats_cache.clear()
                    await ctx.send(
                        f"✅ Query cache cleared!\n"
                        f"**Removed:** {stats['total_keys']} cached entries\n"
                        f"💡 Cache will rebuild automatically"
                    )
                    logger.info(f"🗑️ Cache cleared by {ctx.author}")
                else:
                    await ctx.send("❌ Could not access stats cache")
            else:
                await ctx.send("❌ Cache system not available")
        except Exception as e:
            logger.error(f"Error in cache_clear: {e}", exc_info=True)
            await ctx.send(f"❌ Error clearing cache: {e}")

    @commands.command(name="weapon_diag")
    async def weapon_diag(self, ctx, session_id: Optional[int] = None):
        """🧪 Diagnostic: show weapon stats aggregates for a session."""
        try:
            async with aiosqlite.connect(self.bot.db_path) as db:
                if session_id is None:
                    async with db.execute("SELECT id FROM sessions ORDER BY id DESC LIMIT 1") as cur:
                        row = await cur.fetchone()
                        if not row:
                            await ctx.send("❌ No sessions found in DB.")
                            return
                        session_id = row[0]

                async with db.execute(
                    "SELECT COUNT(*) as rows, SUM(COALESCE(hits,0)) as total_hits, "
                    "SUM(COALESCE(shots,0)) as total_shots, SUM(COALESCE(headshots,0)) as total_headshots "
                    "FROM weapon_comprehensive_stats WHERE session_id = ?",
                    (session_id,),
                ) as cur:
                    agg = await cur.fetchone()

                msg = f"🔎 **Weapon Diagnostics**\n**Session ID:** {session_id}\n"
                if agg:
                    rows, hits, shots, headshots = agg
                    msg += f"**Rows:** {rows}\n**Hits:** {hits or 0}\n**Shots:** {shots or 0}\n**Headshots:** {headshots or 0}"
                else:
                    msg += "No weapon data available."

                await ctx.send(msg)
        except Exception as e:
            logger.error(f"Error in weapon_diag: {e}", exc_info=True)
            await ctx.send(f"❌ weapon_diag failed: {e}")


async def setup(bot):
    """Load the Admin Cog."""
    await bot.add_cog(AdminCog(bot))
