"""
🎮 Session Cog - Session Viewing Commands
Handles all session viewing and analytics commands for the Ultimate ET:Legacy Bot.

Commands:
- session: View specific session by date with multiple view modes
- last_session: View most recent session (moved to LastSessionCog)
- sessions: List all gaming sessions

This cog uses service-oriented architecture for session analytics:
- SessionDataService: Database queries
- SessionStatsAggregator: Statistical aggregations
- SessionEmbedBuilder: Discord embed creation
- SessionGraphGenerator: Performance graphs
- SessionViewHandlers: Different view modes
- PlayerBadgeService: Achievement badges
- PlayerDisplayNameService: Custom display names
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from bot.core.checks import is_public_channel
from bot.core.database_adapter import ensure_player_name_alias
from bot.core.utils import sanitize_error_message

# Import service layer
from bot.services.session_data_service import SessionDataService
from bot.services.session_stats_aggregator import SessionStatsAggregator
from bot.services.session_embed_builder import SessionEmbedBuilder
from bot.services.session_graph_generator import SessionGraphGenerator
from bot.services.session_view_handlers import SessionViewHandlers
from bot.services.player_badge_service import PlayerBadgeService
from bot.services.player_display_name_service import PlayerDisplayNameService
from bot.services.session_timing_shadow_service import SessionTimingShadowService

# Import shared utilities
from bot.stats import StatsCalculator

logger = logging.getLogger("UltimateBot.SessionCog")


def _split_chunks(text: str, max_len: int = 900):
    """Helper to split long text into Discord-safe chunks"""
    lines = text.splitlines(keepends=True)
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) > max_len:
            chunks.append(current.rstrip())
            current = line
        else:
            current += line
    if current:
        chunks.append(current.rstrip())
    return chunks


class SessionCog(commands.Cog, name="Session Commands"):
    """🎮 Session viewing and analytics commands with service architecture"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("🎮 SessionCog initializing with service architecture...")
        self.show_timing_dual = bool(getattr(bot.config, "show_timing_dual", False))
        if not hasattr(bot, "session_timing_shadow_service"):
            bot.session_timing_shadow_service = SessionTimingShadowService(bot.db_adapter)
        self.timing_shadow_service = bot.session_timing_shadow_service

        # Initialize all services (same as LastSessionCog)
        self.data_service = SessionDataService(bot.db_adapter, bot.db_path if hasattr(bot, 'db_path') else None)
        self.stats_aggregator = SessionStatsAggregator(bot.db_adapter)
        self.embed_builder = SessionEmbedBuilder(
            timing_shadow_service=self.timing_shadow_service,
            show_timing_dual=self.show_timing_dual,
        )
        self.graph_generator = SessionGraphGenerator(
            bot.db_adapter,
            timing_debug_service=getattr(bot, 'timing_debug_service', None),
            timing_shadow_service=self.timing_shadow_service,
            show_timing_dual=self.show_timing_dual,
        )
        self.view_handlers = SessionViewHandlers(
            bot.db_adapter,
            StatsCalculator,
            timing_shadow_service=self.timing_shadow_service,
            show_timing_dual=self.show_timing_dual,
        )
        self.badge_service = PlayerBadgeService(bot.db_adapter)
        self.display_name_service = PlayerDisplayNameService(bot.db_adapter)

        logger.info("✅ All services initialized successfully")

    @is_public_channel()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.command(name="session", aliases=["match", "game"])
    async def session(self, ctx, date_arg: str = None, subcommand: str = None):
        """📅 Show detailed session/match statistics for a specific date

        Displays comprehensive stats for all gaming sessions on the specified date.
        Supports multiple view modes for different perspectives.

        Usage:
        - !session 2025-11-15           → Overview (default view)
        - !session 2025-11-15 combat    → Combat stats
        - !session 2025-11-15 obj       → Objectives & support
        - !session 2025-11-15 weapons   → Weapon mastery
        - !session 2025-11-15 support   → Support activity
        - !session 2025-11-15 sprees    → Killing sprees
        - !session 2025-11-15 top       → Top 10 players (all players)
        - !session 2025-11-15 maps      → Per-map summaries
        - !session 2025-11-15 maps full → Round-by-round breakdown
        - !session 2025-11-15 graphs    → Performance graphs
        - !session                      → Show most recent session

        Date formats supported:
        - YYYY-MM-DD (e.g., 2025-11-15)
        - YYYY MM DD (e.g., 2025 11 15)
        - yesterday, today
        - More formats coming soon!
        """
        try:
            # Setup database aliases
            try:
                await ensure_player_name_alias(self.bot.db_adapter, self.bot.config)
            except Exception:  # nosec B110
                pass  # Alias is optional
            # Step 1: Parse and normalize the date
            target_date = None

            if date_arg:
                # Enhanced date parsing
                date_lower = date_arg.lower()

                if date_lower == "yesterday":
                    target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                elif date_lower == "today":
                    target_date = datetime.now().strftime("%Y-%m-%d")
                elif "-" in date_arg:
                    # Already in YYYY-MM-DD format
                    target_date = date_arg
                else:
                    # Try to parse as date components (will handle in future enhancement)
                    target_date = date_arg
            else:
                # No date provided - get the latest session date
                target_date = await self.data_service.get_latest_session_date()
                if not target_date:
                    await ctx.send("❌ No sessions found in database")
                    return

            logger.info(f"📅 Fetching session data for date: {target_date}")

            # Step 2: Fetch session data using the service
            sessions, session_ids, session_ids_str, player_count = await self.data_service.fetch_session_data_by_date(
                target_date
            )

            if not sessions:
                await ctx.send(f"❌ No sessions found for date: **{target_date}**\n💡 Use `!sessions` to see all available dates")
                return

            # Calculate total maps for display
            total_maps = len(sessions) // 2

            logger.info(f"✅ Found {len(sessions)} rounds ({total_maps} maps) with {player_count} players")

            # Step 3: Route to appropriate view based on subcommand
            if subcommand and subcommand.lower() in ("obj", "objectives"):
                await self.view_handlers.show_objectives_view(ctx, target_date, session_ids, session_ids_str, player_count)
                return

            if subcommand and subcommand.lower() in ("combat",):
                await self.view_handlers.show_combat_view(ctx, target_date, session_ids, session_ids_str, player_count)
                return

            if subcommand and subcommand.lower() in ("weapons", "weapon", "weap"):
                await self.view_handlers.show_weapons_view(ctx, target_date, session_ids, session_ids_str, player_count)
                return

            if subcommand and subcommand.lower() in ("support",):
                await self.view_handlers.show_support_view(ctx, target_date, session_ids, session_ids_str, player_count)
                return

            if subcommand and subcommand.lower() in ("sprees", "spree"):
                await self.view_handlers.show_sprees_view(ctx, target_date, session_ids, session_ids_str, player_count)
                return

            if subcommand and subcommand.lower() in ("top", "top10"):
                await self.view_handlers.show_top_view(ctx, target_date, session_ids, session_ids_str, player_count, total_maps)
                return

            # Maps view routing
            if subcommand and subcommand.lower() == "maps":
                # Check for "full" subcommand
                # For "!session 2025-01-20 maps full": parts[0]=!session, [1]=date, [2]=maps, [3]=full
                parts = ctx.message.content.split()
                if len(parts) > 3 and parts[3].lower() == "full":
                    await self.view_handlers.show_maps_full_view(ctx, target_date, sessions, session_ids, session_ids_str, player_count)
                else:
                    await self.view_handlers.show_maps_view(ctx, target_date, sessions, session_ids, session_ids_str, player_count)
                return

            # Graphs view (handled by SessionGraphGenerator)
            if subcommand and subcommand.lower() in ("graphs", "graph"):
                result = await self.graph_generator.generate_performance_graphs(
                    target_date, session_ids, session_ids_str
                )
                offense_img, defense_img, metrics_img, playstyle_img, timeline_img = result

                if offense_img and defense_img and metrics_img and playstyle_img:
                    # Image 1: Combat Stats (Offense)
                    file1 = discord.File(
                        offense_img,
                        filename=f"session_{target_date}_offense.png"
                    )
                    embed1 = discord.Embed(
                        title=f"COMBAT STATS (OFFENSE)  -  {target_date}",
                        description=f"Kills/Deaths, Damage, K/D, DPM - Top players across {total_maps} maps",
                        color=0x5865F2,
                        timestamp=datetime.now()
                    )
                    embed1.set_image(
                        url=f"attachment://session_{target_date}_offense.png"
                    )
                    await ctx.send(embed=embed1, file=file1)

                    # Image 2: Combat Stats (Defense/Support)
                    file2 = discord.File(
                        defense_img,
                        filename=f"session_{target_date}_defense.png"
                    )
                    embed2 = discord.Embed(
                        title=f"COMBAT STATS (DEFENSE/SUPPORT)  -  {target_date}",
                        description="Revives, Time Alive/Dead, Gibs, Headshots",
                        color=0x57F287,
                        timestamp=datetime.now()
                    )
                    embed2.set_image(
                        url=f"attachment://session_{target_date}_defense.png"
                    )
                    await ctx.send(embed=embed2, file=file2)

                    # Image 3: Advanced Metrics
                    file3 = discord.File(
                        metrics_img,
                        filename=f"session_{target_date}_metrics.png"
                    )
                    embed3 = discord.Embed(
                        title=f"ADVANCED METRICS  -  {target_date}",
                        description="FragPotential, Damage Efficiency, Denied Playtime, Survival Rate, Useful Kills, Self Kills, Full Selfkills",
                        color=0xE74C3C,
                        timestamp=datetime.now()
                    )
                    embed3.set_image(
                        url=f"attachment://session_{target_date}_metrics.png"
                    )
                    await ctx.send(embed=embed3, file=file3)

                    # Image 4: Playstyle Analysis
                    file4 = discord.File(
                        playstyle_img,
                        filename=f"session_{target_date}_playstyle.png"
                    )
                    embed4 = discord.Embed(
                        title=f"PLAYSTYLE ANALYSIS  -  {target_date}",
                        description="Player playstyles based on combat metrics",
                        color=0x9B59B6,
                        timestamp=datetime.now()
                    )
                    embed4.set_image(
                        url=f"attachment://session_{target_date}_playstyle.png"
                    )
                    await ctx.send(embed=embed4, file=file4)

                    # Image 5: Performance Timeline (optional)
                    if timeline_img:
                        file5 = discord.File(
                            timeline_img,
                            filename=f"session_{target_date}_timeline.png"
                        )
                        embed5 = discord.Embed(
                            title=f"DPM TIMELINE  -  {target_date}",
                            description="DPM evolution across rounds - Performance trends",
                            color=0xF39C12,
                            timestamp=datetime.now()
                        )
                        embed5.set_image(
                            url=f"attachment://session_{target_date}_timeline.png"
                        )
                        await ctx.send(embed=embed5, file=file5)
                else:
                    await ctx.send(
                        "Could not generate performance graphs for this session"
                    )
                return

            # Step 4: Default view - Overview (improved version of original)
            # Build overview embed using the new data
            embed = discord.Embed(
                title=f"📊 Session Summary: {target_date}",
                description=f"**{total_maps} maps** • **{len(sessions)} rounds** • **{player_count} players**",
                color=0x00FF88,
            )

            # Get unique maps played
            maps_set = set()
            for session in sessions:
                maps_set.add(session[1])  # map_name is at index 1
            maps_list = sorted(list(maps_set))

            # Add maps played
            maps_text = ", ".join(maps_list)
            if len(maps_text) > 900:
                maps_text = ", ".join(maps_list[:8]) + f" (+{len(maps_list) - 8} more)"
            embed.add_field(
                name="🗺️ Maps Played", value=maps_text, inline=False
            )

            # Get top players with badges and display names
            top_players_query = f"""
                SELECT
                    p.player_guid,
                    p.player_name,
                    SUM(p.kills) as kills,
                    SUM(p.deaths) as deaths,
                    SUM(p.damage_given) as damage,
                    SUM(p.time_played_seconds) as playtime
                FROM player_comprehensive_stats p
                WHERE p.round_id IN ({session_ids_str})
                GROUP BY p.player_guid, p.player_name
                ORDER BY kills DESC
                LIMIT 10
            """
            top_players = await self.bot.db_adapter.fetch_all(top_players_query, tuple(session_ids))

            # Add all players (not just top 5!)
            if top_players:
                # Batch fetch badges and display names to avoid N+1 queries
                player_guids = [row[0] for row in top_players]
                badges_dict = await self.badge_service.get_player_badges_batch(player_guids)
                names_dict = await self.display_name_service.get_display_names_batch(player_guids)

                player_text = ""
                medals = ["🥇", "🥈", "🥉"] + [f"{i}." for i in range(4, 11)]

                for i, row in enumerate(top_players):
                    guid, name, kills, deaths, damage, playtime = row

                    # Get badge and display name from batch dictionaries
                    badge = badges_dict.get(guid, '')
                    display_name = names_dict.get(guid, name)  # Fallback to query name if not found

                    kd = StatsCalculator.calculate_kd(kills, deaths)
                    dpm = (damage * 60.0 / playtime) if playtime > 0 else 0

                    player_text += f"{medals[i]} {badge} **{display_name}** • {kills}K/{deaths}D ({kd:.2f}) • {dpm:.0f} DPM\n"

                embed.add_field(
                    name=f"🏆 Top {len(top_players)} Players", value=player_text, inline=False
                )

            # Add helpful footer with available views
            embed.set_footer(
                text="💡 Try: combat | obj | weapons | support | sprees | top | maps | graphs"
            )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in session command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving session: {sanitize_error_message(e)}")

    # NOTE: !last_session command has been moved to Last Round Cog
    # See bot/cogs/last_session_cog.py for the full implementation
    # This stub has been removed to avoid command conflicts

    @is_public_channel()
    @commands.command(name="rounds", aliases=["sessions", "list_sessions", "ls"])
    async def list_sessions(self, ctx, *, month: str = None):
        """📅 List all gaming sessions, optionally filtered by month

        Usage:
        - !sessions              → List all sessions (last 20)
        - !sessions 10           → List sessions from October (current year)
        - !sessions 2025-10      → List sessions from October 2025
        - !sessions october      → List sessions from October (current year)
        - !sessions oct          → Same as above
        """
        try:
            # Build query based on month filter
            if month:
                # Handle different month formats
                month_lower = month.strip().lower()
                month_names = {
                    "january": "01",
                    "jan": "01",
                    "february": "02",
                    "feb": "02",
                    "march": "03",
                    "mar": "03",
                    "april": "04",
                    "apr": "04",
                    "may": "05",
                    "june": "06",
                    "jun": "06",
                    "july": "07",
                    "jul": "07",
                    "august": "08",
                    "aug": "08",
                    "september": "09",
                    "sep": "09",
                    "october": "10",
                    "oct": "10",
                    "november": "11",
                    "nov": "11",
                    "december": "12",
                    "dec": "12",
                }

                if month_lower in month_names:
                    # Month name provided - use current year
                    from datetime import datetime

                    current_year = datetime.now().year
                    month_filter = f"{current_year}-{month_names[month_lower]}"
                elif "-" in month:
                    # Full YYYY-MM format
                    month_filter = month
                elif month.isdigit() and len(month) <= 2:
                    # Just month number - use current year
                    from datetime import datetime

                    current_year = datetime.now().year
                    month_filter = f"{current_year}-{int(month):02d}"
                else:
                    await ctx.send(
                        f"❌ Invalid month format: `{month}`\nUse: `!sessions 10` or `!sessions october`"
                    )
                    return

                # Query by gaming_session_id to properly show individual sessions
                if self.bot.config.database_type == 'sqlite':
                    query = """
                        SELECT
                            r.gaming_session_id,
                            SUBSTR(r.round_date, 1, 10) as date,
                            MIN(r.round_date || ' ' || r.round_time) as session_start,
                            MAX(r.round_date || ' ' || r.round_time) as session_end,
                            COUNT(DISTINCT CASE WHEN r.round_number IN (1, 2) THEN r.id END) / 2 as maps,
                            COUNT(DISTINCT CASE WHEN r.round_number IN (1, 2) THEN r.id END) as rounds,
                            (SELECT COUNT(DISTINCT p.player_guid)
                             FROM player_comprehensive_stats p
                             WHERE p.round_id IN (
                                SELECT id FROM rounds WHERE gaming_session_id = r.gaming_session_id
                             )) as players
                        FROM rounds r
                        WHERE r.gaming_session_id IS NOT NULL
                          AND SUBSTR(r.round_date, 1, 7) = ?
                        GROUP BY r.gaming_session_id, SUBSTR(r.round_date, 1, 10)
                        ORDER BY r.gaming_session_id DESC
                    """
                    sessions = await self.bot.db_adapter.fetch_all(query, (month_filter,))
                else:  # PostgreSQL
                    query = """
                        SELECT
                            r.gaming_session_id,
                            SUBSTR(r.round_date, 1, 10) as date,
                            MIN(r.round_date || ' ' || r.round_time) as session_start,
                            MAX(r.round_date || ' ' || r.round_time) as session_end,
                            COUNT(DISTINCT CASE WHEN r.round_number IN (1, 2) THEN r.id END) / 2 as maps,
                            COUNT(DISTINCT CASE WHEN r.round_number IN (1, 2) THEN r.id END) as rounds,
                            (SELECT COUNT(DISTINCT p.player_guid)
                             FROM player_comprehensive_stats p
                             WHERE p.round_id IN (
                                SELECT id FROM rounds WHERE gaming_session_id = r.gaming_session_id
                             )) as players
                        FROM rounds r
                        WHERE r.gaming_session_id IS NOT NULL
                          AND r.round_date LIKE ?
                        GROUP BY r.gaming_session_id, SUBSTR(r.round_date, 1, 10)
                        ORDER BY r.gaming_session_id DESC
                    """
                    sessions = await self.bot.db_adapter.fetch_all(query, (f"{month_filter}%",))
                filter_text = month_filter
            else:
                # Query by gaming_session_id to properly show individual sessions
                if self.bot.config.database_type == 'sqlite':
                    query = """
                        SELECT
                            r.gaming_session_id,
                            SUBSTR(r.round_date, 1, 10) as date,
                            MIN(r.round_date || ' ' || r.round_time) as session_start,
                            MAX(r.round_date || ' ' || r.round_time) as session_end,
                            COUNT(DISTINCT CASE WHEN r.round_number IN (1, 2) THEN r.id END) / 2 as maps,
                            COUNT(DISTINCT CASE WHEN r.round_number IN (1, 2) THEN r.id END) as rounds,
                            (SELECT COUNT(DISTINCT p.player_guid)
                             FROM player_comprehensive_stats p
                             WHERE p.round_id IN (
                                SELECT id FROM rounds WHERE gaming_session_id = r.gaming_session_id
                             )) as players
                        FROM rounds r
                        WHERE r.gaming_session_id IS NOT NULL
                        GROUP BY r.gaming_session_id, SUBSTR(r.round_date, 1, 10)
                        ORDER BY r.gaming_session_id DESC
                        LIMIT 20
                    """
                    sessions = await self.bot.db_adapter.fetch_all(query)
                else:  # PostgreSQL
                    query = """
                        SELECT
                            r.gaming_session_id,
                            SUBSTR(r.round_date, 1, 10) as date,
                            MIN(r.round_date || ' ' || r.round_time) as session_start,
                            MAX(r.round_date || ' ' || r.round_time) as session_end,
                            COUNT(DISTINCT CASE WHEN r.round_number IN (1, 2) THEN r.id END) / 2 as maps,
                            COUNT(DISTINCT CASE WHEN r.round_number IN (1, 2) THEN r.id END) as rounds,
                            (SELECT COUNT(DISTINCT p.player_guid)
                             FROM player_comprehensive_stats p
                             WHERE p.round_id IN (
                                SELECT id FROM rounds WHERE gaming_session_id = r.gaming_session_id
                             )) as players
                        FROM rounds r
                        WHERE r.gaming_session_id IS NOT NULL
                        GROUP BY r.gaming_session_id, SUBSTR(r.round_date, 1, 10)
                        ORDER BY r.gaming_session_id DESC
                        LIMIT 20
                    """
                    sessions = await self.bot.db_adapter.fetch_all(query)
                filter_text = "all time (last 20)"

            if not sessions:
                await ctx.send(f"❌ No rounds found for {filter_text}")
                return

            # Create embed
            embed = discord.Embed(
                title="📅 Gaming Sessions",
                description=f"Showing sessions from **{filter_text}**",
                color=discord.Color.blue(),
            )

            session_list = []
            # Track sessions per date to number them
            date_session_counts = {}

            for row in sessions:
                # Handle both dict (PostgreSQL) and tuple (SQLite) results
                if isinstance(row, dict):
                    session_id = row['gaming_session_id']
                    date = row['date']
                    maps = row['maps']
                    rounds = row['rounds']
                    players = row['players']
                    session_start = row['session_start']
                    session_end = row['session_end']
                else:
                    session_id, date, session_start, session_end, maps, rounds, players = row

                # Count sessions per date for labeling
                if date not in date_session_counts:
                    date_session_counts[date] = 0
                date_session_counts[date] += 1

                # Calculate duration
                try:
                    start_dt = datetime.fromisoformat(
                        session_start.replace("Z", "+00:00") if "Z" in session_start else session_start
                    )
                    end_dt = datetime.fromisoformat(
                        session_end.replace("Z", "+00:00") if "Z" in session_end else session_end
                    )
                    duration = end_dt - start_dt
                    hours = duration.total_seconds() / 3600
                    duration_str = f"{hours:.1f}h"

                    # Extract start time for display
                    start_time = start_dt.strftime("%H:%M")
                    end_time = end_dt.strftime("%H:%M")
                    time_range = f"{start_time}-{end_time}"
                except Exception:
                    duration_str = "N/A"
                    time_range = ""

                # Format session display
                session_label = f"**{date}** (Session #{session_id})"
                if time_range:
                    session_label += f" {time_range}"

                session_list.append(
                    f"{session_label}\n"
                    f"└ {int(maps)} maps • {rounds} rounds • {players} players • {duration_str}"
                )

            # Split into chunks if too long
            chunk_size = 10
            for i in range(0, len(session_list), chunk_size):
                chunk = session_list[i : i + chunk_size]
                embed.add_field(
                    name=f"Sessions {i+1}-{min(i+chunk_size, len(session_list))}",
                    value="\n\n".join(chunk),
                    inline=False,
                )

            embed.set_footer(
                text=f"Total: {len(sessions)} sessions • Use !last_session or !session YYYY-MM-DD for details"
            )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in list_sessions command: {e}", exc_info=True)
            await ctx.send(f"❌ Error listing sessions: {sanitize_error_message(e)}")


async def setup(bot):
    """Load the Session Cog"""
    await bot.add_cog(SessionCog(bot))
