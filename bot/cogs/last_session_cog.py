"""
Last Round Cog - Refactored with service-oriented architecture

This cog handles the !last_session command by delegating to specialized services:
- SessionDataService: Database queries for session data
- SessionStatsAggregator: Statistical aggregations
- SessionEmbedBuilder: Discord embed creation
- SessionGraphGenerator: Performance graph generation
- SessionViewHandlers: Different view modes (obj, combat, weapons, etc.)
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import discord
from discord.ext import commands

from bot.core.checks import is_public_channel
from bot.core.database_adapter import ensure_player_name_alias
from bot.core.utils import sanitize_error_message
from tools.stopwatch_scoring import StopwatchScoring
from bot.stats import StatsCalculator
from bot.services.session_data_service import SessionDataService
from bot.services.session_stats_aggregator import SessionStatsAggregator
from bot.services.session_embed_builder import SessionEmbedBuilder
from bot.services.session_graph_generator import SessionGraphGenerator
from bot.services.session_view_handlers import SessionViewHandlers
from bot.services.player_badge_service import PlayerBadgeService
from bot.services.player_display_name_service import PlayerDisplayNameService
from bot.services.endstats_aggregator import EndstatsAggregator

logger = logging.getLogger("bot.cogs.last_session")


class LastSessionCog(commands.Cog):
    """🎮 Comprehensive last session analytics with multiple view modes"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("🎮 LastSessionCog initializing with service architecture...")

        # Initialize services
        self.data_service = SessionDataService(bot.db_adapter, bot.db_path if hasattr(bot, 'db_path') else None)
        self.stats_aggregator = SessionStatsAggregator(bot.db_adapter)
        self.embed_builder = SessionEmbedBuilder()
        self.graph_generator = SessionGraphGenerator(bot.db_adapter)
        self.view_handlers = SessionViewHandlers(bot.db_adapter, StatsCalculator)
        self.badge_service = PlayerBadgeService(bot.db_adapter)
        self.display_name_service = PlayerDisplayNameService(bot.db_adapter)
        self.endstats_aggregator = EndstatsAggregator(bot.db_adapter)

        logger.info("✅ All services initialized successfully")

    @is_public_channel()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.command(name="last_session", aliases=["last", "latest", "recent", "last_round"])
    async def last_session(self, ctx, subcommand: str = None):
        """🎮 Show the most recent session/match

        Displays detailed stats for the latest played session (full day).
        A session = one day of gaming with all maps/rounds.

        Subcommands:
        - !last_session          → Clean view with essential stats
        - !last_session top      → Top 10 players
        - !last_session combat   → Combat stats
        - !last_session obj      → Objectives & support
        - !last_session weapons  → Weapon mastery
        - !last_session support  → Support activity
        - !last_session sprees   → Killing sprees
        - !last_session maps     → Per-map summaries (popular stats)
        - !last_session maps full → Round-by-round breakdown
        - !last_session graphs   → Performance graphs
        """
        try:
            # Setup database aliases
            try:
                await ensure_player_name_alias(self.bot.db_adapter, self.bot.config)
            except Exception:  # nosec B110
                pass  # Alias is optional, continue without it

            # Phase 1: Get session data
            latest_date = await self.data_service.get_latest_session_date()
            if not latest_date:
                await ctx.send("❌ No rounds found in database")
                return

            sessions, session_ids, session_ids_str, player_count = await self.data_service.fetch_session_data(
                latest_date
            )
            if not sessions:
                await ctx.send("❌ No rounds found for latest date")
                return

            # Calculate total maps for top view
            total_maps = len(sessions) // 2

            # Route to appropriate view based on subcommand
            if subcommand and subcommand.lower() in ("obj", "objectives"):
                await self.view_handlers.show_objectives_view(ctx, latest_date, session_ids, session_ids_str, player_count)
                return

            if subcommand and subcommand.lower() in ("combat",):
                await self.view_handlers.show_combat_view(ctx, latest_date, session_ids, session_ids_str, player_count)
                return

            if subcommand and subcommand.lower() in ("weapons", "weapon", "weap"):
                await self.view_handlers.show_weapons_view(ctx, latest_date, session_ids, session_ids_str, player_count)
                return

            if subcommand and subcommand.lower() in ("support",):
                await self.view_handlers.show_support_view(ctx, latest_date, session_ids, session_ids_str, player_count)
                return

            if subcommand and subcommand.lower() in ("sprees", "spree"):
                await self.view_handlers.show_sprees_view(ctx, latest_date, session_ids, session_ids_str, player_count)
                return

            if subcommand and subcommand.lower() in ("top", "top10"):
                await self.view_handlers.show_top_view(ctx, latest_date, session_ids, session_ids_str, player_count, total_maps)
                return

            if subcommand and subcommand.lower() in ("graphs", "graph", "charts"):
                # Generate performance graphs (returns 5 images)
                result = await self.graph_generator.generate_performance_graphs(
                    latest_date, session_ids, session_ids_str
                )
                offense_img, defense_img, metrics_img, playstyle_img, timeline_img = result

                if offense_img and defense_img and metrics_img and playstyle_img:
                    # Image 1: Combat Stats (Offense)
                    file1 = discord.File(
                        offense_img,
                        filename=f"session_{latest_date}_offense.png"
                    )
                    embed1 = discord.Embed(
                        title=f"COMBAT STATS (OFFENSE)  -  {latest_date}",
                        description=f"Kills/Deaths, Damage, K/D, DPM - Top players across {total_maps} maps",
                        color=0x5865F2,
                        timestamp=datetime.now()
                    )
                    embed1.set_image(
                        url=f"attachment://session_{latest_date}_offense.png"
                    )
                    await ctx.send(embed=embed1, file=file1)

                    # Image 2: Combat Stats (Defense/Support)
                    file2 = discord.File(
                        defense_img,
                        filename=f"session_{latest_date}_defense.png"
                    )
                    embed2 = discord.Embed(
                        title=f"COMBAT STATS (DEFENSE/SUPPORT)  -  {latest_date}",
                        description="Revives, Time Alive/Dead, Gibs, Headshots",
                        color=0x57F287,
                        timestamp=datetime.now()
                    )
                    embed2.set_image(
                        url=f"attachment://session_{latest_date}_defense.png"
                    )
                    await ctx.send(embed=embed2, file=file2)

                    # Image 3: Advanced Metrics
                    file3 = discord.File(
                        metrics_img,
                        filename=f"session_{latest_date}_metrics.png"
                    )
                    embed3 = discord.Embed(
                        title=f"ADVANCED METRICS  -  {latest_date}",
                        description="FragPotential, Damage Efficiency, Denied Playtime, Survival Rate",
                        color=0xE74C3C,
                        timestamp=datetime.now()
                    )
                    embed3.set_image(
                        url=f"attachment://session_{latest_date}_metrics.png"
                    )
                    await ctx.send(embed=embed3, file=file3)

                    # Image 4: Playstyle Analysis
                    file4 = discord.File(
                        playstyle_img,
                        filename=f"session_{latest_date}_playstyle.png"
                    )
                    embed4 = discord.Embed(
                        title=f"PLAYSTYLE ANALYSIS  -  {latest_date}",
                        description="Player playstyles based on combat metrics",
                        color=0x9B59B6,
                        timestamp=datetime.now()
                    )
                    embed4.set_image(
                        url=f"attachment://session_{latest_date}_playstyle.png"
                    )
                    await ctx.send(embed=embed4, file=file4)

                    # Image 5: Performance Timeline (the favorite!)
                    if timeline_img:
                        file5 = discord.File(
                            timeline_img,
                            filename=f"session_{latest_date}_timeline.png"
                        )
                        embed5 = discord.Embed(
                            title=f"DPM TIMELINE  -  {latest_date}",
                            description="DPM evolution across rounds - Performance trends",
                            color=0xF39C12,
                            timestamp=datetime.now()
                        )
                        embed5.set_image(
                            url=f"attachment://session_{latest_date}_timeline.png"
                        )
                        await ctx.send(embed=embed5, file=file5)
                else:
                    await ctx.send(
                        "Could not generate performance graphs for this session"
                    )
                return

            # Maps view routing
            if subcommand and subcommand.lower() == "maps":
                # Check for "full" subcommand
                parts = ctx.message.content.split()
                if len(parts) > 2 and parts[2].lower() == "full":
                    await self.view_handlers.show_maps_full_view(ctx, latest_date, sessions, session_ids, session_ids_str, player_count)
                else:
                    await self.view_handlers.show_maps_view(ctx, latest_date, sessions, session_ids, session_ids_str, player_count)
                return

            # ═══════════════════════════════════════════════════════════════════════
            # DEFAULT COMPREHENSIVE VIEW - Full session analytics
            # ═══════════════════════════════════════════════════════════════════════

            # Phase 2: Get hardcoded teams and team scores
            hardcoded_teams = await self.data_service.get_hardcoded_teams(session_ids)
            team_1_name, team_2_name, team_1_score, team_2_score, scoring_result = await self.data_service.calculate_team_scores(session_ids)

            # Get team mappings FIRST (needed for proper team stats aggregation)
            team_1_name_mapped, team_2_name_mapped, team_1_players_list, team_2_players_list, name_to_team = await self.data_service.build_team_mappings(
                session_ids, session_ids_str, hardcoded_teams
            )

            # Use mapped team names if available
            if team_1_name_mapped and team_2_name_mapped:
                team_1_name = team_1_name_mapped
                team_2_name = team_2_name_mapped

            # Phase 3: Aggregate all data (now with correct team mappings)
            all_players = await self.stats_aggregator.aggregate_all_player_stats(session_ids, session_ids_str)
            team_stats = await self.stats_aggregator.aggregate_team_stats(session_ids, session_ids_str, hardcoded_teams, name_to_team)

            # Phase 3.5: Aggregate endstats (awards and VS stats)
            endstats_data = {'has_data': False}
            try:
                endstats_data = await self.endstats_aggregator.aggregate_session_endstats(
                    session_ids, session_ids_str
                )
            except Exception as e:
                logger.warning(f"Could not fetch endstats: {e}")
                # Continue without endstats - non-critical

            team_1_mvp_stats, team_2_mvp_stats = await self.data_service.get_team_mvps(
                session_ids, session_ids_str, hardcoded_teams, team_1_name, team_2_name
            )

            # Calculate maps info
            rounds_played = len(sessions)
            unique_maps = len(set(s[1] for s in sessions))

            # Build maps played string - each map played ONCE even if it has R1+R2
            # Count how many times each unique map appears (considering both rounds as 1 play)
            map_matches = {}  # Track unique map matches
            for round_id, map_name, round_num, actual_time in sessions:
                if map_name not in map_matches:
                    map_matches[map_name] = []
                map_matches[map_name].append((round_id, round_num, actual_time))

            # Count unique map plays (R1+R2 = 1 play)
            # BUG FIX: Don't assume R1 and R2 have consecutive IDs!
            map_play_counts = {}
            for map_name, rounds_list in map_matches.items():
                # Count R1 rounds = number of times this map was played
                r1_count = sum(1 for _, round_num, _ in rounds_list if round_num == 1)
                r2_count = sum(1 for _, round_num, _ in rounds_list if round_num == 2)
                plays = max(r1_count, r2_count, 1)
                map_play_counts[map_name] = plays

            # Sort by play count descending, then alphabetically
            sorted_maps = sorted(map_play_counts.items(), key=lambda x: (-x[1], x[0]))
            if sorted_maps:
                maps_played = ", ".join(f"{name} (x{count})" if count > 1 else name for name, count in sorted_maps)
            else:
                maps_played = "Unknown"

            # ═══════════════════════════════════════════════════════════════════════
            # BUILD AND SEND EMBEDS
            # ═══════════════════════════════════════════════════════════════════════

            # Fetch achievement badges and display names for all players
            player_guids = [player[1] for player in all_players]  # player_guid is at index 1
            player_badges = await self.badge_service.get_player_badges_batch(player_guids)
            display_names = await self.display_name_service.get_display_names_batch(player_guids)

            # Replace player names with display names
            all_players_with_display_names = []
            for player in all_players:
                player_list = list(player)
                guid = player_list[1]
                if guid in display_names:
                    player_list[0] = display_names[guid]  # Replace name at index 0
                all_players_with_display_names.append(tuple(player_list))

            # DEFAULT VIEW: ONLY SESSION OVERVIEW
            embed1 = await self.embed_builder.build_session_overview_embed(
                latest_date, all_players_with_display_names, maps_played, rounds_played, player_count,
                team_1_name, team_2_name, team_1_score, team_2_score, hardcoded_teams is not None,
                scoring_result, player_badges
            )

            # Try to send the embed, handle size limit errors
            try:
                await ctx.send(embed=embed1)
            except discord.errors.HTTPException as e:
                if "Embed size exceeds maximum size" in str(e) or "50035" in str(e):
                    # Embed is too large, send truncated version
                    await ctx.send(
                        "⚠️ **Session is too large to display in one message!**\n\n"
                        f"📅 **Session:** {latest_date}\n"
                        f"🎮 **Players:** {player_count}\n"
                        f"🗺️ **Rounds:** {rounds_played} ({unique_maps} unique maps)\n\n"
                        "💡 **Try using specific views instead:**\n"
                        "• `!last_session top` - Top players\n"
                        "• `!last_session combat` - Combat stats\n"
                        "• `!last_session maps` - Map breakdown\n"
                        "• `!last_session graphs` - Performance graphs"
                    )
                else:
                    raise

            # Send cumulative endstats as separate message
            if endstats_data and endstats_data.get('has_data'):
                endstats_embed = await self.embed_builder.build_session_endstats_embed(
                    latest_date, endstats_data
                )
                if endstats_embed:
                    await ctx.send(embed=endstats_embed)

        except Exception as e:
            logger.error(f"Error in last_session command: {e}", exc_info=True)
            await ctx.send(
                f"❌ Error retrieving last session: {sanitize_error_message(e)}"
            )

    @is_public_channel()
    @commands.command(name="team_history")
    async def team_history_command(self, ctx, days: int = 30):
        """📊 Show team performance history (PLACEHOLDER)"""
        await ctx.send(f"📊 Team history for last {days} days (feature coming soon)")


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(LastSessionCog(bot))
