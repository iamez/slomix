"""
Player Insights Cog - Performance tracking, records, and analytics

This cog handles:
- !records - Personal best performances and milestones
- !trend - Performance trends over time
- !rating - Skill rating system
- !map_stats - Map-specific statistics
- !playstyle - Class/weapon proficiency analysis
- !personality - Player stereotype classification

Commands use the bot's StatsCache for performance and support @mentions and linked accounts.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

import discord
from discord.ext import commands

from bot.stats import StatsCalculator

logger = logging.getLogger(__name__)


class PlayerInsightsCog(commands.Cog, name="PlayerInsights"):
    """Advanced player performance tracking and analytics"""

    def __init__(self, bot):
        self.bot = bot
        self.stats_cache = bot.stats_cache
        self.season_manager = bot.season_manager
        logger.info("🎯 PlayerInsightsCog initializing...")

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

    async def _resolve_player(self, ctx, player_name: Optional[str] = None) -> Optional[Tuple[str, str]]:
        """
        Resolve player from @mention, linked account, or name search.
        Returns (player_guid, primary_name) or None if not found.
        """
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

    @commands.command(name="records", aliases=["bests", "personal_bests", "pb"])
    async def records(self, ctx, *, player_name: Optional[str] = None):
        """🏆 View your personal best performances and milestones

        Usage:
        - !records              → Your records (if linked)
        - !records playerName   → Search by name
        - !records @user        → Records for mentioned user
        """
        try:
            result = await self._resolve_player(ctx, player_name)
            if not result:
                return

            player_guid, primary_name = result

            # Get personal records from database
            records_query = """
                SELECT
                    MAX(p.kills) as max_kills,
                    MAX(p.deaths) as max_deaths,
                    MAX(p.damage_given) as max_damage,
                    MAX(p.headshot_kills) as max_headshots,
                    MAX(p.kd_ratio) as max_kd,
                    MAX(p.revives) as max_revives,
                    MAX(p.gibs) as max_gibs,
                    MAX(p.objectives) as max_objectives,
                    MAX(p.multikills) as max_multikills,
                    MAX(p.efficiency) as max_efficiency,
                    MIN(CASE WHEN p.deaths > 0 THEN p.deaths ELSE NULL END) as min_deaths,
                    COUNT(DISTINCT p.round_id) as total_rounds
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid = ?
                    AND r.round_number IN (1, 2)
                    AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            """

            records = await self.bot.db_adapter.fetch_one(records_query, (player_guid,))

            if not records or not records[11]:  # total_rounds is 0
                await ctx.send(f"❌ No stats found for {primary_name}")
                return

            # Get the rounds where records were achieved
            max_kills_round = await self.bot.db_adapter.fetch_one(
                """
                SELECT r.map_name, r.round_date, p.kills, p.deaths
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid = ? AND p.kills = ?
                    AND r.round_number IN (1, 2)
                ORDER BY r.round_date DESC
                LIMIT 1
                """,
                (player_guid, records[0])
            )

            max_damage_round = await self.bot.db_adapter.fetch_one(
                """
                SELECT r.map_name, r.round_date, p.damage_given
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid = ? AND p.damage_given = ?
                    AND r.round_number IN (1, 2)
                ORDER BY r.round_date DESC
                LIMIT 1
                """,
                (player_guid, records[2])
            )

            max_headshots_round = await self.bot.db_adapter.fetch_one(
                """
                SELECT r.map_name, r.round_date, p.headshot_kills
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid = ? AND p.headshot_kills = ?
                    AND r.round_number IN (1, 2)
                ORDER BY r.round_date DESC
                LIMIT 1
                """,
                (player_guid, records[3])
            )

            # Calculate milestones
            total_rounds = records[11]
            milestone_games = [100, 250, 500, 1000, 2500, 5000]
            next_milestone = next((m for m in milestone_games if m > total_rounds), None)
            games_to_milestone = next_milestone - total_rounds if next_milestone else 0

            # Get total career stats for milestones
            career_stats = await self.bot.db_adapter.fetch_one(
                """
                SELECT
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths,
                    SUM(p.damage_given) as total_damage,
                    SUM(p.headshot_kills) as total_headshots,
                    SUM(p.revives) as total_revives,
                    SUM(p.objectives) as total_objectives
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid = ?
                    AND r.round_number IN (1, 2)
                    AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                """,
                (player_guid,)
            )

            # Build embed
            embed = discord.Embed(
                title=f"🏆 Personal Records - {primary_name}",
                description=f"Best performances across {total_rounds:,} rounds",
                color=0xFFD700  # Gold
            )

            # Combat Records
            combat_records = []
            if max_kills_round:
                combat_records.append(
                    f"**{records[0]} Kills** ({records[0]}-{max_kills_round[3]})\n"
                    f"└ {max_kills_round[0]} • {max_kills_round[1]}"
                )
            if max_damage_round:
                combat_records.append(
                    f"**{records[2]:,} Damage**\n"
                    f"└ {max_damage_round[0]} • {max_damage_round[1]}"
                )
            if max_headshots_round:
                combat_records.append(
                    f"**{records[3]} Headshots**\n"
                    f"└ {max_headshots_round[0]} • {max_headshots_round[1]}"
                )
            if records[4]:  # max_kd
                combat_records.append(f"**{records[4]:.2f} K/D Ratio**")

            if combat_records:
                embed.add_field(
                    name="⚔️ Combat Records",
                    value="\n\n".join(combat_records),
                    inline=False
                )

            # Objective Records
            objective_records = []
            if records[5]:  # max_revives
                objective_records.append(f"**{records[5]} Revives**")
            if records[6]:  # max_gibs
                objective_records.append(f"**{records[6]} Gibs**")
            if records[7]:  # max_objectives
                objective_records.append(f"**{records[7]} Objectives**")
            if records[8]:  # max_multikills
                objective_records.append(f"**{records[8]} Multikills**")

            if objective_records:
                embed.add_field(
                    name="🎯 Objective Records",
                    value=" • ".join(objective_records),
                    inline=False
                )

            # Other Records
            other_records = []
            if records[9]:  # max_efficiency
                other_records.append(f"**{records[9]:.1f}% Efficiency**")
            if records[10]:  # min_deaths (fewest deaths in a round)
                other_records.append(f"**{records[10]} Fewest Deaths**")

            if other_records:
                embed.add_field(
                    name="📊 Other Records",
                    value=" • ".join(other_records),
                    inline=False
                )

            # Career Milestones
            milestones = []
            if career_stats[0]:  # total_kills
                milestone_kills = [500, 1000, 2500, 5000, 10000, 25000]
                next_kill_milestone = next((m for m in milestone_kills if m > career_stats[0]), None)
                milestones.append(
                    f"🔫 **{career_stats[0]:,} Career Kills**"
                    + (f" ({next_kill_milestone - career_stats[0]:,} to {next_kill_milestone:,})" if next_kill_milestone else " 🌟")
                )

            if career_stats[3]:  # total_headshots
                milestone_hs = [100, 250, 500, 1000, 2500, 5000]
                next_hs_milestone = next((m for m in milestone_hs if m > career_stats[3]), None)
                milestones.append(
                    f"🎯 **{career_stats[3]:,} Career Headshots**"
                    + (f" ({next_hs_milestone - career_stats[3]:,} to {next_hs_milestone:,})" if next_hs_milestone else " 🌟")
                )

            if next_milestone:
                milestones.append(f"🎮 **{total_rounds:,} Games Played** ({games_to_milestone:,} to {next_milestone:,})")
            else:
                milestones.append(f"🎮 **{total_rounds:,} Games Played** 🌟")

            if milestones:
                embed.add_field(
                    name="🎖️ Career Milestones",
                    value="\n".join(milestones),
                    inline=False
                )

            embed.set_footer(text="💡 Break your own records to see them update!")
            embed.timestamp = datetime.utcnow()

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in records command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving records: {e}")


async def setup(bot):
    """Load the PlayerInsightsCog"""
    await bot.add_cog(PlayerInsightsCog(bot))
