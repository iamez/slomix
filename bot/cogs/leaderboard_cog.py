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

from bot.core.checks import is_public_channel
from bot.core.database_adapter import ensure_player_name_alias
from bot.core.lazy_pagination_view import LazyPaginationView
from bot.core.utils import escape_like_pattern_for_query, sanitize_error_message
from bot.stats import StatsCalculator
from bot.services.player_formatter import PlayerFormatter

logger = logging.getLogger(__name__)


class LeaderboardCog(commands.Cog, name="Leaderboard"):
    """Player statistics and rankings system"""

    def __init__(self, bot):
        self.bot = bot
        self.stats_cache = bot.stats_cache
        self.player_formatter = PlayerFormatter(bot.db_adapter)
        logger.info("🏆 LeaderboardCog initializing...")

    async def _enable_sql_diag(self):
        """Enable SQL diagnostics for troubleshooting (SQLite only)"""
        try:
            # PRAGMA is SQLite-specific
            if self.bot.config.database_type == 'sqlite':
                await self.bot.db_adapter.execute("PRAGMA case_sensitive_like = ON")
        except Exception:  # nosec B110
            pass  # PRAGMA is optional optimization

    @is_public_channel()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.command(name="stats")
    async def stats(self, ctx, *, player_name: str = None):
        """📊 Show detailed player statistics

        Usage:
        - !stats              → Your stats (if linked)
        - !stats playerName   → Search by name
        - !stats @user        → Stats for mentioned Discord user
        """
        logger.info(f"🔍 Stats command called by {ctx.author} | player_name='{player_name}' | mentions={ctx.message.mentions}")
        try:
            player_guid = None
            primary_name = None

            # Set up database alias and diagnostics
            try:
                await ensure_player_name_alias(self.bot.db_adapter, self.bot.config)
            except Exception:  # nosec B110
                pass  # Alias is optional
            # Enable SQL diagnostics for troubleshooting
            try:
                await self._enable_sql_diag()
            except Exception:  # nosec B110
                pass  # Diagnostics are optional
            
            # === SCENARIO 1: @MENTION - Look up linked Discord user ===
            if ctx.message.mentions:
                mentioned_user = ctx.message.mentions[0]
                mentioned_id = int(mentioned_user.id)  # Convert to int for PostgreSQL BIGINT

                link = await self.bot.db_adapter.fetch_one(
                    """
                    SELECT player_guid, player_name FROM player_links
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
                            "ET:Legacy account yet!"
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
                            "Admins can help link with:\n"
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
                # Skip to stats retrieval (don't process player_name as search term)

            # === SCENARIO 2: NO ARGS - Use author's linked account ===
            elif not player_name:
                discord_id = int(ctx.author.id)  # Convert to integer for PostgreSQL BIGINT
                query = """
                    SELECT player_guid, player_name FROM player_links
                    WHERE discord_id = $1
                """ if self.bot.config.database_type == 'postgresql' else """
                    SELECT player_guid, player_name FROM player_links
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
            elif player_name and not player_guid:
                # Try exact match in player_links first
                link = await self.bot.db_adapter.fetch_one(
                    """
                    SELECT player_guid, player_name FROM player_links
                    WHERE LOWER(player_name) = LOWER(?)
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
                        # Escape LIKE pattern to prevent injection
                        safe_pattern = escape_like_pattern_for_query(
                            player_name
                        )
                        result = await self.bot.db_adapter.fetch_one(
                            """
                            SELECT player_guid, player_name
                            FROM player_comprehensive_stats
                            WHERE LOWER(player_name) LIKE LOWER(?)
                                  ESCAPE '\\'
                            GROUP BY player_guid, player_name
                            LIMIT 1
                        """,
                            (safe_pattern,),
                        )
                        if not result:
                            await ctx.send(
                                f"❌ Player '{player_name}' not found."
                            )
                            return
                        player_guid = result[0]
                        primary_name = result[1]

            # === NOW WE HAVE player_guid AND primary_name - Get Stats ===
            if not player_guid:
                await ctx.send("❌ Could not find player stats.")
                return

            # 🚀 TRY CACHE FIRST
            cache_key = f"stats_{player_guid}"
            cached_data = self.stats_cache.get(cache_key)
            aliases = None  # Initialize to avoid UnboundLocalError

            if cached_data:
                # Use cached stats
                overall, weapon_overall, fav_weapons, recent = cached_data
                logger.info(f"📦 Cache HIT: {primary_name}")
            else:
                # Cache MISS - Query database
                logger.info(f"💾 Cache MISS: {primary_name} - querying DB")
                
                # Get overall stats (EXCLUDE R0 match summaries to prevent 33% inflation)
                overall = await self.bot.db_adapter.fetch_one(
                        """
                        SELECT
                            COUNT(DISTINCT p.round_id) as total_games,
                            SUM(p.kills) as total_kills,
                            SUM(p.deaths) as total_deaths,
                            SUM(p.damage_given) as total_damage,
                            SUM(p.damage_received) as total_damage_received,
                            SUM(p.headshot_kills) as total_headshots,
                            CASE
                                WHEN SUM(p.time_played_seconds) > 0
                                THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                                ELSE 0
                            END as weighted_dpm,
                            AVG(p.kd_ratio) as avg_kd
                        FROM player_comprehensive_stats p
                        JOIN rounds r ON p.round_id = r.id
                        WHERE p.player_guid = ? AND r.round_number IN (1, 2) AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                    """,
                        (player_guid,),
                    )

                    # Get weapon stats with accuracy (EXCLUDE R0 match summaries)
                weapon_overall = await self.bot.db_adapter.fetch_one(
                    """
                    SELECT
                        SUM(w.hits) as total_hits,
                        SUM(w.shots) as total_shots,
                        SUM(w.headshots) as total_hs
                    FROM weapon_comprehensive_stats w
                    JOIN rounds r ON w.round_id = r.id
                    WHERE w.player_guid = ? AND r.round_number IN (1, 2) AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                """,
                    (player_guid,),
                )

                # Get favorite weapons (EXCLUDE R0 match summaries)
                fav_weapons = await self.bot.db_adapter.fetch_all(
                    """
                    SELECT w.weapon_name, SUM(w.kills) as total_kills
                    FROM weapon_comprehensive_stats w
                    JOIN rounds r ON w.round_id = r.id
                    WHERE w.player_guid = ? AND r.round_number IN (1, 2) AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                    GROUP BY w.weapon_name
                    ORDER BY total_kills DESC
                    LIMIT 3
                """,
                    (player_guid,),
                )

                # Get recent activity (EXCLUDE R0 match summaries)
                recent = await self.bot.db_adapter.fetch_all(
                    """
                    SELECT s.round_date, s.map_name, p.kills, p.deaths
                    FROM player_comprehensive_stats p
                    JOIN rounds s ON p.round_id = s.id
                    WHERE p.player_guid = ? AND s.round_number IN (1, 2)
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

            # Calculate stats (runs for both cache HIT and MISS)
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
            kd_ratio = StatsCalculator.calculate_kd(kills, deaths)
            accuracy = StatsCalculator.calculate_accuracy(hits, shots)
            hs_pct = StatsCalculator.calculate_headshot_percentage(hs, hits)

            # Get formatted player name with badges and custom display name
            formatted_name = await self.player_formatter.format_player(
                player_guid,
                primary_name,
                include_badges=True
            )

            # Build embed with enhanced title
            embed = discord.Embed(
                title="📊 Player Statistics",
                description=f"**{formatted_name}**",
                color=0x5865F2,  # Discord Blurple
                timestamp=datetime.now(),
            )

            # Enhanced stat display with better formatting
            embed.add_field(
                name="🎮 Career Overview",
                value=(
                    f"**Rounds Played:** `{games:,}`\n"
                    f"**K/D Ratio:** `{kd_ratio:.2f}`\n"
                    f"**Avg DPM:** `{avg_dpm:.1f}`" if avg_dpm else "`0.0`"
                ),
                inline=True,
            )

            embed.add_field(
                name="⚔️ Combat Stats",
                value=(
                    f"**Kills:** `{kills:,}` 💀\n"
                    f"**Deaths:** `{deaths:,}` ☠️\n"
                    f"**Headshots:** `{hs:,}` ({hs_pct:.1f}%) 🎯"
                ),
                inline=True,
            )

            embed.add_field(
                name="🎯 Performance",
                value=(
                    f"**Accuracy:** `{accuracy:.1f}%`\n"
                    f"**Damage:** `{dmg:,}` ⬆️\n"
                    f"**Taken:** `{dmg_recv:,}` ⬇️"
                ),
                inline=True,
            )

            # Enhanced weapons display
            if fav_weapons:
                medals = ["🥇", "🥈", "🥉"]
                weapons_text = "\n".join(
                    [
                        f"{medals[i]} **{w[0].replace('WS_', '').replace('_', ' ').title()}** • `{w[1]:,} kills`"
                        for i, w in enumerate(fav_weapons)
                    ]
                )
                embed.add_field(
                    name="🔫 Top Weapons",
                    value=weapons_text,
                    inline=False,
                )

            # Enhanced recent matches display
            if recent:
                recent_text = "\n".join(
                    [
                        f"`{r[0][:10]}` • **{r[1][:20]}** • `{r[2]}K` / `{r[3]}D`"
                        for r in recent
                    ]
                )
                embed.add_field(
                    name="📅 Recent Activity",
                    value=recent_text,
                    inline=False,
                )

            # Get aliases for footer (always fresh, not cached)
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
            await ctx.send(f"❌ Error retrieving stats: {sanitize_error_message(e)}")

    @is_public_channel()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name="leaderboard", aliases=["lb", "top"])
    async def leaderboard(self, ctx, stat_type: str = "kills"):
        """🏆 Show players leaderboard with pagination

        Usage:
        - !lb              → First page (kills)
        - !lb dpm          → First page (DPM)
        - !lb accuracy     → First page (accuracy)

        Available stat types:
        - kills, kd, dpm, accuracy/acc, headshots/hs, games, 
        - revives, gibs, objectives/obj, efficiency/eff, teamwork,
        - multikills, grenades/nades

        Navigate using the arrow buttons below!
        """
        try:
            # Validate stat_type
            stat_type_lower = stat_type.lower()

            # Get total player count to calculate total pages
            count_query = """
                SELECT COUNT(DISTINCT player_guid) 
                FROM player_comprehensive_stats
            """
            total_count = await self.bot.db_adapter.fetch_one(count_query)
            if not total_count:
                await ctx.send("❌ No player data found")
                return
            
            total_players = total_count[0]
            total_pages = max(1, (total_players + 9) // 10)  # 10 per page

            # Create page fetcher - reuses existing leaderboard logic
            async def get_page(page_num: int) -> Optional[discord.Embed]:
                """Fetch a single leaderboard page
                
                Note: page_num is 0-indexed from LazyPaginationView
                """
                players_per_page = 10
                # Convert 0-indexed to 1-indexed for page display
                page_num = page_num + 1
                offset = (page_num - 1) * players_per_page

                # Map aliases
                stat_aliases = {
                    "k": "kills", "kill": "kills", "kd": "kd",
                    "ratio": "kd", "dpm": "dpm", "damage": "dpm",
                    "acc": "accuracy", "accuracy": "accuracy",
                    "hs": "headshots", "headshot": "headshots",
                    "headshots": "headshots", "games": "games",
                    "played": "games", "revives": "revives",
                    "revive": "revives", "medic": "revives",
                    "gibs": "gibs", "gib": "gibs",
                    "obj": "objectives", "objective": "objectives",
                    "objectives": "objectives", "ef": "efficiency",
                    "efficiency": "efficiency", "teamwork": "teamwork",
                    "team": "teamwork", "multikill": "multikills",
                    "multikills": "multikills", "multi": "multikills",
                    "grenade": "grenades", "grenades": "grenades",
                    "nades": "grenades", "nade": "grenades",
                }

                stat = stat_aliases.get(stat_type_lower, "kills")

                # Build appropriate query for this stat type
                # This is the existing logic from the original command
                query = None
                title = None

                if stat == "kills":
                    query = """
                        SELECT
                            MAX(p.player_name) as primary_name,
                            SUM(p.kills) as total_kills,
                            SUM(p.deaths) as total_deaths,
                            COUNT(DISTINCT p.round_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        JOIN rounds r ON p.round_id = r.id
                        WHERE r.round_number IN (1, 2) AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                        GROUP BY p.player_guid
                        HAVING COUNT(DISTINCT p.round_id) > 10
                        ORDER BY total_kills DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    """
                    title = f"🏆 Top Players by Kills (Page {page_num}/{total_pages})"

                elif stat == "kd":
                    query = """
                            SELECT
                                MAX(p.player_name) as primary_name,
                                SUM(p.kills) as total_kills,
                                SUM(p.deaths) as total_deaths,
                                COUNT(DISTINCT p.round_id) as games,
                                p.player_guid
                            FROM player_comprehensive_stats p
                            JOIN rounds r ON p.round_id = r.id
                            WHERE r.round_number IN (1, 2) AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                            GROUP BY p.player_guid
                            HAVING COUNT(DISTINCT p.round_id) > 50 AND SUM(p.deaths) > 0
                            ORDER BY (CAST(SUM(p.kills) AS FLOAT) / SUM(p.deaths)) DESC
                            LIMIT {players_per_page} OFFSET {offset}
                        """
                    title = f"🏆 Top Players by K/D Ratio (Page {page_num}/{total_pages})"

                elif stat == "dpm":
                    query = """
                            SELECT
                                MAX(p.player_name) as primary_name,
                                CASE
                                    WHEN SUM(p.time_played_seconds) > 0
                                    THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                                    ELSE 0
                                END as weighted_dpm,
                                SUM(p.kills) as total_kills,
                                COUNT(DISTINCT p.round_id) as games,
                                p.player_guid
                            FROM player_comprehensive_stats p
                            JOIN rounds r ON p.round_id = r.id
                            WHERE r.round_number IN (1, 2) AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                            GROUP BY p.player_guid
                            HAVING COUNT(DISTINCT p.round_id) > 50
                            ORDER BY weighted_dpm DESC
                            LIMIT {players_per_page} OFFSET {offset}
                        """
                    title = f"🏆 Top Players by DPM (Page {page_num}/{total_pages})"

                elif stat == "accuracy":
                    query = """
                            SELECT
                                MAX(p.player_name) as primary_name,
                                SUM(w.hits) as total_hits,
                                SUM(w.shots) as total_shots,
                                SUM(p.kills) as total_kills,
                                COUNT(DISTINCT p.round_id) as games,
                                p.player_guid
                            FROM player_comprehensive_stats p
                            JOIN rounds r ON p.round_id = r.id
                            JOIN weapon_comprehensive_stats w
                                ON p.round_id = w.round_id
                                AND p.player_guid = w.player_guid
                            WHERE r.round_number IN (1, 2) AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                            GROUP BY p.player_guid
                            HAVING COUNT(DISTINCT p.round_id) > 50 AND SUM(w.shots) > 1000
                            ORDER BY (CAST(SUM(w.hits) AS FLOAT) / SUM(w.shots)) DESC
                            LIMIT {players_per_page} OFFSET {offset}
                        """
                    title = f"🏆 Top Players by Accuracy (Page {page_num}/{total_pages})"

                elif stat == "headshots":
                    query = """
                            SELECT
                                MAX(p.player_name) as primary_name,
                                SUM(p.headshot_kills) as total_hs,
                                SUM(w.hits) as total_hits,
                                SUM(p.kills) as total_kills,
                                COUNT(DISTINCT p.round_id) as games,
                                p.player_guid
                            FROM player_comprehensive_stats p
                            JOIN rounds r ON p.round_id = r.id
                            JOIN weapon_comprehensive_stats w
                                ON p.round_id = w.round_id
                                AND p.player_guid = w.player_guid
                            WHERE r.round_number IN (1, 2) AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                            GROUP BY p.player_guid
                            HAVING COUNT(DISTINCT p.round_id) > 50 AND SUM(w.hits) > 1000
                            ORDER BY (CAST(SUM(p.headshot_kills) AS FLOAT) / SUM(w.hits)) DESC
                            LIMIT {players_per_page} OFFSET {offset}
                        """
                    title = f"🏆 Top Players by Headshot % (Page {page_num}/{total_pages})"

                elif stat == "games":
                    query = """
                            SELECT 
                                MAX(p.player_name) as primary_name,
                                COUNT(DISTINCT p.round_id) as games,
                                SUM(p.kills) as total_kills,
                                SUM(p.deaths) as total_deaths,
                                p.player_guid
                            FROM player_comprehensive_stats p
                            JOIN rounds r ON p.round_id = r.id
                            WHERE r.round_number IN (1, 2) AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                            GROUP BY p.player_guid
                            ORDER BY games DESC
                            LIMIT {players_per_page} OFFSET {offset}
                        """
                    title = f"🏆 Most Active Players (Page {page_num}/{total_pages})"

                elif stat == "revives":
                    query = """
                            SELECT 
                                MAX(p.player_name) as primary_name,
                                SUM(p.revives_given) as total_revives,
                                SUM(p.kills) as total_kills,
                                COUNT(DISTINCT p.round_id) as games,
                                p.player_guid
                            FROM player_comprehensive_stats p
                            JOIN rounds r ON p.round_id = r.id
                            WHERE r.round_number IN (1, 2) AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                            GROUP BY p.player_guid
                            HAVING COUNT(DISTINCT p.round_id) > 10
                            ORDER BY total_revives DESC
                            LIMIT {players_per_page} OFFSET {offset}
                        """
                    title = f"💉 Top Medics - Teammates Revived (Page {page_num}/{total_pages})"

                elif stat == "gibs":
                    query = """
                            SELECT 
                                MAX(p.player_name) as primary_name,
                                SUM(p.gibs) as total_gibs,
                                SUM(p.kills) as total_kills,
                                COUNT(DISTINCT p.round_id) as games,
                                p.player_guid
                            FROM player_comprehensive_stats p
                            JOIN rounds r ON p.round_id = r.id
                            WHERE r.round_number IN (1, 2) AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                            GROUP BY p.player_guid
                            HAVING COUNT(DISTINCT p.round_id) > 10
                            ORDER BY total_gibs DESC
                            LIMIT {players_per_page} OFFSET {offset}
                        """
                    title = f"💀 Top Gibbers (Page {page_num}/{total_pages})"

                elif stat == "objectives":
                    query = """
                            SELECT 
                                MAX(p.player_name) as primary_name,
                                SUM(p.objectives_completed + p.objectives_destroyed + p.objectives_stolen + p.objectives_returned) as total_obj,
                                SUM(p.objectives_completed) as completed,
                                COUNT(DISTINCT p.round_id) as games,
                                p.player_guid
                            FROM player_comprehensive_stats p
                            JOIN rounds r ON p.round_id = r.id
                            WHERE r.round_number IN (1, 2) AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                            GROUP BY p.player_guid
                            HAVING COUNT(DISTINCT p.round_id) > 10
                            ORDER BY total_obj DESC
                            LIMIT {players_per_page} OFFSET {offset}
                        """
                    title = f"🎯 Top Objective Players (Page {page_num}/{total_pages})"

                elif stat == "efficiency":
                    query = """
                            SELECT 
                                MAX(p.player_name) as primary_name,
                                AVG(p.efficiency) as avg_eff,
                                SUM(p.kills) as total_kills,
                                COUNT(DISTINCT p.round_id) as games,
                                p.player_guid
                            FROM player_comprehensive_stats p
                            JOIN rounds r ON p.round_id = r.id
                            WHERE r.round_number IN (1, 2) AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                            GROUP BY p.player_guid
                            HAVING COUNT(DISTINCT p.round_id) > 50
                            ORDER BY avg_eff DESC
                            LIMIT {players_per_page} OFFSET {offset}
                        """
                    title = f"⚡ Highest Efficiency (Page {page_num}/{total_pages})"

                elif stat == "teamwork":
                    query = """
                            SELECT
                                MAX(p.player_name) as primary_name,
                                SUM(p.team_damage_given) as total_team_dmg,
                                SUM(p.damage_given) as total_dmg,
                                COUNT(DISTINCT p.round_id) as games,
                                p.player_guid
                            FROM player_comprehensive_stats p
                            JOIN rounds r ON p.round_id = r.id
                            WHERE r.round_number IN (1, 2) AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                            GROUP BY p.player_guid
                            HAVING COUNT(DISTINCT p.round_id) > 50 AND SUM(p.damage_given) > 0
                            ORDER BY (CAST(SUM(p.team_damage_given) AS FLOAT) / SUM(p.damage_given)) ASC
                            LIMIT {players_per_page} OFFSET {offset}
                        """
                    title = (
                        "🤝 Best Teamwork (Lowest Team Damage %)"
                        f" (Page {page_num}/{total_pages})"
                    )

                elif stat == "multikills":
                    query = """
                            SELECT 
                                MAX(p.player_name) as primary_name,
                                SUM(p.double_kills + p.triple_kills + p.quad_kills + p.multi_kills + p.mega_kills) as total_multi,
                                SUM(p.mega_kills) as megas,
                                COUNT(DISTINCT p.round_id) as games,
                                p.player_guid
                            FROM player_comprehensive_stats p
                            JOIN rounds r ON p.round_id = r.id
                            WHERE r.round_number IN (1, 2) AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                            GROUP BY p.player_guid
                            HAVING COUNT(DISTINCT p.round_id) > 10
                            ORDER BY total_multi DESC
                            LIMIT {players_per_page} OFFSET {offset}
                        """
                    title = f"🔥 Most Multikills (Page {page_num}/{total_pages})"

                elif stat == "grenades":
                    query = """
                            SELECT
                                MAX(p.player_name) as primary_name,
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
                            JOIN rounds r ON w.round_id = r.id
                            WHERE w.weapon_name = 'WS_GRENADE'
                              AND r.round_number IN (1, 2) AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                            GROUP BY w.player_guid
                            HAVING COUNT(DISTINCT w.round_id) > 10
                            ORDER BY total_kills DESC
                            LIMIT {players_per_page} OFFSET {offset}
                        """
                    title = f"💣 Top Grenadiers - AOE Masters (Page {page_num}/{total_pages})"

                if not query:
                    return None

                # Format query with pagination values
                query = query.format(
                    players_per_page=players_per_page,
                    offset=offset
                )

                try:
                    results = await self.bot.db_adapter.fetch_all(query)
                except Exception as e:
                    logger.warning(f"Failed to fetch leaderboard page {page_num}: {e}")
                    return None

                if not results:
                    return None

                # Get formatted names with badges for all players on this page
                player_list = [(row[-1], row[0]) for row in results]  # (guid, name) tuples
                formatted_names = await self.player_formatter.format_players_batch(
                    player_list, include_badges=True
                )

                # Build embed
                embed = discord.Embed(
                    title=title,
                    color=0xFFD700,  # Gold
                    timestamp=datetime.now(),
                )

                # Format results based on stat type
                leaderboard_text = ""
                medals = ["🥇", "🥈", "🥉"]

                for i, row in enumerate(results):
                    rank = offset + i + 1
                    if rank <= 3:
                        medal = medals[rank - 1]
                    else:
                        medal = f"`#{rank}`"

                    player_guid = row[-1]
                    # Use formatted name with badges
                    name = formatted_names.get(player_guid, row[0])

                    if stat == "kills":
                        kills, deaths, games = row[1], row[2], row[3]
                        kd = StatsCalculator.calculate_kd(kills, deaths)
                        leaderboard_text += (
                            f"{medal} **{name}**\n"
                            f"   `{kills:,}` kills • `{kd:.2f}` K/D • `{games}` games\n"
                        )

                    elif stat == "kd":
                        kills, deaths, games = row[1], row[2], row[3]
                        kd = StatsCalculator.calculate_kd(kills, deaths)
                        leaderboard_text += (
                            f"{medal} **{name}**\n"
                            f"   `{kd:.2f}` K/D • `{kills:,}K`/`{deaths:,}D` • `{games}` games\n"
                        )

                    elif stat == "dpm":
                        avg_dpm, kills, games = row[1], row[2], row[3]
                        leaderboard_text += (
                            f"{medal} **{name}**\n"
                            f"   `{avg_dpm:.1f}` DPM • `{kills:,}` kills • `{games}` games\n"
                        )

                    elif stat == "accuracy":
                        hits, shots, kills, games = row[1], row[2], row[3], row[4]
                        acc = (hits / shots * 100) if shots > 0 else 0
                        leaderboard_text += (
                            f"{medal} **{name}**\n"
                            f"   `{acc:.1f}%` accuracy • `{kills:,}` kills • `{games}` games\n"
                        )

                    elif stat == "headshots":
                        hs, hits, kills, games = row[1], row[2], row[3], row[4]
                        hs_pct = (hs / hits * 100) if hits > 0 else 0
                        leaderboard_text += (
                            f"{medal} **{name}**\n"
                            f"   `{hs_pct:.1f}%` HS rate • `{hs:,}` headshots • `{games}` games\n"
                        )

                    elif stat == "games":
                        games, kills, deaths = row[1], row[2], row[3]
                        kd = kills / deaths if deaths > 0 else kills
                        leaderboard_text += (
                            f"{medal} **{name}**\n"
                            f"   `{games:,}` games • `{kills:,}` kills • `{kd:.2f}` K/D\n"
                        )

                    elif stat == "revives":
                        revives, kills, games = row[1], row[2], row[3]
                        leaderboard_text += (
                            f"{medal} **{name}** 🏥\n"
                            f"   `{revives:,}` revives • `{kills:,}` kills • `{games}` games\n"
                        )

                    elif stat == "gibs":
                        gibs, kills, games = row[1], row[2], row[3]
                        leaderboard_text += (
                            f"{medal} **{name}** 🦴\n"
                            f"   `{gibs:,}` gibs • `{kills:,}` kills • `{games}` games\n"
                        )

                    elif stat == "objectives":
                        total_obj, completed, games = row[1], row[2], row[3]
                        leaderboard_text += (
                            f"{medal} **{name}** 🎯\n"
                            f"   `{total_obj:,}` objectives • `{completed}` completed • `{games}` games\n"
                        )

                    elif stat == "efficiency":
                        avg_eff, kills, games = row[1], row[2], row[3]
                        leaderboard_text += (
                            f"{medal} **{name}**\n"
                            f"   `{avg_eff:.1f}` efficiency • `{kills:,}` kills • `{games}` games\n"
                        )

                    elif stat == "teamwork":
                        team_dmg, total_dmg, games = row[1], row[2], row[3]
                        team_pct = (
                            (team_dmg / total_dmg * 100)
                            if total_dmg > 0
                            else 0
                        )
                        leaderboard_text += (
                            f"{medal} **{name}** 🤝\n"
                            f"   `{team_pct:.2f}%` team damage • `{games}` games\n"
                        )

                    elif stat == "multikills":
                        total_multi, megas, games = row[1], row[2], row[3]
                        leaderboard_text += (
                            f"{medal} **{name}** 🔥\n"
                            f"   `{total_multi:,}` multikills • `{megas}` mega • `{games}` games\n"
                        )

                    elif stat == "grenades":
                        kills, throws, hits, aoe_ratio, games = (
                            row[1],
                            row[2],
                            row[3],
                            row[4],
                            row[5],
                        )
                        accuracy = (
                            (hits / throws * 100) if throws > 0 else 0
                        )
                        aoe_emoji = "🔥" if aoe_ratio >= 3.0 else "💣"
                        leaderboard_text += (
                            f"{medal} **{name}** {aoe_emoji}\n"
                            f"   `{kills:,}` kills • `{accuracy:.1f}%` acc • `{aoe_ratio:.2f}` AOE • `{games}` games\n"
                        )

                embed.description = leaderboard_text
                footer_text = "💡 Use !lb [stat] for different leaderboards"
                embed.set_footer(text=footer_text)

                return embed

            # Create view with lazy pagination
            view = LazyPaginationView(
                ctx,
                page_fetcher=get_page,
                total_pages=min(total_pages, 50),  # Cap at 50
            )

            # Get and send first page (0-indexed for LazyPaginationView)
            first_page = await get_page(0)
            if first_page:
                await ctx.send(embed=first_page, view=view)
            else:
                await ctx.send(
                    f"❌ No data found for leaderboard type: {stat_type}"
                )

        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving leaderboard: {sanitize_error_message(e)}")


async def setup(bot):
    """Load the Leaderboard Cog"""
    await bot.add_cog(LeaderboardCog(bot))
    logger.info("✅ Leaderboard Cog loaded (stats, leaderboard)")
