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

    @commands.command(name="map_stats", aliases=["mapstats", "map_performance"])
    async def map_stats(self, ctx, *, player_name: Optional[str] = None):
        """🗺️ View performance breakdown by map

        Usage:
        - !map_stats              → Your map stats (if linked)
        - !map_stats playerName   → Search by name
        - !map_stats @user        → Map stats for mentioned user
        """
        try:
            result = await self._resolve_player(ctx, player_name)
            if not result:
                return

            player_guid, primary_name = result

            # Get per-map statistics
            map_stats_query = """
                SELECT
                    r.map_name,
                    COUNT(DISTINCT p.round_id) as games_played,
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths,
                    CASE
                        WHEN SUM(p.deaths) > 0 THEN CAST(SUM(p.kills) AS FLOAT) / SUM(p.deaths)
                        ELSE CAST(SUM(p.kills) AS FLOAT)
                    END as kd_ratio,
                    AVG(p.damage_given) as avg_damage,
                    AVG(p.headshot_kills) as avg_headshots,
                    SUM(CASE WHEN r.winner_team = p.team THEN 1 ELSE 0 END) as wins
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid = ?
                    AND r.round_number IN (1, 2)
                    AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                GROUP BY r.map_name
                ORDER BY games_played DESC, kd_ratio DESC
                LIMIT 15
            """

            map_stats = await self.bot.db_adapter.fetch_all(map_stats_query, (player_guid,))

            if not map_stats:
                await ctx.send(f"❌ No map statistics found for {primary_name}")
                return

            # Calculate best and worst maps
            sorted_by_kd = sorted(map_stats, key=lambda x: x[4], reverse=True)
            best_map = sorted_by_kd[0]
            worst_map = sorted_by_kd[-1]

            # Build embed
            embed = discord.Embed(
                title=f"🗺️ Map Performance - {primary_name}",
                description=f"Statistics across {len(map_stats)} maps",
                color=0x3498DB  # Blue
            )

            # Best map
            embed.add_field(
                name=f"🏆 Best Map: {best_map[0]}",
                value=(
                    f"**{best_map[4]:.2f} K/D** • {best_map[1]} games\n"
                    f"{best_map[2]} kills • {best_map[3]} deaths\n"
                    f"Win Rate: {(best_map[7]/best_map[1]*100):.1f}%"
                ),
                inline=True
            )

            # Worst map
            embed.add_field(
                name=f"⚠️ Worst Map: {worst_map[0]}",
                value=(
                    f"**{worst_map[4]:.2f} K/D** • {worst_map[1]} games\n"
                    f"{worst_map[2]} kills • {worst_map[3]} deaths\n"
                    f"Win Rate: {(worst_map[7]/worst_map[1]*100):.1f}%"
                ),
                inline=True
            )

            # Map breakdown (top 10)
            map_list = []
            for i, (map_name, games, kills, deaths, kd, avg_dmg, avg_hs, wins) in enumerate(map_stats[:10], 1):
                win_rate = (wins / games * 100) if games > 0 else 0
                map_list.append(
                    f"**{i}. {map_name}**\n"
                    f"└ {games} games • {kd:.2f} K/D • {win_rate:.0f}% WR"
                )

            embed.add_field(
                name="📊 Map Breakdown",
                value="\n".join(map_list),
                inline=False
            )

            embed.set_footer(text="💡 Play more maps to see more stats!")
            embed.timestamp = datetime.utcnow()

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in map_stats command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving map stats: {e}")

    @commands.command(name="playstyle", aliases=["style", "loadout", "weapons"])
    async def playstyle(self, ctx, *, player_name: Optional[str] = None):
        """🎯 Analyze your playstyle and weapon proficiency

        Usage:
        - !playstyle              → Your playstyle (if linked)
        - !playstyle playerName   → Search by name
        - !playstyle @user        → Playstyle for mentioned user
        """
        try:
            result = await self._resolve_player(ctx, player_name)
            if not result:
                return

            player_guid, primary_name = result

            # Get weapon statistics
            weapon_stats_query = """
                SELECT
                    w.weapon_name,
                    SUM(w.kills) as total_kills,
                    SUM(w.deaths) as total_deaths,
                    SUM(w.headshots) as total_headshots,
                    CASE
                        WHEN SUM(w.shots) > 0 THEN CAST(SUM(w.hits) AS FLOAT) / SUM(w.shots) * 100
                        ELSE 0
                    END as accuracy
                FROM weapon_comprehensive_stats w
                JOIN rounds r ON w.round_id = r.id
                WHERE w.player_guid = ?
                    AND r.round_number IN (1, 2)
                    AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                GROUP BY w.weapon_name
                HAVING SUM(w.kills) > 0
                ORDER BY total_kills DESC
                LIMIT 10
            """

            weapon_stats = await self.bot.db_adapter.fetch_all(weapon_stats_query, (player_guid,))

            if not weapon_stats:
                await ctx.send(f"❌ No weapon statistics found for {primary_name}")
                return

            # Get overall stats for classification
            overall_stats = await self.bot.db_adapter.fetch_one(
                """
                SELECT
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths,
                    SUM(p.headshot_kills) as total_headshots,
                    SUM(p.revives) as total_revives,
                    SUM(p.gibs) as total_gibs,
                    SUM(p.objectives) as total_objectives,
                    SUM(p.damage_given) as total_damage,
                    COUNT(DISTINCT p.round_id) as total_rounds
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid = ?
                    AND r.round_number IN (1, 2)
                    AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                """,
                (player_guid,)
            )

            # Calculate playstyle classification
            total_kills = overall_stats[0] or 1
            total_rounds = overall_stats[7] or 1
            hs_rate = (overall_stats[2] / total_kills * 100) if total_kills > 0 else 0
            revives_per_game = overall_stats[3] / total_rounds
            objectives_per_game = overall_stats[5] / total_rounds
            kd_ratio = overall_stats[0] / overall_stats[1] if overall_stats[1] > 0 else 0

            # Classify playstyle
            playstyle_tags = []
            if hs_rate > 30:
                playstyle_tags.append("🎯 Sharpshooter")
            if revives_per_game > 3:
                playstyle_tags.append("⚕️ Medic Main")
            if objectives_per_game > 2:
                playstyle_tags.append("🎖️ Objective Runner")
            if kd_ratio > 2.0:
                playstyle_tags.append("💀 Fragger")
            elif kd_ratio < 0.8:
                playstyle_tags.append("🛡️ Support Player")

            if not playstyle_tags:
                playstyle_tags.append("⚔️ Balanced Player")

            # Build embed
            embed = discord.Embed(
                title=f"🎯 Playstyle Analysis - {primary_name}",
                description=" • ".join(playstyle_tags),
                color=0x9B59B6  # Purple
            )

            # Top weapons
            top_weapons = []
            for i, (weapon, kills, deaths, headshots, accuracy) in enumerate(weapon_stats[:5], 1):
                hs_rate_weapon = (headshots / kills * 100) if kills > 0 else 0
                top_weapons.append(
                    f"**{i}. {weapon}**\n"
                    f"└ {kills:,} kills • {accuracy:.1f}% acc • {hs_rate_weapon:.1f}% HS"
                )

            embed.add_field(
                name="🔫 Top Weapons",
                value="\n".join(top_weapons),
                inline=False
            )

            # Playstyle metrics
            metrics = [
                f"**Headshot Rate:** {hs_rate:.1f}%",
                f"**K/D Ratio:** {kd_ratio:.2f}",
                f"**Revives/Game:** {revives_per_game:.1f}",
                f"**Objectives/Game:** {objectives_per_game:.1f}",
                f"**Damage/Game:** {overall_stats[6]/total_rounds:,.0f}"
            ]

            embed.add_field(
                name="📊 Playstyle Metrics",
                value="\n".join(metrics),
                inline=False
            )

            # Weapon diversity
            total_weapons_used = len(weapon_stats)
            primary_weapon_kills = weapon_stats[0][1] if weapon_stats else 0
            weapon_diversity = (1 - primary_weapon_kills / total_kills) * 100 if total_kills > 0 else 0

            embed.add_field(
                name="🎲 Weapon Diversity",
                value=f"{weapon_diversity:.1f}% • Using {total_weapons_used} different weapons",
                inline=False
            )

            embed.set_footer(text="💡 Try different weapons to expand your playstyle!")
            embed.timestamp = datetime.utcnow()

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in playstyle command: {e}", exc_info=True)
            await ctx.send(f"❌ Error analyzing playstyle: {e}")

    @commands.command(name="personality", aliases=["player_type", "archetype"])
    async def personality(self, ctx, *, player_name: Optional[str] = None):
        """🎭 Discover your player personality type

        Usage:
        - !personality              → Your personality (if linked)
        - !personality playerName   → Search by name
        - !personality @user        → Personality for mentioned user
        """
        try:
            result = await self._resolve_player(ctx, player_name)
            if not result:
                return

            player_guid, primary_name = result

            # Get comprehensive stats for personality analysis
            personality_stats = await self.bot.db_adapter.fetch_one(
                """
                SELECT
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths,
                    SUM(p.headshot_kills) as total_headshots,
                    SUM(p.revives) as total_revives,
                    SUM(p.gibs) as total_gibs,
                    SUM(p.objectives) as total_objectives,
                    SUM(p.damage_given) as total_damage,
                    SUM(p.damage_received) as total_damage_received,
                    SUM(p.team_damage) as total_team_damage,
                    SUM(p.team_kills) as total_team_kills,
                    SUM(p.multikills) as total_multikills,
                    SUM(p.knife_kills) as total_knife_kills,
                    SUM(p.grenades) as total_grenades,
                    COUNT(DISTINCT p.round_id) as total_rounds,
                    AVG(p.efficiency) as avg_efficiency
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid = ?
                    AND r.round_number IN (1, 2)
                    AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                """,
                (player_guid,)
            )

            if not personality_stats or not personality_stats[13]:  # total_rounds
                await ctx.send(f"❌ Not enough data for {primary_name}")
                return

            # Calculate personality metrics
            total_kills = personality_stats[0] or 1
            total_deaths = personality_stats[1] or 1
            total_rounds = personality_stats[13] or 1
            kd_ratio = total_kills / total_deaths if total_deaths > 0 else total_kills

            hs_rate = (personality_stats[2] / total_kills * 100) if total_kills > 0 else 0
            revives_per_game = personality_stats[3] / total_rounds
            gibs_per_game = personality_stats[4] / total_rounds
            objectives_per_game = personality_stats[5] / total_rounds
            damage_ratio = personality_stats[6] / personality_stats[7] if personality_stats[7] > 0 else 1
            aggression = (personality_stats[6] / total_rounds) / 1000  # Normalize damage
            multikills_per_game = personality_stats[10] / total_rounds
            knife_kills_rate = (personality_stats[11] / total_kills * 100) if total_kills > 0 else 0

            # Personality classification algorithm
            personality_type = None
            personality_desc = ""
            personality_traits = []

            # Primary archetypes
            if hs_rate > 35 and kd_ratio > 1.5:
                personality_type = "🎯 The Sharpshooter"
                personality_desc = "Deadly accurate with exceptional aim. Every shot counts."
                personality_traits = ["Precision-focused", "Patient", "Calculated"]
            elif revives_per_game > 4 and objectives_per_game < 1:
                personality_type = "⚕️ The Medic"
                personality_desc = "Team player who keeps everyone alive. The backbone of the squad."
                personality_traits = ["Supportive", "Team-oriented", "Selfless"]
            elif objectives_per_game > 3:
                personality_type = "🎖️ The Objective Runner"
                personality_desc = "Mission-focused and objective-driven. Gets things done."
                personality_traits = ["Goal-oriented", "Determined", "Strategic"]
            elif kd_ratio > 2.5 and multikills_per_game > 0.5:
                personality_type = "💀 The Fragger"
                personality_desc = "Pure killing machine. Dominates every engagement."
                personality_traits = ["Aggressive", "Dominant", "Relentless"]
            elif gibs_per_game > 2 and kd_ratio > 1.5:
                personality_type = "🔪 The Executioner"
                personality_desc = "Finishes what others start. No mercy, no prisoners."
                personality_traits = ["Ruthless", "Efficient", "Unforgiving"]
            elif knife_kills_rate > 5:
                personality_type = "🗡️ The Assassin"
                personality_desc = "Silent and deadly. Prefers the personal touch."
                personality_traits = ["Stealthy", "Bold", "Unpredictable"]
            elif revives_per_game > 2 and objectives_per_game > 2:
                personality_type = "🛡️ The All-Rounder"
                personality_desc = "Jack of all trades, master of teamwork. Does whatever it takes."
                personality_traits = ["Versatile", "Adaptable", "Reliable"]
            elif damage_ratio > 1.5 and kd_ratio > 1.2:
                personality_type = "🔥 The Aggressor"
                personality_desc = "Always on the attack. Pressure and aggression define your game."
                personality_traits = ["Fearless", "Intense", "High-energy"]
            elif kd_ratio < 0.8 and revives_per_game > 2:
                personality_type = "🏥 The Selfless Healer"
                personality_desc = "Puts the team first, even at personal cost. A true hero."
                personality_traits = ["Sacrificial", "Caring", "Noble"]
            elif personality_stats[14] and personality_stats[14] > 60:  # avg_efficiency
                personality_type = "⚡ The Efficient Operator"
                personality_desc = "Maximizes every action. No wasted movement, no wasted effort."
                personality_traits = ["Methodical", "Smart", "Optimized"]
            else:
                personality_type = "⚔️ The Warrior"
                personality_desc = "Steady and reliable. A solid presence in every match."
                personality_traits = ["Consistent", "Dependable", "Balanced"]

            # Build embed
            embed = discord.Embed(
                title=f"{personality_type}",
                description=f"**{primary_name}**\n\n*{personality_desc}*",
                color=0xE74C3C  # Red
            )

            # Personality traits
            embed.add_field(
                name="🎭 Traits",
                value=" • ".join(personality_traits),
                inline=False
            )

            # Key stats that define this personality
            key_stats = [
                f"**K/D Ratio:** {kd_ratio:.2f}",
                f"**Headshot Rate:** {hs_rate:.1f}%",
                f"**Revives/Game:** {revives_per_game:.1f}",
                f"**Objectives/Game:** {objectives_per_game:.1f}",
            ]

            if multikills_per_game > 0.3:
                key_stats.append(f"**Multikills/Game:** {multikills_per_game:.1f}")
            if knife_kills_rate > 2:
                key_stats.append(f"**Knife Kills:** {knife_kills_rate:.1f}%")

            embed.add_field(
                name="📊 Defining Stats",
                value="\n".join(key_stats),
                inline=False
            )

            # Fun facts
            fun_facts = []
            if hs_rate > 40:
                fun_facts.append("🎯 Headshot artist - every shot is a work of art")
            if revives_per_game > 5:
                fun_facts.append("⚕️ Guardian angel - you've saved countless lives")
            if gibs_per_game > 3:
                fun_facts.append("💀 No respect for the fallen - maximum disrespect")
            if knife_kills_rate > 10:
                fun_facts.append("🗡️ Knife fanatic - why use bullets?")
            if multikills_per_game > 1:
                fun_facts.append("🔥 Streak master - multi-kills are your specialty")
            if damage_ratio > 2:
                fun_facts.append("💥 Damage dealer - you dish it out way more than you take it")

            if fun_facts:
                embed.add_field(
                    name="✨ Fun Facts",
                    value="\n".join(fun_facts),
                    inline=False
                )

            embed.set_footer(text=f"Based on {total_rounds:,} games played")
            embed.timestamp = datetime.utcnow()

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in personality command: {e}", exc_info=True)
            await ctx.send(f"❌ Error analyzing personality: {e}")


async def setup(bot):
    """Load the PlayerInsightsCog"""
    await bot.add_cog(PlayerInsightsCog(bot))
