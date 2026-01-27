"""
Timing Debug Service - Compares stats file timing vs Lua webhook timing

This service posts debug embeds to a dev channel showing the timing differences
between two data sources:
1. Stats file (c0rnp0rn) - parsed from game server stats files
2. Lua webhook - real-time data captured by our Lua script

Purpose: Validate that our Lua timing fixes (surrender bug, pause tracking)
are working correctly by comparing against the "official" stats file timing.
"""

import discord
from datetime import datetime
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger('TimingDebugService')


class TimingDebugService:
    """
    Service for posting timing comparison debug embeds.

    Compares round timing from:
    - Stats file (rounds table): actual_time, time_limit
    - Lua webhook (lua_round_teams table): actual_duration_seconds, pause info, end_reason
    """

    def __init__(self, bot, db_adapter, config):
        """
        Initialize timing debug service.

        Args:
            bot: Discord bot instance (for channel access)
            db_adapter: DatabaseAdapter instance (for database queries)
            config: BotConfig instance (for timing_debug_channel_id, enabled flag)
        """
        self.bot = bot
        self.db_adapter = db_adapter
        self.config = config

        # Get config values with defaults
        self.enabled = getattr(config, 'timing_debug_enabled', False)
        self.debug_channel_id = getattr(config, 'timing_debug_channel_id', 0)

        if self.enabled:
            logger.info(f"✅ TimingDebugService initialized (channel: {self.debug_channel_id})")
        else:
            logger.info("⏸️ TimingDebugService disabled")

    def _parse_time_to_seconds(self, time_str: str) -> Optional[int]:
        """
        Parse time string (MM:SS or HH:MM:SS) to seconds.

        Args:
            time_str: Time string like "12:34" or "1:23:45"

        Returns:
            Total seconds, or None if parsing fails
        """
        if not time_str or time_str == 'Unknown':
            return None

        try:
            parts = time_str.strip().split(':')
            if len(parts) == 2:
                # MM:SS format
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                # HH:MM:SS format
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            else:
                return None
        except (ValueError, AttributeError):
            return None

    def _get_diff_color(self, diff_seconds: Optional[int]) -> discord.Color:
        """
        Get embed color based on timing difference.

        Args:
            diff_seconds: Absolute difference in seconds, or None

        Returns:
            Discord color (green < 60s, orange 60-120s, red > 120s)
        """
        if diff_seconds is None:
            return discord.Color.greyple()  # No data to compare
        elif diff_seconds < 60:
            return discord.Color.green()
        elif diff_seconds < 120:
            return discord.Color.orange()
        else:
            return discord.Color.red()

    async def _get_channel(self) -> Optional[discord.TextChannel]:
        """Get the debug channel, or None if not configured/found."""
        if not self.debug_channel_id:
            return None

        channel = self.bot.get_channel(self.debug_channel_id)
        if not channel:
            logger.warning(f"⚠️ Timing debug channel {self.debug_channel_id} not found")
        return channel

    async def post_round_timing_comparison(
        self,
        round_id: int,
        match_id: Optional[str] = None,
        round_number: Optional[int] = None
    ) -> None:
        """
        Compare and post timing debug embed for a single round.

        Called after a round is published to the stats channel.
        Queries both rounds and lua_round_teams tables to compare timing.

        Args:
            round_id: Database round ID
            match_id: Optional match identifier (fetched from DB if not provided)
            round_number: Optional round number (fetched from DB if not provided)
        """
        if not self.enabled:
            return

        channel = await self._get_channel()
        if not channel:
            return

        try:
            # Query both tables for timing data
            query = """
                SELECT
                    r.id,
                    r.match_id,
                    r.round_number,
                    r.map_name,
                    r.time_limit,
                    r.actual_time,
                    l.actual_duration_seconds as lua_duration,
                    l.total_pause_seconds as lua_pauses,
                    l.pause_count as lua_pause_count,
                    l.end_reason as lua_end_reason,
                    l.surrender_team,
                    l.surrender_caller_name,
                    l.axis_score,
                    l.allies_score
                FROM rounds r
                LEFT JOIN lua_round_teams l
                    ON r.match_id = l.match_id
                    AND r.round_number = l.round_number
                WHERE r.id = $1
            """
            row = await self.db_adapter.fetch_one(query, (round_id,))

            if not row:
                logger.warning(f"⚠️ No round data found for round_id={round_id}")
                return

            # Unpack results
            _, db_match_id, db_round_num, map_name, time_limit, actual_time, \
                lua_duration, lua_pauses, lua_pause_count, lua_end_reason, \
                surrender_team, surrender_caller_name, axis_score, allies_score = row

            # Parse stats file time to seconds
            stats_duration = self._parse_time_to_seconds(actual_time)

            # Calculate difference
            diff_seconds = None
            if stats_duration is not None and lua_duration is not None:
                diff_seconds = abs(stats_duration - lua_duration)

            # Determine embed color
            embed_color = self._get_diff_color(diff_seconds)

            # Build embed
            embed = discord.Embed(
                title=f"⏱️ TIMING DEBUG: {map_name or 'Unknown'} R{db_round_num}",
                color=embed_color,
                timestamp=datetime.now()
            )

            # Stats File (c0rnp0rn) section
            stats_value = f"**Duration:** {actual_time or 'N/A'}"
            if stats_duration is not None:
                stats_value += f" ({stats_duration} sec)"
            stats_value += f"\n**Time Limit:** {time_limit or 'N/A'}"

            embed.add_field(
                name="📊 Stats File (c0rnp0rn)",
                value=stats_value,
                inline=False
            )

            # Lua Webhook (ours) section
            if lua_duration is not None:
                lua_mins = lua_duration // 60
                lua_secs = lua_duration % 60
                lua_value = f"**Duration:** {lua_mins}:{lua_secs:02d} ({lua_duration} sec)"

                if lua_pauses and lua_pause_count:
                    lua_value += f"\n**Pauses:** {lua_pause_count} ({lua_pauses} sec)"
                elif lua_pauses == 0:
                    lua_value += f"\n**Pauses:** None"

                if lua_end_reason:
                    lua_value += f"\n**End Reason:** {lua_end_reason}"

                # Surrender info (v1.4.0)
                if surrender_team and surrender_team > 0:
                    team_name = "Axis" if surrender_team == 1 else "Allies"
                    lua_value += f"\n**Surrendered:** {team_name}"
                    if surrender_caller_name:
                        lua_value += f" (by {surrender_caller_name})"

                # Match score (v1.4.0)
                if axis_score is not None and allies_score is not None:
                    lua_value += f"\n**Score:** Axis {axis_score} - {allies_score} Allies"
            else:
                lua_value = "⚠️ **No Lua data available**\n(Webhook may not have triggered)"

            embed.add_field(
                name="🔧 Lua Webhook (ours)",
                value=lua_value,
                inline=False
            )

            # Analysis section
            analysis_parts = []

            if diff_seconds is not None:
                analysis_parts.append(f"**Difference:** {diff_seconds} seconds")

                # Check for surrender fix
                if lua_end_reason == 'surrender' and diff_seconds > 0:
                    analysis_parts.append(f"**Surrender Fix:** ✅ Yes (saved {diff_seconds}s)")
                elif lua_end_reason == 'surrender':
                    analysis_parts.append(f"**Surrender Fix:** ✅ Applied")
                elif diff_seconds == 0:
                    analysis_parts.append("**Match:** ✅ Perfect timing match!")
                elif diff_seconds < 5:
                    analysis_parts.append("**Match:** ✅ Within acceptable variance")
                else:
                    analysis_parts.append("**Match:** ⚠️ Investigate timing discrepancy")

                # Note if pauses explain the difference
                if lua_pauses and lua_pauses > 0:
                    remaining_diff = diff_seconds - lua_pauses
                    if abs(remaining_diff) < 5:
                        analysis_parts.append(f"**Pauses explain diff:** ✅ ({lua_pauses}s pauses)")
            else:
                if lua_duration is None:
                    analysis_parts.append("**Status:** Cannot compare - no Lua data")
                else:
                    analysis_parts.append("**Status:** Cannot compare - missing stats duration")

            embed.add_field(
                name="🔍 Analysis",
                value="\n".join(analysis_parts) if analysis_parts else "No analysis available",
                inline=False
            )

            # Footer with IDs for debugging
            embed.set_footer(text=f"match_id: {db_match_id} | round_id: {round_id}")

            # Send embed
            await channel.send(embed=embed)
            logger.debug(f"📤 Posted timing debug for {map_name} R{db_round_num}")

        except Exception as e:
            logger.error(f"❌ Error posting round timing comparison: {e}", exc_info=True)

    async def post_session_timing_comparison(
        self,
        session_ids: List[int]
    ) -> None:
        """
        Compare and post aggregated timing debug embed for a session.

        Called after session graphs are generated.
        Shows a summary table of all rounds in the session with timing comparisons.

        Args:
            session_ids: List of round IDs in the session
        """
        if not self.enabled:
            return

        if not session_ids:
            return

        channel = await self._get_channel()
        if not channel:
            return

        try:
            # Query all rounds in session with Lua data
            placeholders = ','.join(['$' + str(i+1) for i in range(len(session_ids))])
            query = f"""
                SELECT
                    r.id,
                    r.match_id,
                    r.round_number,
                    r.map_name,
                    r.time_limit,
                    r.actual_time,
                    l.actual_duration_seconds as lua_duration,
                    l.total_pause_seconds as lua_pauses,
                    l.end_reason as lua_end_reason,
                    l.surrender_team,
                    l.surrender_caller_name
                FROM rounds r
                LEFT JOIN lua_round_teams l
                    ON r.match_id = l.match_id
                    AND r.round_number = l.round_number
                WHERE r.id IN ({placeholders})
                ORDER BY r.round_date, r.round_time, r.round_number
            """
            rows = await self.db_adapter.fetch_all(query, tuple(session_ids))

            if not rows:
                return

            # Build summary data
            total_rounds = len(rows)
            rounds_with_lua = 0
            surrender_fixes = 0
            total_time_corrected = 0
            max_diff = 0

            table_lines = []

            for row in rows:
                round_id, match_id, round_num, map_name, time_limit, actual_time, \
                    lua_duration, lua_pauses, lua_end_reason, \
                    surrender_team, surrender_caller_name = row

                # Parse stats duration
                stats_duration = self._parse_time_to_seconds(actual_time)

                # Calculate difference
                diff = None
                fix_indicator = ""

                if lua_duration is not None:
                    rounds_with_lua += 1

                    if stats_duration is not None:
                        diff = stats_duration - lua_duration  # Positive = stats is longer
                        max_diff = max(max_diff, abs(diff))

                        if lua_end_reason == 'surrender' and diff > 0:
                            surrender_fixes += 1
                            total_time_corrected += diff
                            fix_indicator = "✓"
                        elif diff == 0:
                            fix_indicator = "="
                        elif abs(diff) < 5:
                            fix_indicator = "≈"
                        else:
                            fix_indicator = "?"
                else:
                    diff = None
                    fix_indicator = "⚠️"

                # Build table row
                map_short = (map_name or "?")[:8]
                stats_str = f"{stats_duration}s" if stats_duration else "N/A"
                lua_str = f"{lua_duration}s" if lua_duration else "N/A"
                diff_str = f"{diff:+d}s" if diff is not None else "N/A"

                table_lines.append(
                    f"| {map_short:8} | {round_num:>2} | {stats_str:>6} | {lua_str:>5} | {diff_str:>5} | {fix_indicator:^4} |"
                )

            # Determine embed color based on overall quality
            if rounds_with_lua == 0:
                embed_color = discord.Color.greyple()
            elif max_diff < 30:
                embed_color = discord.Color.green()
            elif max_diff < 120:
                embed_color = discord.Color.orange()
            else:
                embed_color = discord.Color.red()

            # Build embed
            embed = discord.Embed(
                title=f"⏱️ SESSION TIMING DEBUG: {total_rounds} rounds",
                color=embed_color,
                timestamp=datetime.now()
            )

            # Table header
            table_header = "| Map      | R# | Stats |  Lua | Diff | Fix? |"
            table_divider = "|----------|---:|------:|-----:|-----:|:----:|"

            # Combine table (with code block for monospace)
            table_content = f"```\n{table_header}\n{table_divider}\n"
            table_content += "\n".join(table_lines)
            table_content += "\n```"

            embed.add_field(
                name="Round Comparison",
                value=table_content if len(table_content) < 1024 else "Too many rounds to display",
                inline=False
            )

            # Summary section
            summary_parts = [
                f"• **Rounds with Lua data:** {rounds_with_lua}/{total_rounds}",
            ]

            if surrender_fixes > 0:
                summary_parts.append(f"• **Surrender fixes applied:** {surrender_fixes}")
                summary_parts.append(f"• **Total time corrected:** {total_time_corrected}s")

            if max_diff > 0:
                summary_parts.append(f"• **Max timing difference:** {max_diff}s")

            if rounds_with_lua < total_rounds:
                missing = total_rounds - rounds_with_lua
                summary_parts.append(f"• **⚠️ Missing Lua data:** {missing} rounds")

            embed.add_field(
                name="Summary",
                value="\n".join(summary_parts),
                inline=False
            )

            # Legend
            embed.add_field(
                name="Legend",
                value="✓ = Surrender fix applied | = = Perfect match | ≈ = Close (<5s) | ? = Large diff | ⚠️ = No Lua data",
                inline=False
            )

            # Footer
            embed.set_footer(text=f"Session IDs: {session_ids[0]}..{session_ids[-1]}")

            # Send embed
            await channel.send(embed=embed)
            logger.info(f"📤 Posted session timing debug for {total_rounds} rounds")

        except Exception as e:
            logger.error(f"❌ Error posting session timing comparison: {e}", exc_info=True)
