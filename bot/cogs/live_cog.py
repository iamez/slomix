"""
Live Match Cog - Real-time match updates

This cog handles:
- !live - Show current match status
- Real-time updates during active gaming sessions

Provides live stats and match information while games are in progress.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class LiveCog(commands.Cog, name="Live"):
    """Real-time match updates and current session stats"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("📡 LiveCog initializing...")

    @commands.command(name="live", aliases=["current", "now", "active"])
    async def live(self, ctx):
        """📡 Show current match status and live stats

        Displays real-time information about the current gaming session,
        including who's playing, recent performance, and session stats.
        """
        try:
            # Check if there's an active session
            if not self.bot.session_active:
                await ctx.send(
                    "❌ No active gaming session right now.\n"
                    "💡 Sessions start automatically when 6+ players join voice channels!"
                )
                return

            # Get session info
            duration = discord.utils.utcnow() - self.bot.session_start_time if self.bot.session_start_time else timedelta(0)

            # Get current voice channel members
            current_players = []
            total_in_voice = 0
            for channel_id in self.bot.gaming_voice_channels:
                channel = self.bot.get_channel(channel_id)
                if channel and isinstance(channel, discord.VoiceChannel):
                    total_in_voice += len(channel.members)
                    for member in channel.members:
                        current_players.append({
                            'name': member.display_name,
                            'id': member.id
                        })

            # Get recent stats from the current session
            session_stats = await self._get_current_session_stats()

            # Build embed
            embed = discord.Embed(
                title="📡 Live Match Status",
                description=f"Gaming session in progress!",
                color=0x00FF00  # Green
            )

            # Session info
            embed.add_field(
                name="⏱️ Session Duration",
                value=self._format_duration(duration),
                inline=True
            )

            embed.add_field(
                name="👥 Players in Voice",
                value=f"{total_in_voice} player{'' if total_in_voice == 1 else 's'}",
                inline=True
            )

            if session_stats:
                embed.add_field(
                    name="🎮 Rounds Played",
                    value=f"{session_stats['rounds_played']} round{'' if session_stats['rounds_played'] == 1 else 's'}",
                    inline=True
                )

                # Top performers this session
                if session_stats.get('top_players'):
                    top_text = []
                    for i, player in enumerate(session_stats['top_players'][:5], 1):
                        kd = player['kills'] / player['deaths'] if player['deaths'] > 0 else player['kills']
                        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                        top_text.append(
                            f"{medal} **{player['name']}** • {player['kills']}K/{player['deaths']}D ({kd:.2f})"
                        )

                    embed.add_field(
                        name="🌟 Session Leaders",
                        value="\n".join(top_text),
                        inline=False
                    )

                # Recent activity
                if session_stats.get('recent_map'):
                    embed.add_field(
                        name="🗺️ Current/Last Map",
                        value=session_stats['recent_map'],
                        inline=True
                    )

                # Session totals
                if session_stats.get('total_kills'):
                    totals = [
                        f"💀 **{session_stats['total_kills']:,}** total kills",
                        f"🎯 **{session_stats['total_headshots']:,}** headshots",
                        f"⚕️ **{session_stats['total_revives']:,}** revives"
                    ]
                    embed.add_field(
                        name="📊 Session Totals",
                        value="\n".join(totals),
                        inline=False
                    )

            # Who's online
            if current_players:
                online_names = [p['name'] for p in current_players[:10]]
                if len(online_names) > 10:
                    online_text = ", ".join(online_names[:10]) + f" +{len(online_names)-10} more"
                else:
                    online_text = ", ".join(online_names)

                embed.add_field(
                    name="🎙️ Currently in Voice",
                    value=online_text,
                    inline=False
                )

            embed.set_footer(text="🔴 Live • Updates in real-time")
            embed.timestamp = datetime.utcnow()

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in live command: {e}", exc_info=True)
            await ctx.send(f"❌ Error getting live status: {e}")

    async def _get_current_session_stats(self) -> Optional[Dict]:
        """Get stats for the current gaming session"""
        try:
            if not self.bot.current_session:
                return None

            # Get session stats
            query = """
                SELECT
                    COUNT(DISTINCT r.id) as rounds_played,
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths,
                    SUM(p.headshot_kills) as total_headshots,
                    SUM(p.revives) as total_revives
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE r.session_id = ?
                    AND r.round_number IN (1, 2)
            """

            stats = await self.bot.db_adapter.fetch_one(query, (self.bot.current_session,))

            if not stats or stats[0] == 0:
                return None

            # Get top players
            top_players_query = """
                SELECT
                    p.player_name,
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE r.session_id = ?
                    AND r.round_number IN (1, 2)
                GROUP BY p.player_name
                ORDER BY total_kills DESC
                LIMIT 5
            """

            top_players = await self.bot.db_adapter.fetch_all(top_players_query, (self.bot.current_session,))

            # Get most recent map
            recent_map_query = """
                SELECT r.map_name
                FROM rounds r
                WHERE r.session_id = ?
                ORDER BY r.round_date DESC
                LIMIT 1
            """

            recent_map = await self.bot.db_adapter.fetch_one(recent_map_query, (self.bot.current_session,))

            return {
                'rounds_played': stats[0],
                'total_kills': stats[1] or 0,
                'total_deaths': stats[2] or 0,
                'total_headshots': stats[3] or 0,
                'total_revives': stats[4] or 0,
                'top_players': [
                    {'name': row[0], 'kills': row[1], 'deaths': row[2]}
                    for row in top_players
                ] if top_players else [],
                'recent_map': recent_map[0] if recent_map else None
            }

        except Exception as e:
            logger.error(f"Error getting session stats: {e}")
            return None

    def _format_duration(self, duration: timedelta) -> str:
        """Format timedelta as human-readable string"""
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"


async def setup(bot):
    """Load the LiveCog"""
    await bot.add_cog(LiveCog(bot))
