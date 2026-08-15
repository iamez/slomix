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

import aiohttp

# import aiosqlite  # Removed - using database adapter
from discord.ext import commands

from bot.core.checks import is_admin, is_moderator, is_owner
from bot.core.utils import sanitize_error_message

logger = logging.getLogger(__name__)

# The system overview is a handful of small queries plus one UDP probe; if it
# has not answered by then, "the website API is not answering" IS the status.
_SYSTEM_HTTP_TIMEOUT_S = 10

_SYSTEM_STATE_EMOJI = {
    "ok": "🟢",
    "idle": "⚪",
    "warn": "🟠",
    "down": "🔴",
    "unknown": "❔",
}


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
    async def weapon_diag(self, ctx, round_id: int | None = None):
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
            live_requested = summary.get('live_requested', not dry_run)
            guardrail_reason = summary.get('guardrail_reason')
            preflight_checked = summary.get('preflight_checked', False)
            preflight_ok = summary.get('preflight_ok', False)
            write_error_count = summary.get('write_error_count', 0)
            write_error_threshold = summary.get('write_error_threshold', 0)

            mode = "DRY-RUN (logging only)" if dry_run else "LIVE"
            msg = f"🔗 **Round Correlation Status** ({mode})\n\n"
            requested_mode = "LIVE" if live_requested else "DRY-RUN"
            msg += f"**Requested mode:** {requested_mode}\n"
            if preflight_checked:
                msg += f"**Schema preflight:** {'ok' if preflight_ok else 'failed'}\n"
            if guardrail_reason:
                msg += f"⚠️ **Guardrail:** `{guardrail_reason}`\n"
            msg += f"**Write errors:** {write_error_count}/{write_error_threshold}\n\n"

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
                    if len(row) < 5:
                        continue  # defensive: unexpected row shape shouldn't crash the command
                    cid = row[0] if row[0] else '?'
                    status = row[3] if row[3] else '?'
                    pct = row[4] if row[4] else 0
                    msg += f"{cid}: {status} ({pct}%)\n"
                msg += "```"

            await ctx.send(msg)
        except Exception as e:
            logger.error(f"Error in correlation_status: {e}", exc_info=True)
            await ctx.send(f"❌ correlation_status failed: {sanitize_error_message(e)}")


    @is_moderator()
    # Every invocation opens an outbound HTTP call that itself runs a UDP probe
    # and several queries, so it is rate-limited per channel on top of the
    # access check — a status command must never become a load generator.
    @commands.cooldown(1, 30, commands.BucketType.channel)
    @commands.command(name="sistem", aliases=["system"])
    async def system_status(self, ctx):
        """🩺 Ali cela veriga teče? (isti vir kot stran #/system)"""
        url = f"{self.bot.config.website_api_base}/system/overview"
        try:
            timeout = aiohttp.ClientTimeout(total=_SYSTEM_HTTP_TIMEOUT_S)
            async with aiohttp.ClientSession(timeout=timeout) as http, http.get(url) as resp:
                if resp.status != 200:
                    await ctx.send(f"🔴 **Sistem:** spletni API je odgovoril s HTTP {resp.status}.")
                    return
                data = await resp.json()
        except Exception as e:
            # The command's whole job is to report state, so an unreachable API
            # is an answer, not an error to swallow.
            logger.info("sistem: overview unreachable (%s)", e)
            await ctx.send("🔴 **Sistem:** spletni API se ne odziva — to je hkrati odgovor.")
            return

        try:
            await ctx.send(self._format_system_overview(data))
        except Exception as e:
            # A malformed payload is a status finding too, not a stack trace.
            logger.warning("sistem: could not format overview (%s)", e)
            await ctx.send("🟠 **Sistem:** odgovor ni v pričakovani obliki.")

    @staticmethod
    def _format_system_overview(data) -> str:
        """Render the overview payload; tolerant of anything the API sends."""
        if not isinstance(data, dict):
            raise TypeError(f"overview payload is {type(data).__name__}, not a dict")
        overall = str(data.get("overall", "unknown"))
        lines = [f"{_SYSTEM_STATE_EMOJI.get(overall, '❔')} **Sistem — {overall.upper()}**"]

        for stage in data.get("stages") or []:
            if not isinstance(stage, dict):
                continue
            emoji = _SYSTEM_STATE_EMOJI.get(stage.get("state"), "❔")
            lines.append(f"{emoji} **{stage.get('label', stage.get('key'))}** — {stage.get('summary', '')}")

        linkage = data.get("linkage") or {}
        if linkage.get("available"):
            breaches = linkage.get("breaches") or []
            if breaches:
                detail = ", ".join(
                    f"{b.get('metric')} {b.get('value')} (meja {b.get('threshold')})" for b in breaches
                )
                lines.append(f"🟠 **Integriteta:** {detail}")
            else:
                lines.append("🟢 **Integriteta:** nobena meja ni presežena")

        generated = data.get("generated_at")
        if generated:
            lines.append(f"_preverjeno {str(generated).replace('T', ' ')[:19]} UTC_")

        return "\n".join(lines)


async def setup(bot):
    """Load the Admin Cog."""
    await bot.add_cog(AdminCog(bot))
