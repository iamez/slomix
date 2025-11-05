"""
Leaderboard Cog - Player statistics and rankings

This cog handles:
- !stats - Detailed individual player statistics with caching
- !leaderboard (aliases: !lb, !top) - Rankings by various stats with pagination

The stats command supports @mentions, linked accounts, and name search.
The leaderboard command supports 13 different stat types including kills, K/D,
DPM, accuracy, headshots, games, revives, gibs, objectives, efficiency,
teamwork, multikills, and grenades.

Both commands use the bot's StatsCache for improved performance.
"""

import logging
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class LeaderboardCog(commands.Cog, name="Leaderboard"):
    """Player statistics and rankings system"""

    def __init__(self, bot):
        self.bot = bot
        self.stats_cache = bot.stats_cache
        logger.info("🏆 LeaderboardCog initializing...")

    async def _ensure_player_name_alias(self):
        """Create temp view/alias for player_name column compatibility"""
        try:
            # Only create alias for SQLite (PostgreSQL will have proper schema)
            if self.bot.config.database_type == 'sqlite':
                await self.bot.db_adapter.execute(
                    "CREATE TEMP VIEW IF NOT EXISTS player_comprehensive_stats_alias AS "
                    "SELECT *, player_name AS name FROM player_comprehensive_stats"
                )
        except Exception:
            pass

    async def _enable_sql_diag(self):
        """Enable SQL diagnostics for troubleshooting (SQLite only)"""
        try:
            # PRAGMA is SQLite-specific
            if self.bot.config.database_type == 'sqlite':
                await self.bot.db_adapter.execute("PRAGMA case_sensitive_like = ON")
        except Exception:
            pass

    @commands.command(name="stats")
    async def stats(self, ctx, *, player_name: str = None):
        """📊 Show detailed player statistics

        Usage:
        - !stats              → Your stats (if linked)
        - !stats playerName   → Search by name
        - !stats @user        → Stats for mentioned Discord user
        """
        try:
            player_guid = None
            primary_name = None

            # Set up database alias and diagnostics
            try:
                await self._ensure_player_name_alias()
            except Exception:
                pass
            # Enable SQL diagnostics for troubleshooting
            try:
                await self._enable_sql_diag()
            except Exception:
                pass
            
            # === SCENARIO 1: @MENTION - Look up linked Discord user ===
            if ctx.message.mentions:
                mentioned_user = ctx.message.mentions[0]
                mentioned_id = str(mentioned_user.id)

                link = await self.bot.db_adapter.fetch_one(
                    """
                    SELECT et_guid, et_name FROM player_links
                    WHERE discord_id = ?
                """,
                    (mentioned_id,),
                )

                if not link:
                    # User not linked - helpful message
                    embed = discord.Embed(
                        title="⚠️ Account Not Linked",
                        description=(
                            f"{mentioned_user.mention} hasn't linked their "
                            f"ET:Legacy account yet!"
                        ),
                        color=0xFFA500,
                    )
                    embed.add_field(
                        name="How to Link",
                        value=(
                            "• `!link` - Search for your player\n"
                            "• `!link <name>` - Link by name\n"
                            "• `!link <GUID>` - Link with GUID"
                        ),
                        inline=False,
                    )
                    embed.add_field(
                        name="Admin Help",
                        value=(
                            f"Admins can help link with:\n"
                            f"`!link {mentioned_user.mention} <GUID>`"
                        ),
                        inline=False,
                    )
                    await ctx.send(embed=embed)
                    return

                player_guid = link[0]
                primary_name = link[1]
                logger.info(
                    f"Stats via @mention: {ctx.author} looked up "
                    f"{mentioned_user} (GUID: {player_guid})"
                )

            # === SCENARIO 2: NO ARGS - Use author's linked account ===
            elif not player_name:
                discord_id = int(ctx.author.id)  # Convert to integer for PostgreSQL BIGINT
                query = """
                    SELECT et_guid, et_name FROM player_links
                    WHERE discord_id = $1
                """ if self.bot.config.database_type == 'postgresql' else """
                    SELECT et_guid, et_name FROM player_links
                    WHERE discord_id = ?
                """
                link = await self.bot.db_adapter.fetch_one(query, (discord_id,))

                if not link:
                    await ctx.send(
                        "❌ Please specify a player name or link your "
                        "account with `!link`"
                    )
                    return

                player_guid = link[0]
                primary_name = link[1]

            # === SCENARIO 3: NAME SEARCH - Traditional lookup ===
            else:
                # Try exact match in player_links first
                link = await self.bot.db_adapter.fetch_one(
                    """
                    SELECT et_guid, et_name FROM player_links
                    WHERE LOWER(et_name) = LOWER(?)
                    LIMIT 1
                """,
                    (player_name,),
                )

                if link:
                    player_guid = link[0]
                    primary_name = link[1]
                else:
                    # Search in player_aliases (uses 'guid' and 'alias' columns)
                    alias_result = await self.bot.db_adapter.fetch_one(
                        """
                        SELECT guid, alias
                        FROM player_aliases
                        WHERE LOWER(alias) LIKE LOWER(?)
                        ORDER BY last_seen DESC
                        LIMIT 1
                    """,
                        (f"%{player_name}%",),
                    )

                    if alias_result:
                        player_guid = alias_result[0]
                        primary_name = alias_result[1]
                    else:
                        # Fallback to player_comprehensive_stats
                        placeholder = '$1' if self.bot.config.database_type == 'postgresql' else '?'
                        result = await self.bot.db_adapter.fetch_one(
                            f"""
                            SELECT player_guid, player_name
                            FROM player_comprehensive_stats
                            WHERE LOWER(player_name) LIKE LOWER({placeholder})
                            GROUP BY player_guid, player_name
                            LIMIT 1
                        """,
                            (f"%{player_name}%",),
                        )
                        if not result:
                            await ctx.send(
                                f"❌ Player '{player_name}' not found."
                            )
                            return
                        player_guid = result[0]
                        primary_name = result[1]

                # === NOW WE HAVE player_guid AND primary_name - Get Stats ===

                # 🚀 TRY CACHE FIRST
                cache_key = f"stats_{player_guid}"
                cached_data = self.stats_cache.get(cache_key)

                if cached_data:
                    # Use cached stats
                    overall, weapon_overall, fav_weapons, recent = cached_data
                    logger.info(f"📦 Cache HIT: {primary_name}")
                else:
                    # Cache MISS - Query database
                    logger.info(f"💾 Cache MISS: {primary_name} - querying DB")

                    # Get overall stats
                    overall = await self.bot.db_adapter.fetch_one(
                        """
                        SELECT
                            COUNT(DISTINCT round_id) as total_games,
                            SUM(kills) as total_kills,
                            SUM(deaths) as total_deaths,
                            SUM(damage_given) as total_damage,
                            SUM(damage_received) as total_damage_received,
                            SUM(headshot_kills) as total_headshots,
                            CASE
                                WHEN SUM(time_played_seconds) > 0
                                THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                                ELSE 0
                            END as weighted_dpm,
                            AVG(kd_ratio) as avg_kd
                        FROM player_comprehensive_stats
                        WHERE player_guid = ?
                    """,
                        (player_guid,),
                    )

                    # Get weapon stats with accuracy
                    weapon_overall = await self.bot.db_adapter.fetch_one(
                        """
                        SELECT
                            SUM(w.hits) as total_hits,
                            SUM(w.shots) as total_shots,
                            SUM(w.headshots) as total_hs
                        FROM weapon_comprehensive_stats w
                        WHERE w.player_guid = ?
                    """,
                        (player_guid,),
                    )

                    # Get favorite weapons
                    fav_weapons = await self.bot.db_adapter.fetch_all(
                        """
                        SELECT weapon_name, SUM(kills) as total_kills
                        FROM weapon_comprehensive_stats
                        WHERE player_guid = ?
                        GROUP BY weapon_name
                        ORDER BY total_kills DESC
                        LIMIT 3
                    """,
                        (player_guid,),
                    )

                    # Get recent activity
                    recent = await self.bot.db_adapter.fetch_all(
                        """
                        SELECT s.round_date, s.map_name, p.kills, p.deaths
                        FROM player_comprehensive_stats p
                        JOIN rounds s ON p.round_id = s.id
                        WHERE p.player_guid = ?
                        ORDER BY s.round_date DESC
                        LIMIT 3
                    """,
                        (player_guid,),
                    )
                    
                    # 💾 STORE IN CACHE
                    self.stats_cache.set(
                        cache_key,
                        (overall, weapon_overall, fav_weapons, recent),
                    )
                    logger.info(f"💾 Cached stats for {primary_name}")

                    # Calculate stats
                    (
                        games,
                        kills,
                        deaths,
                        dmg,
                        dmg_recv,
                        hs,
                        avg_dpm,
                        avg_kd,
                    ) = overall
                    hits, shots, hs_weapon = (
                        weapon_overall if weapon_overall else (0, 0, 0)
                    )

                    # Handle None values from database
                    kills = kills or 0
                    deaths = deaths or 0
                    kd_ratio = kills / deaths if deaths > 0 else kills
                    accuracy = (hits / shots * 100) if shots > 0 else 0
                    hs_pct = (hs / hits * 100) if hits > 0 else 0

                    # Build embed
                    embed = discord.Embed(
                        title=f"📊 Stats for {primary_name}",
                        color=0x0099FF,
                        timestamp=datetime.now(),
                    )

                    embed.add_field(
                        name="🎮 Overview",
                        value=(
                            f"**Games Played:** {games:,}\n**K/D Ratio:** {kd_ratio:.2f}\n**Avg DPM:** {avg_dpm:.1f}"
                            if avg_dpm
                            else "0.0"
                        ),
                        inline=True,
                    )

                    embed.add_field(
                        name="⚔️ Combat",
                        value=f"**Kills:** {kills:,}\n**Deaths:** {deaths:,}\n**Headshots:** {hs:,} ({hs_pct:.1f}%)",
                        inline=True,
                    )

                    embed.add_field(
                        name="🎯 Accuracy",
                        value=f"**Overall:** {accuracy:.1f}%\n**Damage Given:** {dmg:,}\n**Damage Taken:** {dmg_recv:,}",
                        inline=True,
                    )

                    if fav_weapons:
                        weapons_text = "\n".join(
                            [
                                f"**{w[0].replace('WS_', '').title()}:** {w[1]:,} kills"
                                for w in fav_weapons
                            ]
                        )
                        embed.add_field(
                            name="🔫 Favorite Weapons",
                            value=weapons_text,
                            inline=False,
                        )

                    if recent:
                        recent_text = "\n".join(
                            [
                                f"`{r[0]}` **{r[1]}** - {r[2]}K/{r[3]}D"
                                for r in recent
                            ]
                        )
                        embed.add_field(
                            name="📅 Recent Matches",
                            value=recent_text,
                            inline=False,
                        )

                    # Get aliases for footer
                    aliases = await self.bot.db_adapter.fetch_all(
                        """
                        SELECT alias
                        FROM player_aliases
                        WHERE guid = ? AND LOWER(alias) != LOWER(?)
                        ORDER BY last_seen DESC, times_seen DESC
                        LIMIT 3
                    """,
                        (player_guid, primary_name),
                    )

                # Build footer with GUID and aliases
                footer_text = f"GUID: {player_guid}"
                if aliases:
                    alias_names = ", ".join([a[0] for a in aliases])
                    footer_text += f" | Also known as: {alias_names}"

                embed.set_footer(text=footer_text)
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in stats command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving stats: {e}")

    @commands.command(name="leaderboard", aliases=["lb", "top"])
    async def leaderboard(self, ctx, stat_type: str = "kills", page: int = 1):
        """🏆 Show players leaderboard with pagination

        Usage:
        - !lb              → First page (kills)
        - !lb 2            → Page 2 (kills)
        - !lb dpm          → First page (DPM)
        - !lb dpm 2        → Page 2 (DPM)

        Available stat types:
        - kills: Total kills
        - kd: Kill/Death ratio
        - dpm: Damage per minute
        - accuracy/acc: Overall accuracy
        - headshots/hs: Headshot percentage
        - games: Games played
        - revives: Most revives given (medic)
        - gibs: Most gibs (finishing moves)
        - objectives/obj: Most objectives completed
        - efficiency/eff: Highest efficiency rating
        - teamwork: Best teamwork (lowest team damage %)
        - multikills: Most multikills (doubles, triples, etc)
        - grenades/nades: Top grenadiers (grenade kills + accuracy)
        """
        try:
            # Handle case where user passes page number as first arg
            # e.g., !lb 2 should be interpreted as page 2 of kills
            if stat_type.isdigit():
                page = int(stat_type)
                stat_type = "kills"
            else:
                stat_type = stat_type.lower()

            # Ensure page is at least 1
            page = max(1, page)

            # 10 players per page
            players_per_page = 10
            offset = (page - 1) * players_per_page

            # Map aliases to stat types
            stat_aliases = {
                "k": "kills",
                "kill": "kills",
                "kd": "kd",
                "ratio": "kd",
                "dpm": "dpm",
                "damage": "dpm",
                "acc": "accuracy",
                "accuracy": "accuracy",
                "hs": "headshots",
                "headshot": "headshots",
                "headshots": "headshots",
                "games": "games",
                "played": "games",
                "revives": "revives",
                "revive": "revives",
                "medic": "revives",
                "gibs": "gibs",
                "gib": "gibs",
                "obj": "objectives",
                "objective": "objectives",
                "objectives": "objectives",
                "eff": "efficiency",
                "efficiency": "efficiency",
                "teamwork": "teamwork",
                "team": "teamwork",
                "multikill": "multikills",
                "multikills": "multikills",
                "multi": "multikills",
                "grenade": "grenades",
                "grenades": "grenades",
                "nades": "grenades",
                "nade": "grenades",
            }

            stat_type = stat_aliases.get(stat_type, "kills")

            # Get total count for pagination
            count_query = """
                SELECT COUNT(DISTINCT player_guid) 
                FROM player_comprehensive_stats
            """
            total_players = (await self.bot.db_adapter.fetch_one(count_query))[0]

            total_pages = (
                total_players + players_per_page - 1
            ) // players_per_page

            if stat_type == "kills":
                query = f"""
                    SELECT 
                        (SELECT player_name FROM player_comprehensive_stats 
                         WHERE player_guid = p.player_guid 
                         GROUP BY player_name 
                         ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                        SUM(p.kills) as total_kills,
                        SUM(p.deaths) as total_deaths,
                        COUNT(DISTINCT p.round_id) as games,
                        p.player_guid
                    FROM player_comprehensive_stats p
                    GROUP BY p.player_guid
                    HAVING games > 10
                    ORDER BY total_kills DESC
                    LIMIT {players_per_page} OFFSET {offset}
                """
                title = (
                    f"🏆 Top Players by Kills (Page {page}/{total_pages})"
                )

            elif stat_type == "kd":
                query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.kills) as total_kills,
                            SUM(p.deaths) as total_deaths,
                            COUNT(DISTINCT p.round_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 50 AND total_deaths > 0
                        ORDER BY (CAST(total_kills AS FLOAT) / total_deaths) DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                title = f"🏆 Top Players by K/D Ratio (Page {page}/{total_pages})"

            elif stat_type == "dpm":
                query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            CASE
                                WHEN SUM(p.time_played_seconds) > 0
                                THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                                ELSE 0
                            END as weighted_dpm,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.round_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 50
                        ORDER BY weighted_dpm DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                title = f"🏆 Top Players by DPM (Page {page}/{total_pages})"

            elif stat_type == "accuracy":
                query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(w.hits) as total_hits,
                            SUM(w.shots) as total_shots,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.round_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        JOIN weapon_comprehensive_stats w
                            ON p.round_id = w.round_id
                            AND p.player_guid = w.player_guid
                        GROUP BY p.player_guid
                        HAVING games > 50 AND total_shots > 1000
                        ORDER BY (CAST(total_hits AS FLOAT) / total_shots) DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                title = f"🏆 Top Players by Accuracy (Page {page}/{total_pages})"

            elif stat_type == "headshots":
                query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.headshot_kills) as total_hs,
                            SUM(w.hits) as total_hits,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.round_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        JOIN weapon_comprehensive_stats w
                            ON p.round_id = w.round_id
                            AND p.player_guid = w.player_guid
                        GROUP BY p.player_guid
                        HAVING games > 50 AND total_hits > 1000
                        ORDER BY (CAST(total_hs AS FLOAT) / total_hits) DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                title = f"🏆 Top Players by Headshot % (Page {page}/{total_pages})"

            elif stat_type == "games":
                query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            COUNT(DISTINCT p.round_id) as games,
                            SUM(p.kills) as total_kills,
                            SUM(p.deaths) as total_deaths,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        ORDER BY games DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                title = (
                        f"🏆 Most Active Players (Page {page}/{total_pages})"
                    )

            elif stat_type == "revives":
                query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.revives_given) as total_revives,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.round_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 10
                        ORDER BY total_revives DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                title = f"💉 Top Medics - Teammates Revived (Page {page}/{total_pages})"

            elif stat_type == "gibs":
                query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.gibs) as total_gibs,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.round_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 10
                        ORDER BY total_gibs DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                title = f"💀 Top Gibbers (Page {page}/{total_pages})"

            elif stat_type == "objectives":
                query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.objectives_completed + p.objectives_destroyed + p.objectives_stolen + p.objectives_returned) as total_obj,
                            SUM(p.objectives_completed) as completed,
                            COUNT(DISTINCT p.round_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 10
                        ORDER BY total_obj DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                title = (
                        f"🎯 Top Objective Players (Page {page}/{total_pages})"
                    )

            elif stat_type == "efficiency":
                query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            AVG(p.efficiency) as avg_eff,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.round_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 50
                        ORDER BY avg_eff DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                title = f"⚡ Highest Efficiency (Page {page}/{total_pages})"

            elif stat_type == "teamwork":
                query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.team_damage_given) as total_team_dmg,
                            SUM(p.damage_given) as total_dmg,
                            COUNT(DISTINCT p.round_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 50 AND total_dmg > 0
                        ORDER BY (CAST(total_team_dmg AS FLOAT) / total_dmg) ASC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                title = f"🤝 Best Teamwork (Lowest Team Damage %) (Page {page}/{total_pages})"

            elif stat_type == "multikills":
                query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.double_kills + p.triple_kills + p.quad_kills + p.multi_kills + p.mega_kills) as total_multi,
                            SUM(p.mega_kills) as megas,
                            COUNT(DISTINCT p.round_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 10
                        ORDER BY total_multi DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                title = f"🔥 Most Multikills (Page {page}/{total_pages})"

            elif stat_type == "grenades":
                query = f"""
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = w.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(w.kills) as total_kills,
                            SUM(w.shots) as total_throws,
                            SUM(w.hits) as total_hits,
                            CASE 
                                WHEN SUM(w.kills) > 0 
                                THEN ROUND(CAST(SUM(w.hits) AS FLOAT) / SUM(w.kills), 2)
                                ELSE 0 
                            END as aoe_ratio,
                            COUNT(DISTINCT w.round_id) as games,
                            w.player_guid
                        FROM weapon_comprehensive_stats w
                        WHERE w.weapon_name = 'WS_GRENADE'
                        GROUP BY w.player_guid
                        HAVING games > 10
                        ORDER BY total_kills DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                title = f"💣 Top Grenadiers - AOE Masters (Page {page}/{total_pages})"

            results = await self.bot.db_adapter.fetch_all(query)

            if not results:
                await ctx.send(
                    f"❌ No data found for leaderboard type: {stat_type}"
                )
                return

            # Build embed
            embed = discord.Embed(
                title=title,
                color=0xFFD700,
                timestamp=datetime.now(),  # Gold color
            )

            # Format results based on stat type
            leaderboard_text = ""
            medals = ["🥇", "🥈", "🥉"]

            for i, row in enumerate(results):
                # Calculate actual rank (based on page)
                rank = offset + i + 1

                # Use medal for top 3 overall, otherwise show rank number
                if rank <= 3:
                    medal = medals[rank - 1]
                else:
                    medal = f"{rank}."

                name = row[0]

                # Add dev badge for ciril (bot developer)
                player_guid = row[-1]  # GUID is always last column
                if player_guid == "E587CA5F":
                    name = f"{name} 👑"  # Crown emoji for dev

                if stat_type == "kills":
                    kills, deaths, games = row[1], row[2], row[3]
                    kd = kills / deaths if deaths > 0 else kills
                    leaderboard_text += f"{medal} **{name}** - {kills:,}K ({kd:.2f} K/D, {games} games)\n"

                elif stat_type == "kd":
                    kills, deaths, games = row[1], row[2], row[3]
                    kd = kills / deaths if deaths > 0 else kills
                    leaderboard_text += f"{medal} **{name}** - {kd:.2f} K/D ({kills:,}K/{deaths:,}D, {games} games)\n"

                elif stat_type == "dpm":
                    avg_dpm, kills, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {avg_dpm:.1f} DPM ({kills:,}K, {games} games)\n"

                elif stat_type == "accuracy":
                    hits, shots, kills, games = row[1], row[2], row[3], row[4]
                    acc = (hits / shots * 100) if shots > 0 else 0
                    leaderboard_text += f"{medal} **{name}** - {acc:.1f}% Acc ({kills:,}K, {games} games)\n"

                elif stat_type == "headshots":
                    hs, hits, kills, games = row[1], row[2], row[3], row[4]
                    hs_pct = (hs / hits * 100) if hits > 0 else 0
                    leaderboard_text += f"{medal} **{name}** - {hs_pct:.1f}% HS ({hs:,} HS, {games} games)\n"

                elif stat_type == "games":
                    games, kills, deaths = row[1], row[2], row[3]
                    kd = kills / deaths if deaths > 0 else kills
                    leaderboard_text += f"{medal} **{name}** - {games:,} games ({kills:,}K, {kd:.2f} K/D)\n"

                elif stat_type == "revives":
                    revives, kills, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {revives:,} teammates revived ({kills:,}K, {games} games)\n"

                elif stat_type == "gibs":
                    gibs, kills, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {gibs:,} gibs ({kills:,}K, {games} games)\n"

                elif stat_type == "objectives":
                    total_obj, completed, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {total_obj:,} objectives ({completed} completed, {games} games)\n"

                elif stat_type == "efficiency":
                    avg_eff, kills, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {avg_eff:.1f} efficiency ({kills:,}K, {games} games)\n"

                elif stat_type == "teamwork":
                    team_dmg, total_dmg, games = row[1], row[2], row[3]
                    team_pct = (
                        (team_dmg / total_dmg * 100) if total_dmg > 0 else 0
                    )
                    leaderboard_text += f"{medal} **{name}** - {team_pct:.2f}% team damage ({games} games)\n"

                elif stat_type == "multikills":
                    total_multi, megas, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {total_multi:,} multikills ({megas} mega, {games} games)\n"

                elif stat_type == "grenades":
                    kills, throws, hits, aoe_ratio, games = (
                        row[1],
                        row[2],
                        row[3],
                        row[4],
                        row[5],
                    )
                    accuracy = (hits / throws * 100) if throws > 0 else 0
                    aoe_emoji = "🔥" if aoe_ratio >= 3.0 else ""
                    leaderboard_text += f"{medal} **{name}** - {kills:,} kills • {accuracy:.1f}% acc • {aoe_ratio:.2f} AOE {aoe_emoji} ({games} games)\n"

                embed.description = leaderboard_text

            # Add usage footer with pagination info
            if page < total_pages:
                next_page_hint = f" | Next: !lb {stat_type} {page + 1}"
            else:
                next_page_hint = ""

            footer_text = f"💡 Use !lb [stat] [page]{next_page_hint}"
            embed.set_footer(text=footer_text)

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving leaderboard: {e}")


async def setup(bot):
    """Load the Leaderboard Cog"""
    await bot.add_cog(LeaderboardCog(bot))
    logger.info("✅ Leaderboard Cog loaded (stats, leaderboard)")
