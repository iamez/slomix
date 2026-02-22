"""
Admin Cog - Database Administration & Diagnostics
==================================================
Extraction Date: 2025-11-01
Updated: 2025-11-01 - Cleaned to only admin/diagnostic commands

Administrative commands for bot operators.
Other commands moved to specialized cogs.

Commands:
- !reload - Reload bot code without restarting (admin only)
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
# import aiosqlite  # Removed - using database adapter
from discord.ext import commands

from bot.core.checks import is_owner, is_admin, is_moderator
from bot.core.utils import sanitize_error_message

logger = logging.getLogger(__name__)


class AdminCog(commands.Cog, name="Admin"):
    """🔧 Server Administration & Diagnostics"""

    def __init__(self, bot):
        """Initialize the Admin Cog."""
        self.bot = bot
        logger.info("🔧 AdminCog loaded (cache_clear, weapon_diag)")

    @is_admin()
    @commands.command(name="cache_clear")
    async def cache_clear(self, ctx):
        """🗑️ Clear query cache (Admin only - use in admin channel)."""
        try:

            if hasattr(self.bot, 'get_cog'):
                main_cog = self.bot.get_cog('ETLegacyCommands')
                if main_cog and hasattr(main_cog, 'stats_cache'):
                    stats = main_cog.stats_cache.stats()
                    main_cog.stats_cache.clear()
                    await ctx.send(
                        "✅ Query cache cleared!\n"
                        f"**Removed:** {stats['total_keys']} cached entries\n"
                        "💡 Cache will rebuild automatically"
                    )
                    logger.info(f"🗑️ Cache cleared by {ctx.author}")
                else:
                    await ctx.send("❌ Could not access stats cache")
            else:
                await ctx.send("❌ Cache system not available")
        except Exception as e:
            logger.error(f"Error in cache_clear: {e}", exc_info=True)
            await ctx.send(f"❌ Error clearing cache: {sanitize_error_message(e)}")

    @is_owner()
    @commands.command(name="reload")
    async def reload_bot(self, ctx):
        """🔄 Reload the bot (Root only) - Reconnects to Discord with updated code."""
        try:
            await ctx.send("🔄 Reloading bot... This will take a few seconds.")
            logger.info(f"🔄 Bot reload initiated by {ctx.author}")
            
            # Reload all cogs
            reloaded_cogs = []
            failed_cogs = []
            
            for cog_name in list(self.bot.extensions.keys()):
                try:
                    await self.bot.reload_extension(cog_name)
                    reloaded_cogs.append(cog_name.split('.')[-1])
                    logger.info(f"✅ Reloaded: {cog_name}")
                except Exception as e:
                    failed_cogs.append(f"{cog_name.split('.')[-1]}: {str(e)[:50]}")
                    logger.error(f"❌ Failed to reload {cog_name}: {e}")
            
            # Report results
            result_msg = "✅ **Bot Reloaded!**\n\n"
            if reloaded_cogs:
                result_msg += f"**Reloaded ({len(reloaded_cogs)}):** {', '.join(reloaded_cogs)}\n"
            if failed_cogs:
                result_msg += f"\n⚠️ **Failed ({len(failed_cogs)}):**\n" + "\n".join(f"• {cog}" for cog in failed_cogs)
            
            result_msg += "\n\n💡 Bot is now running updated code!"
            await ctx.send(result_msg)
            logger.info("✅ Bot reload complete")
            
        except Exception as e:
            logger.error(f"Error in reload_bot: {e}", exc_info=True)
            await ctx.send(f"❌ Error reloading bot: {sanitize_error_message(e)}")

    @is_moderator()
    @commands.command(name="weapon_diag")
    async def weapon_diag(self, ctx, round_id: Optional[int] = None):
        """🧪 Diagnostic: show weapon stats aggregates for a session."""
        try:
            if round_id is None:
                row = await self.bot.db_adapter.fetch_one("SELECT id FROM rounds ORDER BY id DESC LIMIT 1")
                if not row:
                    await ctx.send("❌ No rounds found in DB.")
                    return
                round_id = row[0]

            agg = await self.bot.db_adapter.fetch_one(
                "SELECT COUNT(*) as rows, SUM(COALESCE(hits,0)) as total_hits, "
                "SUM(COALESCE(shots,0)) as total_shots, SUM(COALESCE(headshots,0)) as total_headshots "
                "FROM weapon_comprehensive_stats WHERE round_id = ?",
                (round_id,)
            )

            msg = f"🔎 **Weapon Diagnostics**\n**Round ID:** {round_id}\n"
            if agg:
                rows, hits, shots, headshots = agg
                msg += f"**Rows:** {rows}\n**Hits:** {hits or 0}\n**Shots:** {shots or 0}\n**Headshots:** {headshots or 0}"
            else:
                msg += "No weapon data available."

            await ctx.send(msg)
        except Exception as e:
            logger.error(f"Error in weapon_diag: {e}", exc_info=True)
            await ctx.send(f"❌ weapon_diag failed: {sanitize_error_message(e)}")


    @is_admin()
    @commands.command(name="correlation_status")
    async def correlation_status(self, ctx):
        """🔗 Show round correlation status (Admin only)."""
        try:
            svc = getattr(self.bot, 'correlation_service', None)
            if not svc:
                await ctx.send("❌ Correlation service not initialized.")
                return

            summary = await svc.get_status_summary()
            counts = summary.get('counts', {})
            total = summary.get('total', 0)
            dry_run = summary.get('dry_run', True)

            mode = "DRY-RUN (logging only)" if dry_run else "LIVE"
            msg = f"🔗 **Round Correlation Status** ({mode})\n\n"

            if total == 0:
                msg += "No correlations tracked yet.\n"
            else:
                msg += f"**Total:** {total}\n"
                for status, cnt in sorted(counts.items()):
                    emoji = {'complete': '✅', 'partial': '🔶', 'pending': '⏳'}.get(status, '❓')
                    msg += f"{emoji} **{status}:** {cnt}\n"

            recent = summary.get('recent', [])
            if recent:
                msg += "\n**Recent (last 10):**\n```\n"
                for row in recent:
                    cid = row[0] if row[0] else '?'
                    status = row[3] if row[3] else '?'
                    pct = row[4] if row[4] else 0
                    msg += f"{cid}: {status} ({pct}%)\n"
                msg += "```"

            await ctx.send(msg)
        except Exception as e:
            logger.error(f"Error in correlation_status: {e}", exc_info=True)
            await ctx.send(f"❌ correlation_status failed: {sanitize_error_message(e)}")


async def setup(bot):
    """Load the Admin Cog."""
    await bot.add_cog(AdminCog(bot))
