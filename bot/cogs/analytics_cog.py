"""
Analytics Cog

Advanced player analytics commands:
- !consistency <player>
- !map_stats <player>
- !playstyle <player>
- !awards (session fun stats)
"""

import logging
from typing import Optional

import discord
from discord.ext import commands

from bot.core.checks import is_public_channel
from bot.services.player_analytics_service import PlayerAnalyticsService

logger = logging.getLogger("bot.cogs.analytics")


class AnalyticsCog(commands.Cog):
    """Advanced player analytics commands."""

    def __init__(self, bot):
        self.bot = bot
        self.analytics = PlayerAnalyticsService(bot.db_adapter)
        logger.info("AnalyticsCog initialized")

    async def _resolve_player_guid(self, player_name: str) -> Optional[str]:
        """Resolve player name to GUID."""
        query = """
            SELECT DISTINCT player_guid
            FROM player_comprehensive_stats
            WHERE LOWER(player_name) = LOWER($1)
            LIMIT 1
        """
        result = await self.bot.db_adapter.fetch_one(query, (player_name,))
        if result:
            return result[0]

        # Try partial match
        query = """
            SELECT DISTINCT player_guid
            FROM player_comprehensive_stats
            WHERE LOWER(player_name) LIKE LOWER($1)
            ORDER BY round_date DESC
            LIMIT 1
        """
        result = await self.bot.db_adapter.fetch_one(query, (f"%{player_name}%",))
        return result[0] if result else None

    @commands.command(name="consistency", aliases=["reliable", "variance"])
    @is_public_channel()
    async def consistency_command(self, ctx, *, player: str = None):
        """
        Show player's consistency score (reliability).

        Measures how stable a player's performance is across rounds.
        Higher score = more predictable/reliable performance.

        Usage: !consistency <player>
        """
        if not player:
            await ctx.send("**Usage:** `!consistency <player>`")
            return

        async with ctx.typing():
            guid = await self._resolve_player_guid(player)
            if not guid:
                await ctx.send(f"Could not find player: {player}")
                return

            stats = await self.analytics.get_consistency_score(guid)

            if not stats:
                await ctx.send(f"Not enough data for {player} (need 10+ rounds)")
                return

            # Color based on consistency
            if stats.consistency_score >= 70:
                color = discord.Color.green()
            elif stats.consistency_score >= 50:
                color = discord.Color.gold()
            else:
                color = discord.Color.red()

            embed = discord.Embed(
                title="📊 Consistency Analysis",
                description=self.analytics.format_consistency(stats),
                color=color
            )

            # Add interpretation
            if stats.consistency_tier == "Consistent":
                embed.set_footer(text="You know what you're getting - reliable every game")
            elif stats.consistency_tier == "Streaky":
                embed.set_footer(text="Feast or famine - can carry or struggle")
            else:
                embed.set_footer(text="Mix of good and bad games")

            await ctx.send(embed=embed)

    @commands.command(name="map_stats", aliases=["maps", "mapstats"])
    @is_public_channel()
    async def map_stats_command(self, ctx, *, player: str = None):
        """
        Show player's performance by map.

        Shows which maps a player overperforms or underperforms on.

        Usage: !map_stats <player>
        """
        if not player:
            await ctx.send("**Usage:** `!map_stats <player>`")
            return

        async with ctx.typing():
            guid = await self._resolve_player_guid(player)
            if not guid:
                await ctx.send(f"Could not find player: {player}")
                return

            stats = await self.analytics.get_map_affinity(guid)

            if not stats:
                await ctx.send(f"Not enough map data for {player}")
                return

            embed = discord.Embed(
                title="🗺️ Map Performance",
                description=self.analytics.format_map_affinity(stats),
                color=discord.Color.blue()
            )

            # Highlight best/worst
            if stats.best_map and stats.worst_map:
                embed.add_field(
                    name="Summary",
                    value=(
                        f"**Best:** {stats.best_map} (+{stats.best_map_delta:.0f}%)\n"
                        f"**Worst:** {stats.worst_map} ({stats.worst_map_delta:.0f}%)"
                    ),
                    inline=False
                )

            await ctx.send(embed=embed)

    @commands.command(name="playstyle", aliases=["style", "role"])
    @is_public_channel()
    async def playstyle_command(self, ctx, *, player: str = None):
        """
        Show player's attack vs defense preference.

        Analyzes whether a player performs better on attack or defense.

        Usage: !playstyle <player>
        """
        if not player:
            await ctx.send("**Usage:** `!playstyle <player>`")
            return

        async with ctx.typing():
            guid = await self._resolve_player_guid(player)
            if not guid:
                await ctx.send(f"Could not find player: {player}")
                return

            stats = await self.analytics.get_playstyle_preference(guid)

            if not stats:
                await ctx.send(f"Not enough data for {player} (need 10+ rounds)")
                return

            # Color based on preference
            if stats.preference == "attacker":
                color = discord.Color.red()
            elif stats.preference == "defender":
                color = discord.Color.blue()
            else:
                color = discord.Color.purple()

            embed = discord.Embed(
                title="⚔️ Playstyle Analysis",
                description=self.analytics.format_playstyle(stats),
                color=color
            )

            # Add recommendation
            if stats.preference == "attacker":
                embed.set_footer(text="Consider volunteering to attack more often")
            elif stats.preference == "defender":
                embed.set_footer(text="Your defensive play is your strength")
            else:
                embed.set_footer(text="Versatile player - adapts to both roles")

            await ctx.send(embed=embed)

    @commands.command(name="awards", aliases=["fun_stats", "funstats"])
    @is_public_channel()
    async def awards_command(self, ctx):
        """
        Show fun/celebratory awards for the latest session.

        Non-toxic stats that celebrate different playstyles.

        Usage: !awards
        """
        async with ctx.typing():
            # Get latest session
            from bot.services.session_data_service import SessionDataService
            data_service = SessionDataService(self.bot.db_adapter, None)

            latest_date = await data_service.get_latest_session_date()
            if not latest_date:
                await ctx.send("No sessions found")
                return

            _, session_ids, _, _ = await data_service.fetch_session_data(latest_date)

            if not session_ids:
                await ctx.send("No rounds found for latest session")
                return

            awards = await self.analytics.get_session_fun_awards(session_ids)

            if not awards:
                await ctx.send("No awards earned this session")
                return

            embed = discord.Embed(
                title=f"🏆 Session Awards - {latest_date}",
                description=self.analytics.format_awards(awards),
                color=discord.Color.gold()
            )

            await ctx.send(embed=embed)

    @commands.command(name="fatigue")
    @is_public_channel()
    async def fatigue_command(self, ctx, *, player: str = None):
        """
        Show if a player fatigued during their latest session.

        Compares early vs late session performance.

        Usage: !fatigue <player>
        """
        if not player:
            await ctx.send("**Usage:** `!fatigue <player>`")
            return

        async with ctx.typing():
            guid = await self._resolve_player_guid(player)
            if not guid:
                await ctx.send(f"Could not find player: {player}")
                return

            # Get latest gaming session for this player
            query = """
                SELECT DISTINCT r.gaming_session_id
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid = $1
                ORDER BY r.gaming_session_id DESC
                LIMIT 1
            """
            result = await self.bot.db_adapter.fetch_one(query, (guid,))

            if not result:
                await ctx.send(f"No session data for {player}")
                return

            gaming_session_id = result[0]
            stats = await self.analytics.get_session_fatigue(guid, gaming_session_id)

            if not stats:
                await ctx.send(f"Not enough rounds in session for fatigue analysis (need 6+)")
                return

            # Color based on trend
            if stats.trend == "warming_up":
                color = discord.Color.green()
                emoji = "📈"
            elif stats.trend == "fatiguing":
                color = discord.Color.red()
                emoji = "📉"
            else:
                color = discord.Color.blue()
                emoji = "➖"

            embed = discord.Embed(
                title=f"{emoji} Session Fatigue Analysis",
                color=color
            )

            embed.add_field(
                name="DPM by Session Phase",
                value=(
                    f"**Early:** {stats.early_dpm:.1f}\n"
                    f"**Mid:** {stats.mid_dpm:.1f}\n"
                    f"**Late:** {stats.late_dpm:.1f}"
                ),
                inline=True
            )

            sign = "+" if stats.fatigue_index >= 0 else ""
            embed.add_field(
                name="Summary",
                value=(
                    f"**Trend:** {stats.trend.replace('_', ' ').title()}\n"
                    f"**Change:** {sign}{stats.fatigue_index:.0f}%\n"
                    f"**Rounds:** {stats.total_rounds}"
                ),
                inline=True
            )

            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AnalyticsCog(bot))
