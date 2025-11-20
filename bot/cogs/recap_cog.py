"""
Recap Cog - Performance summaries and recaps

This cog handles:
- !recap_week - Weekly performance recap
- !recap_month - Monthly performance recap
- !recap_year - Yearly performance recap

Commands provide comprehensive performance summaries over different time periods.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class RecapCog(commands.Cog, name="Recap"):
    """Performance recap and summary system"""

    def __init__(self, bot):
        self.bot = bot
        self.stats_cache = bot.stats_cache
        logger.info("📅 RecapCog initializing...")

    async def _ensure_player_name_alias(self):
        """Create temp view/alias for player_name column compatibility"""
        try:
            if self.bot.config.database_type == 'sqlite':
                await self.bot.db_adapter.execute(
                    "CREATE TEMP VIEW IF NOT EXISTS player_comprehensive_stats_alias AS "
                    "SELECT *, player_name AS name FROM player_comprehensive_stats"
                )
        except Exception:
            pass

    async def _resolve_player(self, ctx, player_name: Optional[str] = None):
        """Resolve player from @mention, linked account, or name search"""
        try:
            await self._ensure_player_name_alias()
        except Exception:
            pass

        player_guid = None
        primary_name = None

        # Handle @mention
        if ctx.message.mentions:
            mentioned_user = ctx.message.mentions[0]
            mentioned_id = int(mentioned_user.id)

            link = await self.bot.db_adapter.fetch_one(
                "SELECT et_guid, et_name FROM player_links WHERE discord_id = ?",
                (mentioned_id,),
            )

            if not link:
                await ctx.send(f"❌ {mentioned_user.mention} hasn't linked their account yet!")
                return None

            player_guid = link[0]
            primary_name = link[1]

        # Handle no arguments - use author's linked account
        elif not player_name:
            discord_id = int(ctx.author.id)
            query = """
                SELECT et_guid, et_name FROM player_links WHERE discord_id = $1
            """ if self.bot.config.database_type == 'postgresql' else """
                SELECT et_guid, et_name FROM player_links WHERE discord_id = ?
            """
            link = await self.bot.db_adapter.fetch_one(query, (discord_id,))

            if not link:
                await ctx.send("❌ You haven't linked your account! Use `!link` to get started.")
                return None

            player_guid = link[0]
            primary_name = link[1]

        # Handle name search
        else:
            # Try exact GUID match first
            result = await self.bot.db_adapter.fetch_one(
                "SELECT player_guid, player_name FROM player_comprehensive_stats WHERE player_guid = ? LIMIT 1",
                (player_name,),
            )

            # If not GUID, search by name
            if not result:
                query = """
                    SELECT player_guid, player_name FROM player_comprehensive_stats
                    WHERE player_name ILIKE $1
                    LIMIT 1
                """ if self.bot.config.database_type == 'postgresql' else """
                    SELECT player_guid, player_name FROM player_comprehensive_stats
                    WHERE player_name LIKE ?
                    LIMIT 1
                """
                result = await self.bot.db_adapter.fetch_one(
                    query,
                    (f"%{player_name}%",),
                )

            if not result:
                await ctx.send(f"❌ Player '{player_name}' not found.")
                return None

            player_guid = result[0]
            primary_name = result[1]

        return (player_guid, primary_name)

    async def _get_recap_stats(self, player_guid: str, days: int) -> Optional[Dict]:
        """Get performance statistics for the specified time period"""
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')

        # Get stats for the period
        stats = await self.bot.db_adapter.fetch_one(
            """
            SELECT
                COUNT(DISTINCT p.round_id) as games_played,
                SUM(p.kills) as total_kills,
                SUM(p.deaths) as total_deaths,
                SUM(p.damage_given) as total_damage,
                SUM(p.headshot_kills) as total_headshots,
                SUM(p.revives) as total_revives,
                SUM(p.gibs) as total_gibs,
                SUM(p.objectives) as total_objectives,
                SUM(p.multikills) as total_multikills,
                AVG(p.kd_ratio) as avg_kd,
                AVG(p.efficiency) as avg_efficiency,
                MAX(p.kills) as best_kills,
                MAX(p.damage_given) as best_damage,
                SUM(CASE WHEN r.winner_team = p.team THEN 1 ELSE 0 END) as wins
            FROM player_comprehensive_stats p
            JOIN rounds r ON p.round_id = r.id
            WHERE p.player_guid = ?
                AND r.round_date >= ?
                AND r.round_number IN (1, 2)
                AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            """,
            (player_guid, cutoff_str)
        )

        if not stats or not stats[0]:  # No games played
            return None

        # Get comparison to previous period
        prev_cutoff_date = cutoff_date - timedelta(days=days)
        prev_cutoff_str = prev_cutoff_date.strftime('%Y-%m-%d')

        prev_stats = await self.bot.db_adapter.fetch_one(
            """
            SELECT
                COUNT(DISTINCT p.round_id) as games_played,
                AVG(p.kd_ratio) as avg_kd,
                SUM(p.kills) as total_kills,
                SUM(p.deaths) as total_deaths
            FROM player_comprehensive_stats p
            JOIN rounds r ON p.round_id = r.id
            WHERE p.player_guid = ?
                AND r.round_date >= ?
                AND r.round_date < ?
                AND r.round_number IN (1, 2)
                AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            """,
            (player_guid, prev_cutoff_str, cutoff_str)
        )

        # Get best performance round
        best_round = await self.bot.db_adapter.fetch_one(
            """
            SELECT r.map_name, r.round_date, p.kills, p.deaths, p.damage_given
            FROM player_comprehensive_stats p
            JOIN rounds r ON p.round_id = r.id
            WHERE p.player_guid = ?
                AND r.round_date >= ?
                AND r.round_number IN (1, 2)
            ORDER BY p.kills DESC, p.damage_given DESC
            LIMIT 1
            """,
            (player_guid, cutoff_str)
        )

        # Get most played maps
        top_maps = await self.bot.db_adapter.fetch_all(
            """
            SELECT r.map_name, COUNT(*) as plays
            FROM player_comprehensive_stats p
            JOIN rounds r ON p.round_id = r.id
            WHERE p.player_guid = ?
                AND r.round_date >= ?
                AND r.round_number IN (1, 2)
            GROUP BY r.map_name
            ORDER BY plays DESC
            LIMIT 3
            """,
            (player_guid, cutoff_str)
        )

        return {
            'stats': stats,
            'prev_stats': prev_stats,
            'best_round': best_round,
            'top_maps': top_maps
        }

    @commands.command(name="recap_week", aliases=["weekly_recap", "week_recap"])
    async def recap_week(self, ctx, *, player_name: Optional[str] = None):
        """📅 View your weekly performance recap

        Usage:
        - !recap_week              → Your weekly recap (if linked)
        - !recap_week playerName   → Search by name
        - !recap_week @user        → Weekly recap for mentioned user
        """
        try:
            result = await self._resolve_player(ctx, player_name)
            if not result:
                return

            player_guid, primary_name = result

            # Get stats for last 7 days
            recap_data = await self._get_recap_stats(player_guid, 7)

            if not recap_data:
                await ctx.send(f"❌ No activity in the past week for {primary_name}")
                return

            stats = recap_data['stats']
            prev_stats = recap_data['prev_stats']
            best_round = recap_data['best_round']
            top_maps = recap_data['top_maps']

            # Calculate derived stats
            games_played = stats[0]
            kd_ratio = stats[2] / stats[3] if stats[3] > 0 else stats[2]
            hs_rate = (stats[4] / stats[2] * 100) if stats[2] > 0 else 0
            win_rate = (stats[13] / games_played * 100) if games_played > 0 else 0

            # Calculate trends
            kd_trend = ""
            if prev_stats and prev_stats[0] > 0:
                prev_kd = prev_stats[2] / prev_stats[3] if prev_stats[3] > 0 else 0
                kd_diff = kd_ratio - prev_kd
                if kd_diff > 0.1:
                    kd_trend = f" 📈 (+{kd_diff:.2f})"
                elif kd_diff < -0.1:
                    kd_trend = f" 📉 ({kd_diff:.2f})"

            # Build embed
            embed = discord.Embed(
                title=f"📅 Weekly Recap - {primary_name}",
                description=f"Performance summary for the past 7 days",
                color=0x3498DB
            )

            # Overview
            overview = [
                f"🎮 **{games_played} Games Played**",
                f"⚔️ **{stats[2]:,} Kills** • {stats[3]:,} Deaths",
                f"📊 **{kd_ratio:.2f} K/D Ratio**{kd_trend}",
                f"🎯 **{hs_rate:.1f}% Headshot Rate**",
                f"🏆 **{win_rate:.1f}% Win Rate** ({stats[13]}/{games_played})"
            ]

            embed.add_field(
                name="📊 Overview",
                value="\n".join(overview),
                inline=False
            )

            # Best performance
            if best_round:
                embed.add_field(
                    name=f"🌟 Best Round",
                    value=(
                        f"**{best_round[0]}** • {best_round[1]}\n"
                        f"{best_round[2]} kills • {best_round[3]} deaths\n"
                        f"{best_round[4]:,} damage"
                    ),
                    inline=True
                )

            # Highlights
            highlights = []
            if stats[4] > 0:  # headshots
                highlights.append(f"🎯 {stats[4]:,} Headshots")
            if stats[5] > 0:  # revives
                highlights.append(f"⚕️ {stats[5]:,} Revives")
            if stats[7] > 0:  # objectives
                highlights.append(f"🎖️ {stats[7]:,} Objectives")
            if stats[8] > 0:  # multikills
                highlights.append(f"🔥 {stats[8]:,} Multikills")

            if highlights:
                embed.add_field(
                    name="✨ Highlights",
                    value="\n".join(highlights),
                    inline=True
                )

            # Top maps
            if top_maps:
                maps_text = "\n".join([f"**{m[0]}** • {m[1]} games" for m in top_maps])
                embed.add_field(
                    name="🗺️ Most Played Maps",
                    value=maps_text,
                    inline=False
                )

            embed.set_footer(text="💡 Check !recap_month for monthly stats")
            embed.timestamp = datetime.utcnow()

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in recap_week command: {e}", exc_info=True)
            await ctx.send(f"❌ Error generating weekly recap: {e}")

    @commands.command(name="recap_month", aliases=["monthly_recap", "month_recap"])
    async def recap_month(self, ctx, *, player_name: Optional[str] = None):
        """📅 View your monthly performance recap

        Usage:
        - !recap_month              → Your monthly recap (if linked)
        - !recap_month playerName   → Search by name
        - !recap_month @user        → Monthly recap for mentioned user
        """
        try:
            result = await self._resolve_player(ctx, player_name)
            if not result:
                return

            player_guid, primary_name = result

            # Get stats for last 30 days
            recap_data = await self._get_recap_stats(player_guid, 30)

            if not recap_data:
                await ctx.send(f"❌ No activity in the past month for {primary_name}")
                return

            stats = recap_data['stats']
            prev_stats = recap_data['prev_stats']
            best_round = recap_data['best_round']
            top_maps = recap_data['top_maps']

            # Calculate derived stats
            games_played = stats[0]
            kd_ratio = stats[2] / stats[3] if stats[3] > 0 else stats[2]
            hs_rate = (stats[4] / stats[2] * 100) if stats[2] > 0 else 0
            win_rate = (stats[13] / games_played * 100) if games_played > 0 else 0
            dpm = (stats[3] * 60 / games_played) if games_played > 0 else 0

            # Build embed
            embed = discord.Embed(
                title=f"📅 Monthly Recap - {primary_name}",
                description=f"Performance summary for the past 30 days",
                color=0x9B59B6
            )

            # Overview
            overview = [
                f"🎮 **{games_played} Games Played**",
                f"⚔️ **{stats[2]:,} Kills** • {stats[3]:,} Deaths",
                f"📊 **{kd_ratio:.2f} K/D Ratio**",
                f"🎯 **{hs_rate:.1f}% Headshot Rate**",
                f"🏆 **{win_rate:.1f}% Win Rate** ({stats[13]}/{games_played})",
                f"💥 **{stats[3]:,} Total Damage**"
            ]

            embed.add_field(
                name="📊 Monthly Overview",
                value="\n".join(overview),
                inline=False
            )

            # Best performance
            if best_round:
                embed.add_field(
                    name=f"🌟 Best Round This Month",
                    value=(
                        f"**{best_round[0]}** • {best_round[1]}\n"
                        f"{best_round[2]} kills • {best_round[3]} deaths\n"
                        f"{best_round[4]:,} damage"
                    ),
                    inline=True
                )

            # Records
            records = [
                f"🔥 **{stats[11]} Kills** (single game)",
                f"💥 **{stats[12]:,} Damage** (single game)"
            ]

            embed.add_field(
                name="🏆 Monthly Records",
                value="\n".join(records),
                inline=True
            )

            # Contributions
            contributions = []
            if stats[5] > 0:  # revives
                contributions.append(f"⚕️ {stats[5]:,} Revives ({stats[5]/games_played:.1f}/game)")
            if stats[7] > 0:  # objectives
                contributions.append(f"🎖️ {stats[7]:,} Objectives ({stats[7]/games_played:.1f}/game)")
            if stats[6] > 0:  # gibs
                contributions.append(f"💀 {stats[6]:,} Gibs ({stats[6]/games_played:.1f}/game)")

            if contributions:
                embed.add_field(
                    name="🤝 Team Contributions",
                    value="\n".join(contributions),
                    inline=False
                )

            # Top maps
            if top_maps:
                maps_text = "\n".join([f"**{m[0]}** • {m[1]} games" for m in top_maps])
                embed.add_field(
                    name="🗺️ Most Played Maps",
                    value=maps_text,
                    inline=False
                )

            embed.set_footer(text="💡 Use !recap_year for yearly stats")
            embed.timestamp = datetime.utcnow()

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in recap_month command: {e}", exc_info=True)
            await ctx.send(f"❌ Error generating monthly recap: {e}")

    @commands.command(name="recap_year", aliases=["yearly_recap", "year_recap"])
    async def recap_year(self, ctx, *, player_name: Optional[str] = None):
        """📅 View your yearly performance recap

        Usage:
        - !recap_year              → Your yearly recap (if linked)
        - !recap_year playerName   → Search by name
        - !recap_year @user        → Yearly recap for mentioned user
        """
        try:
            result = await self._resolve_player(ctx, player_name)
            if not result:
                return

            player_guid, primary_name = result

            # Get stats for last 365 days
            recap_data = await self._get_recap_stats(player_guid, 365)

            if not recap_data:
                await ctx.send(f"❌ No activity in the past year for {primary_name}")
                return

            stats = recap_data['stats']
            best_round = recap_data['best_round']
            top_maps = recap_data['top_maps']

            # Calculate derived stats
            games_played = stats[0]
            kd_ratio = stats[2] / stats[3] if stats[3] > 0 else stats[2]
            hs_rate = (stats[4] / stats[2] * 100) if stats[2] > 0 else 0
            win_rate = (stats[13] / games_played * 100) if games_played > 0 else 0

            # Build embed
            embed = discord.Embed(
                title=f"🎊 Year in Review - {primary_name}",
                description=f"Your ET:Legacy journey over the past year",
                color=0xE74C3C
            )

            # Major stats
            major_stats = [
                f"🎮 **{games_played:,} Games Played**",
                f"⚔️ **{stats[2]:,} Total Kills**",
                f"💀 **{stats[3]:,} Total Deaths**",
                f"📊 **{kd_ratio:.2f} K/D Ratio**",
                f"🏆 **{win_rate:.1f}% Win Rate**"
            ]

            embed.add_field(
                name="📈 Yearly Stats",
                value="\n".join(major_stats),
                inline=False
            )

            # Combat excellence
            combat = [
                f"🎯 **{stats[4]:,} Headshots** ({hs_rate:.1f}% rate)",
                f"💥 **{stats[3]:,} Total Damage**",
                f"🔥 **{stats[8]:,} Multikills**",
                f"⚡ **{stats[10]:.1f}% Avg Efficiency**"
            ]

            embed.add_field(
                name="⚔️ Combat Excellence",
                value="\n".join(combat),
                inline=False
            )

            # Team play
            team_play = [
                f"⚕️ **{stats[5]:,} Revives** ({stats[5]/games_played:.1f}/game)",
                f"🎖️ **{stats[7]:,} Objectives** ({stats[7]/games_played:.1f}/game)",
                f"💀 **{stats[6]:,} Gibs** ({stats[6]/games_played:.1f}/game)"
            ]

            embed.add_field(
                name="🤝 Team Player",
                value="\n".join(team_play),
                inline=False
            )

            # Best performance
            if best_round:
                embed.add_field(
                    name=f"🌟 Best Round of the Year",
                    value=(
                        f"**{best_round[0]}** • {best_round[1]}\n"
                        f"{best_round[2]} kills • {best_round[3]} deaths\n"
                        f"{best_round[4]:,} damage"
                    ),
                    inline=False
                )

            # Top maps
            if top_maps:
                maps_text = "\n".join([f"**{i+1}. {m[0]}** • {m[1]} games" for i, m in enumerate(top_maps)])
                embed.add_field(
                    name="🗺️ Favorite Maps",
                    value=maps_text,
                    inline=False
                )

            embed.set_footer(text=f"Amazing year, {primary_name}! 🎉")
            embed.timestamp = datetime.utcnow()

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in recap_year command: {e}", exc_info=True)
            await ctx.send(f"❌ Error generating yearly recap: {e}")


async def setup(bot):
    """Load the RecapCog"""
    await bot.add_cog(RecapCog(bot))
