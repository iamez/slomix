"""
Last Round Cog - Refactored with service-oriented architecture

This cog handles the !last_session command by delegating to specialized services:
- SessionDataService: Database queries for session data
- SessionStatsAggregator: Statistical aggregations
- SessionEmbedBuilder: Discord embed creation
- SessionGraphGenerator: Performance graph generation
- SessionViewHandlers: Different view modes (obj, combat, weapons, etc.)
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple

import discord
from discord.ext import commands

from bot.core.checks import is_admin, is_admin_channel, is_public_channel
from bot.core.database_adapter import ensure_player_name_alias
from bot.core.endstats_pagination_view import EndstatsPaginationView
from bot.core.utils import sanitize_error_message
from bot.stats import StatsCalculator
from bot.services.session_data_service import SessionDataService
from bot.services.stopwatch_scoring_service import StopwatchScoringService
from bot.services.session_stats_aggregator import SessionStatsAggregator
from bot.services.session_embed_builder import SessionEmbedBuilder
from bot.services.session_graph_generator import SessionGraphGenerator
from bot.services.session_view_handlers import SessionViewHandlers
from bot.services.player_badge_service import PlayerBadgeService
from bot.services.player_display_name_service import PlayerDisplayNameService
from bot.services.endstats_aggregator import EndstatsAggregator
from bot.services.session_timing_shadow_service import SessionTimingShadowService

logger = logging.getLogger("bot.cogs.last_session")


class LastSessionCog(commands.Cog):
    """🎮 Comprehensive last session analytics with multiple view modes"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("🎮 LastSessionCog initializing with service architecture...")
        self.show_timing_dual = bool(getattr(bot.config, "show_timing_dual", False))
        if not hasattr(bot, "session_timing_shadow_service"):
            bot.session_timing_shadow_service = SessionTimingShadowService(bot.db_adapter)
        self.timing_shadow_service = bot.session_timing_shadow_service

        # Initialize services
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
        self.endstats_aggregator = EndstatsAggregator(bot.db_adapter)
        self.scoring_service = StopwatchScoringService(bot.db_adapter)

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
        - !last_session time     → Time audit (played/dead/denied)
        - !last_session time_raw → Raw Lua time export (CSV)
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

            if subcommand and subcommand.lower() in ("time", "timing", "times"):
                await self.view_handlers.show_time_view(ctx, latest_date, session_ids, session_ids_str, player_count)
                return

            if subcommand and subcommand.lower() in ("time_raw", "timeraw", "time-raw", "timecsv", "time_csv"):
                await self.view_handlers.show_time_raw_export(ctx, latest_date, session_ids, session_ids_str)
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
                        description="FragPotential, Damage Efficiency, Denied Playtime, Survival Rate, Useful Kills, Self Kills, Full Selfkills",
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

            # Scoring debug view (header winner + side mapping)
            if subcommand and subcommand.lower() == "debug":
                hardcoded_teams = await self.data_service.get_hardcoded_teams(session_ids)
                if not hardcoded_teams or len(hardcoded_teams) < 2:
                    await ctx.send("❌ No hardcoded teams available for scoring debug.")
                    return

                team_rosters = {k: v.get('guids', []) for k, v in hardcoded_teams.items()}
                scoring_result = await self.scoring_service.calculate_session_scores_with_teams(
                    latest_date, session_ids, team_rosters
                )
                if not scoring_result or 'maps' not in scoring_result:
                    await ctx.send("❌ No scoring debug data available.")
                    return

                team_a_name = scoring_result.get('team_a_name', 'Team A')
                team_b_name = scoring_result.get('team_b_name', 'Team B')

                lines = []
                for m in scoring_result['maps']:
                    map_name = m.get('map', 'Unknown')
                    winner = m.get('winner', 'tie')
                    winner_side = m.get('winner_side', 'n/a')
                    team_a_r1_side = m.get('team_a_r1_side', 'n/a')
                    team_a_r2_side = m.get('team_a_r2_side', 'n/a')
                    r1_def_side = m.get('r1_defender_side', 'n/a')
                    source = m.get('scoring_source', 'n/a')
                    counted = m.get('counted', True)
                    note = m.get('note') or m.get('description', '')

                    lines.append(
                        f"**{map_name}** → winner: `{winner}` | "
                        f"winner_side:`{winner_side}` r1_def:`{r1_def_side}` "
                        f"TeamA R1:`{team_a_r1_side}` R2:`{team_a_r2_side}` "
                        f"source:`{source}` counted:`{counted}` note:`{note}`"
                    )

                if len(lines) > 20:
                    lines = lines[:20] + ["... (truncated)"]

                embed = discord.Embed(
                    title=f"🧪 Scoring Debug - {latest_date}",
                    description=(
                        f"TeamA=`{team_a_name}` • TeamB=`{team_b_name}`\n\n" +
                        "\n".join(lines)
                    ),
                    color=0x95A5A6,
                    timestamp=datetime.now()
                )
                await ctx.send(embed=embed)
                return

            # ═══════════════════════════════════════════════════════════════════════
            # DEFAULT COMPREHENSIVE VIEW - Full session analytics
            # ═══════════════════════════════════════════════════════════════════════

            # Phase 2: Get hardcoded teams and team scores
            hardcoded_teams = await self.data_service.get_hardcoded_teams(session_ids)

            # Get team mappings FIRST (needed for proper team stats aggregation and scoring)
            team_1_name_mapped, team_2_name_mapped, team_1_players_list, team_2_players_list, name_to_team = await self.data_service.build_team_mappings(
                session_ids, session_ids_str, hardcoded_teams
            )

            # Try to calculate team-aware stopwatch scoring (MAP wins, not round wins)
            scoring_result = None
            if hardcoded_teams and len(hardcoded_teams) >= 2:
                # Build team_rosters dict for scoring service
                team_rosters = {}
                for team_name, players in hardcoded_teams.items():
                    # Extract GUIDs from player data (supports both dict and list formats)
                    if isinstance(players, dict):
                        guids = players.get('guids', [])
                    else:
                        guids = []
                        for p in players:
                            if isinstance(p, dict) and 'guid' in p:
                                guids.append(p['guid'])
                            elif isinstance(p, str):
                                guids.append(p)
                    team_rosters[team_name] = guids

                scoring_result = await self.scoring_service.calculate_session_scores_with_teams(
                    latest_date, session_ids, team_rosters
                )

            if scoring_result:
                # Use team-aware map scoring (correct for stopwatch mode)
                team_1_name = scoring_result.get('team_a_name', 'Team A')
                team_2_name = scoring_result.get('team_b_name', 'Team B')
                team_1_score = scoring_result.get('team_a_maps', 0)
                team_2_score = scoring_result.get('team_b_maps', 0)
            else:
                # Fallback to old round-based scoring
                scores = await self.stats_aggregator.calculate_session_scores(session_ids, session_ids_str, hardcoded_teams)
                team_1_name = scores['team_a_name']
                team_2_name = scores['team_b_name']
                team_1_score = scores['team_a_score']
                team_2_score = scores['team_b_score']
                scoring_result = scores

            # Use mapped team names if available and scoring didn't provide them
            if team_1_name_mapped and team_2_name_mapped:
                if team_1_name in ('Team A', 'Team 1'):
                    team_1_name = team_1_name_mapped
                if team_2_name in ('Team B', 'Team 2'):
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

            full_selfkills_available = await self.stats_aggregator.has_full_selfkills_column()
            timing_dual_by_guid = None
            timing_dual_meta = None
            if self.show_timing_dual:
                try:
                    timing_dual_payload = await self.view_handlers.get_session_timing_dual_by_guid(session_ids)
                    timing_dual_by_guid = timing_dual_payload.get("players", {})
                    timing_dual_meta = timing_dual_payload.get("meta", {})
                except Exception as e:  # nosec B110
                    logger.warning("Could not build timing dual payload: %s", e)
                    timing_dual_by_guid = {}
                    timing_dual_meta = {"reason": "Shadow timing unavailable"}

            # DEFAULT VIEW: ONLY SESSION OVERVIEW
            embed1 = await self.embed_builder.build_session_overview_embed(
                latest_date, all_players_with_display_names, maps_played, rounds_played, player_count,
                team_1_name, team_2_name, team_1_score, team_2_score, hardcoded_teams is not None,
                scoring_result, player_badges, full_selfkills_available,
                timing_dual_by_guid=timing_dual_by_guid,
                timing_dual_meta=timing_dual_meta,
                show_timing_dual=self.show_timing_dual,
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
                map_pages, round_pages = await self._build_endstats_pages(
                    latest_date, sessions, session_ids
                )
                if map_pages:
                    view = EndstatsPaginationView(ctx, map_pages, round_pages)
                    first_embed = view._decorate_embed(map_pages[0])
                    message = await ctx.send(embed=first_embed, view=view)
                    view.message = message
                else:
                    logger.warning("Endstats data found but no pages were generated")

        except Exception as e:
            logger.error(f"Error in last_session command: {e}", exc_info=True)
            await ctx.send(
                f"❌ Error retrieving last session: {sanitize_error_message(e)}"
            )

    @is_admin_channel()
    @is_admin()
    @commands.command(name="last_session_debug", aliases=["last_debug", "ls_debug"])
    async def last_session_debug(self, ctx, top_n: int = 8):
        """Admin debug: compact top-N timing diffs (old vs shadow/new)."""
        try:
            top_n = max(1, min(int(top_n or 8), 20))

            latest_date = await self.data_service.get_latest_session_date()
            if not latest_date:
                await ctx.send("❌ No rounds found in database")
                return

            sessions, session_ids, _session_ids_str, _player_count = await self.data_service.fetch_session_data(
                latest_date
            )
            if not sessions:
                await ctx.send("❌ No rounds found for latest date")
                return

            summary = await self.view_handlers.get_timing_diff_summary(session_ids, top_n=top_n)
            rows = summary.get("rows", [])
            meta = summary.get("meta", {})
            rounds_total = int(meta.get("rounds_total") or len(session_ids))
            rounds_with_telemetry = int(meta.get("rounds_with_telemetry") or 0)
            reason = meta.get("reason") or ""
            source = meta.get("source") or "none"

            embed = discord.Embed(
                title=f"🧪 Last Session Timing Debug - {latest_date}",
                description=(
                    f"Top `{top_n}` timing diffs (`O` old stats vs `N` shadow/Lua)\n"
                    f"Lua coverage: `{rounds_with_telemetry}/{rounds_total}` rounds"
                ),
                color=0x95A5A6,
                timestamp=datetime.now(),
            )

            if rows:
                lines = []
                for idx, item in enumerate(rows, start=1):
                    map_name = str(item.get("map_name") or "unknown")[:14]
                    round_number = int(item.get("round_number") or 0)
                    player_name = str(item.get("player_name") or "").strip()
                    if "old_dead_seconds" in item:
                        old_dead = int(item.get("old_dead_seconds") or 0)
                        new_dead = int(item.get("new_dead_seconds") or 0)
                        old_denied = int(item.get("old_denied_seconds") or 0)
                        new_denied = int(item.get("new_denied_seconds") or 0)
                        dead_diff = int(item.get("dead_diff_seconds") or (new_dead - old_dead))
                        denied_diff = int(item.get("denied_diff_seconds") or (new_denied - old_denied))
                        fallback_reason = str(item.get("fallback_reason") or "")
                        fallback_note = f" ⚠️{fallback_reason}" if fallback_reason and fallback_reason != "none" else ""
                        player_segment = f" `{player_name[:12]}`" if player_name else ""
                        lines.append(
                            f"`{idx:>2}.` **{map_name} R{round_number}**{player_segment} "
                            f"💀O`{self.view_handlers._format_seconds(old_dead)}` "
                            f"N`{self.view_handlers._format_seconds(new_dead)}` "
                            f"Δ`{dead_diff:+d}s` "
                            f"⏳O`{self.view_handlers._format_seconds(old_denied)}` "
                            f"N`{self.view_handlers._format_seconds(new_denied)}` "
                            f"Δ`{denied_diff:+d}s`{fallback_note}"
                        )
                    else:
                        stats_seconds = int(item.get("stats_seconds") or 0)
                        lua_seconds_val = item.get("lua_seconds")
                        lua_seconds = int(lua_seconds_val) if lua_seconds_val is not None else stats_seconds
                        diff_seconds = int(item.get("diff_seconds") or 0)
                        lines.append(
                            f"`{idx:>2}.` **{map_name} R{round_number}** "
                            f"O`{self.view_handlers._format_seconds(stats_seconds)}` "
                            f"N`{self.view_handlers._format_seconds(lua_seconds)}` "
                            f"Δ`{diff_seconds:+d}s`"
                        )

                embed.add_field(
                    name="Round Diffs",
                    value="\n".join(lines),
                    inline=False,
                )
            else:
                no_data_reason = reason or "No comparable Lua timing rows were found."
                embed.add_field(
                    name="Round Diffs",
                    value=f"⚠️ {no_data_reason}",
                    inline=False,
                )

            embed.set_footer(text=f"source={source}" + (f" • {reason}" if reason and reason != "OK" else ""))
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error("Error in last_session_debug command: %s", e, exc_info=True)
            await ctx.send(f"❌ Error retrieving timing debug: {sanitize_error_message(e)}")

    @is_public_channel()
    @commands.command(name="team_history")
    async def team_history_command(self, ctx, days: int = 30):
        """📊 Show team performance history (PLACEHOLDER)"""
        await ctx.send(f"📊 Team history for last {days} days (feature coming soon)")

    @is_public_channel()
    @commands.command(name="endstats_audit", aliases=["endstats_check", "endstats_status"])
    async def endstats_audit_command(self, ctx):
        """🔎 Audit endstats coverage for the latest session."""
        try:
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

            placeholders = ",".join(["?"] * len(session_ids))
            query = f"""
                WITH target_rounds AS (
                    SELECT id, map_name, round_number, round_date, round_time
                    FROM rounds
                    WHERE id IN ({placeholders})
                ),
                awards AS (
                    SELECT round_id, COUNT(*) AS awards_count
                    FROM round_awards
                    WHERE round_id IN ({placeholders})
                    GROUP BY round_id
                )
                SELECT tr.id, tr.map_name, tr.round_number,
                       COALESCE(aw.awards_count, 0) AS awards_count
                FROM target_rounds tr
                LEFT JOIN awards aw ON aw.round_id = tr.id
                ORDER BY tr.round_date, tr.round_time
            """
            params = tuple(session_ids) * 2
            rows = await self.bot.db_adapter.fetch_all(query, params)

            total_rounds = len(rows)
            rounds_with_awards = sum(1 for row in rows if (row[3] or 0) > 0)

            missing_awards = [
                f"`{row[1]}` R{row[2]} (id {row[0]})"
                for row in rows if (row[3] or 0) == 0
            ]
            embed = discord.Embed(
                title=f"🔎 Endstats Audit - {latest_date}",
                description="Coverage summary for the latest session",
                color=0x5DADE2,
                timestamp=datetime.now(),
            )

            embed.add_field(
                name="Coverage",
                value=(
                    f"Rounds: `{total_rounds}`\n"
                    f"Awards: `{rounds_with_awards}/{total_rounds}`"
                ),
                inline=False,
            )

            if missing_awards:
                display = missing_awards[:10]
                if len(missing_awards) > 10:
                    display.append(f"... +{len(missing_awards) - 10} more")
                embed.add_field(
                    name="Missing Awards",
                    value="\n".join(display),
                    inline=False,
                )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in endstats_audit command: {e}", exc_info=True)
            await ctx.send(
                f"❌ Error auditing endstats: {sanitize_error_message(e)}"
            )

    def _group_map_matches_for_endstats(self, sessions: List[Tuple]) -> List[Dict[str, Any]]:
        """Group session rounds into map matches (R1/R2 pairs) preserving order."""
        map_matches: List[Dict[str, Any]] = []
        i = 0
        while i < len(sessions):
            round_id, map_name, round_num, actual_time = sessions[i]
            match_data = {
                "map_name": map_name,
                "rounds": [],
            }

            while i < len(sessions) and sessions[i][1] == map_name and len(match_data["rounds"]) < 2:
                round_id, map_name, round_num, actual_time = sessions[i]
                match_data["rounds"].append(
                    {
                        "round_id": round_id,
                        "round_num": round_num,
                        "actual_time": actual_time,
                    }
                )
                i += 1

            map_matches.append(match_data)

        return map_matches

    async def _fetch_endstats_round_data(
        self, session_ids: List[int]
    ) -> Dict[int, List[Dict[str, Any]]]:
        if not session_ids:
            return {}

        placeholders = ",".join(["?"] * len(session_ids))

        awards_query = f"""
            SELECT round_id, award_name, player_name, award_value, award_value_numeric
            FROM round_awards
            WHERE round_id IN ({placeholders})
            ORDER BY round_id, id
        """
        awards_rows = await self.bot.db_adapter.fetch_all(awards_query, tuple(session_ids))

        awards_by_round: Dict[int, List[Dict[str, Any]]] = {}
        for round_id, award_name, player_name, award_value, award_numeric in awards_rows:
            awards_by_round.setdefault(round_id, []).append(
                {
                    "name": award_name,
                    "player": player_name,
                    "value": award_value,
                    "numeric": award_numeric,
                }
            )

        return awards_by_round

    async def _build_endstats_pages(
        self,
        latest_date: str,
        sessions: List[Tuple],
        session_ids: List[int],
    ) -> Tuple[List[discord.Embed], List[discord.Embed]]:
        """Build endstats embeds for map-level and round-level pagination."""
        awards_by_round = await self._fetch_endstats_round_data(session_ids)
        map_matches = self._group_map_matches_for_endstats(sessions)

        if not map_matches:
            return [], []

        map_counts: Dict[str, int] = {}
        for match in map_matches:
            map_name = match["map_name"]
            map_counts[map_name] = map_counts.get(map_name, 0) + 1

        map_occurrence: Dict[str, int] = {}
        map_pages: List[discord.Embed] = []
        round_pages: List[discord.Embed] = []

        for map_index, match in enumerate(map_matches, start=1):
            map_name = match["map_name"]
            if map_counts[map_name] > 1:
                occurrence_num = map_occurrence.get(map_name, 0) + 1
                map_occurrence[map_name] = occurrence_num
                display_map_name = f"{map_name} (#{occurrence_num})"
            else:
                display_map_name = map_name

            map_embed = discord.Embed(
                title=f"🏆 Endstats - {display_map_name}",
                description=f"Session {latest_date} • Map {map_index}/{len(map_matches)}",
                color=0xF1C40F,
                timestamp=datetime.now(),
            )

            for round_info in match["rounds"]:
                round_id = round_info["round_id"]
                round_num = round_info["round_num"]

                awards_text = self.endstats_aggregator.build_round_awards_display(
                    awards_by_round.get(round_id, []),
                    max_per_category=1,
                    max_total=12,
                )
                field_value = awards_text

                map_embed.add_field(
                    name=f"Round {round_num}",
                    value=field_value,
                    inline=False,
                )

            map_pages.append(map_embed)

            for round_info in match["rounds"]:
                round_id = round_info["round_id"]
                round_num = round_info["round_num"]

                round_embed = discord.Embed(
                    title=f"🏆 Endstats - {display_map_name} R{round_num}",
                    description=f"Session {latest_date}",
                    color=0xF39C12,
                    timestamp=datetime.now(),
                )

                awards_text = self.endstats_aggregator.build_round_awards_display(
                    awards_by_round.get(round_id, []),
                    max_per_category=3,
                    max_total=36,
                )
                round_embed.add_field(name="Awards", value=awards_text, inline=False)

                round_pages.append(round_embed)

        return map_pages, round_pages


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(LastSessionCog(bot))
