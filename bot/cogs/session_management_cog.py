"""
🎬 Session Management Cog - Session Control Commands
Handles manual session start/stop and monitoring control.

Commands:
- session_start: Start a new gaming session
- session_end: Stop SSH monitoring

Note: These are different from session *viewing* commands (in Session Cog).
These commands control the active session and monitoring state.
"""

import logging
from datetime import datetime

import discord
from discord.ext import commands

from bot.core.checks import is_admin
from bot.core.utils import sanitize_error_message

logger = logging.getLogger("UltimateBot.SessionManagementCog")


class SessionManagementCog(commands.Cog, name="Session Management"):
    """🎬 Session control commands"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("🎬 SessionManagementCog initializing...")

    @is_admin()
    @commands.command(name="session_start")
    async def session_start(self, ctx, *, map_name: str = "Unknown"):
        """🎬 Start a new gaming session
        
        Usage: !session_start [map_name]
        
        This manually starts a gaming session and creates a database entry.
        Normally sessions are auto-detected via voice channel monitoring.
        """
        try:
            if self.bot.current_session:
                await ctx.send(
                    "❌ A session is already active. End it first with `!session_end`"
                )
                return

            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M:%S")

            round_row = await self.bot.db_adapter.fetch_one(
                """
                INSERT INTO rounds (round_time, round_date, map_name, round_status)
                VALUES (?, ?, ?, 'active')
                RETURNING id
                """,
                (time_str, date_str, map_name),
            )
            if not round_row:
                raise RuntimeError("Failed to create session round entry")

            round_id = round_row[0]
            self.bot.current_session = round_id

            # Enable monitoring
            self.bot.monitoring = True

            embed = discord.Embed(
                title="🎬 Session Started!",
                description=(
                    f"Round ID: **{round_id}**\n"
                    f"Map: **{map_name}**\n"
                    f"Date: **{date_str}**\n\n"
                    "✅ Monitoring enabled - stats will be tracked automatically."
                ),
                color=0x00FF00,
                timestamp=datetime.now(),
            )

            await ctx.send(embed=embed)
            logger.info(f"✅ Session started manually: ID {round_id}, map {map_name}")

        except Exception as e:
            logger.error(f"Error in session_start: {e}", exc_info=True)
            try:
                await ctx.send(
                    f"❌ Error starting session: {sanitize_error_message(e)}")
            except Exception:  # nosec B110
                pass  # Discord send failed, already logged above

    @is_admin()
    @commands.command(name="session_end")
    async def session_end(self, ctx):
        """🏁 Stop SSH monitoring
        
        Usage: !session_end
        
        This stops automatic stats monitoring and SSH file checking.
        Does not delete the current session, just disables monitoring.
        """
        try:
            if not self.bot.monitoring:
                await ctx.send("❌ Monitoring is not currently active.")
                return

            # Disable monitoring flag
            self.bot.monitoring = False

            embed = discord.Embed(
                title="🏁 Monitoring Stopped",
                description=(
                    "SSH monitoring has been disabled.\n\n"
                    "Use `!session_start` to re-enable automatic monitoring."
                ),
                color=0xFF0000,
                timestamp=datetime.now(),
            )

            await ctx.send(embed=embed)
            logger.info("✅ Monitoring manually stopped via !session_end")

        except Exception as e:
            logger.error(f"Error ending session: {e}", exc_info=True)
            await ctx.send(f"❌ Error ending session: {sanitize_error_message(e)}")


async def setup(bot):
    """Load the Session Management Cog"""
    await bot.add_cog(SessionManagementCog(bot))
