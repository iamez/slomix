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
from datetime import datetime, timedelta
import logging
import re
from typing import List, Optional, Tuple, Any, Dict

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
            text = str(time_str).strip()
            parts = text.split(':')
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            if '.' in text:
                minutes = float(text)
                return int(minutes * 60)
            return int(float(text))
        except (ValueError, AttributeError):
            return None

    def _parse_round_datetime(self, round_date: str, round_time: str) -> Optional[datetime]:
        """Parse round date/time from multiple known formats."""
        date_str = str(round_date).strip() if round_date is not None else ""
        time_str = str(round_time).strip() if round_time is not None else ""

        if re.match(r"^\d{4}-\d{2}-\d{2}-\d{6}$", date_str):
            try:
                return datetime.strptime(date_str, "%Y-%m-%d-%H%M%S")
            except ValueError:
                pass

        if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", date_str):
            try:
                return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

        if time_str and ":" in time_str:
            try:
                return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

        if time_str and re.match(r"^\d{6}$", time_str):
            try:
                return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H%M%S")
            except ValueError:
                pass

        return None

    async def _fetch_lua_data(
        self,
        round_id: Optional[int],
        map_name: str,
        round_number: int,
        round_date: str,
        round_time: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch Lua webhook timing data with fuzzy match.
        """
        if round_id:
            direct_query = """
                SELECT id, match_id, round_number, map_name,
                       round_start_unix, round_end_unix, actual_duration_seconds,
                       total_pause_seconds, pause_count, end_reason,
                       winner_team, defender_team, time_limit_minutes,
                       lua_warmup_seconds, lua_warmup_start_unix,
                       lua_pause_events,
                       surrender_team, surrender_caller_name,
                       axis_score, allies_score,
                       captured_at
                FROM lua_round_teams
                WHERE round_id = $1
                ORDER BY captured_at DESC
                LIMIT 1
            """
            row = await self.db_adapter.fetch_one(direct_query, (round_id,))
            if row:
                (id_, match_id, rn, mn, start_unix, end_unix, duration,
                 pause_sec, pause_count, end_reason, winner, defender, timelimit,
                 warmup_sec, warmup_start, pause_events,
                 surr_team, surr_caller, axis_score, allies_score, captured_at) = row

                return {
                    'lua_id': id_,
                    'match_id': match_id,
                    'round_number': rn,
                    'map_name': mn,
                    'round_start_unix': start_unix,
                    'round_end_unix': end_unix,
                    'lua_duration_seconds': duration,
                    'total_pause_seconds': pause_sec or 0,
                    'pause_count': pause_count or 0,
                    'end_reason': end_reason,
                    'winner_team': winner,
                    'defender_team': defender,
                    'time_limit_minutes': timelimit,
                    'warmup_seconds': warmup_sec or 0,
                    'warmup_start_unix': warmup_start,
                    'surrender_team': surr_team,
                    'surrender_caller': surr_caller,
                    'axis_score': axis_score,
                    'allies_score': allies_score,
                    'captured_at': captured_at,
                    'match_confidence': 'direct'
                }

        round_datetime = self._parse_round_datetime(round_date, round_time)
        if not round_datetime:
            logger.warning(f"Could not parse round datetime: {round_date} {round_time}")
            return None

        query = """
            SELECT id, match_id, round_number, map_name,
                   round_start_unix, round_end_unix, actual_duration_seconds,
                   total_pause_seconds, pause_count, end_reason,
                   winner_team, defender_team, time_limit_minutes,
                   lua_warmup_seconds, lua_warmup_start_unix,
                   lua_pause_events,
                   surrender_team, surrender_caller_name,
                   axis_score, allies_score,
                   captured_at
            FROM lua_round_teams
            WHERE map_name = $1
              AND round_number = $2
            ORDER BY captured_at DESC
            LIMIT 5
        """

        try:
            rows = await self.db_adapter.fetch_all(query, (map_name, round_number))
        except Exception as e:
            logger.warning(f"Could not query lua_round_teams: {e}")
            return None

        if not rows:
            return None

        best_match = None
        min_diff = timedelta(hours=24)

        for row in rows:
            (id_, match_id, rn, mn, start_unix, end_unix, duration,
             pause_sec, pause_count, end_reason, winner, defender, timelimit,
             warmup_sec, warmup_start, pause_events,
             surr_team, surr_caller, axis_score, allies_score, captured_at) = row

            candidates = []
            if end_unix:
                try:
                    candidates.append(datetime.fromtimestamp(end_unix))
                except (OSError, ValueError, TypeError):
                    pass
            if start_unix:
                try:
                    candidates.append(datetime.fromtimestamp(start_unix))
                except (OSError, ValueError, TypeError):
                    pass
            if captured_at:
                if isinstance(captured_at, str):
                    try:
                        captured_dt = datetime.fromisoformat(captured_at.replace('Z', '+00:00'))
                        candidates.append(captured_dt.replace(tzinfo=None))
                    except ValueError:
                        pass
                else:
                    candidates.append(captured_at.replace(tzinfo=None) if captured_at.tzinfo else captured_at)

            if not candidates:
                continue

            best_candidate = min(candidates, key=lambda dt: abs(dt - round_datetime))
            time_diff = abs(best_candidate - round_datetime)

            if time_diff < min_diff and time_diff < timedelta(minutes=30):
                min_diff = time_diff
                best_match = {
                    'lua_id': id_,
                    'match_id': match_id,
                    'round_number': rn,
                    'map_name': mn,
                    'round_start_unix': start_unix,
                    'round_end_unix': end_unix,
                    'lua_duration_seconds': duration,
                    'total_pause_seconds': pause_sec or 0,
                    'pause_count': pause_count or 0,
                    'end_reason': end_reason,
                    'winner_team': winner,
                    'defender_team': defender,
                    'time_limit_minutes': timelimit,
                    'warmup_seconds': warmup_sec or 0,
                    'warmup_start_unix': warmup_start,
                    'surrender_team': surr_team,
                    'surrender_caller': surr_caller,
                    'axis_score': axis_score,
                    'allies_score': allies_score,
                    'captured_at': captured_at,
                    'match_confidence': 'high' if time_diff < timedelta(minutes=10) else 'medium'
                }

        return best_match

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
            # Query rounds table (Lua matched separately to avoid match_id mismatch)
            query = """
                SELECT
                    r.id,
                    r.match_id,
                    r.round_number,
                    r.map_name,
                    r.round_date,
                    r.round_time,
                    r.time_limit,
                    r.actual_time
                FROM rounds r
                WHERE r.id = $1
            """
            row = await self.db_adapter.fetch_one(query, (round_id,))

            if not row:
                logger.warning(f"⚠️ No round data found for round_id={round_id}")
                return

            # Unpack results
            _, db_match_id, db_round_num, map_name, round_date, round_time, time_limit, actual_time = row

            lua_data = await self._fetch_lua_data(round_id, map_name, db_round_num, round_date, round_time)
            lua_duration = lua_data.get('lua_duration_seconds') if lua_data else None
            lua_start_unix = lua_data.get('round_start_unix') if lua_data else None
            lua_end_unix = lua_data.get('round_end_unix') if lua_data else None
            lua_pauses = lua_data.get('total_pause_seconds') if lua_data else None
            lua_pause_count = lua_data.get('pause_count') if lua_data else None
            lua_end_reason = lua_data.get('end_reason') if lua_data else None
            surrender_team = lua_data.get('surrender_team') if lua_data else None
            surrender_caller_name = lua_data.get('surrender_caller') if lua_data else None
            axis_score = lua_data.get('axis_score') if lua_data else None
            allies_score = lua_data.get('allies_score') if lua_data else None
            lua_warmup_seconds = lua_data.get('warmup_seconds') if lua_data else None
            lua_warmup_start_unix = lua_data.get('warmup_start_unix') if lua_data else None
            match_confidence = lua_data.get('match_confidence') if lua_data else None

            # Parse stats file time to seconds
            stats_duration = self._parse_time_to_seconds(actual_time)

            # Calculate difference
            diff_seconds = None
            if stats_duration is not None and lua_duration is not None:
                diff_seconds = abs(stats_duration - lua_duration)

            # Filename timestamp (round_date/round_time) as 3rd timing anchor
            file_dt = self._parse_round_datetime(round_date, round_time)
            file_unix = int(file_dt.timestamp()) if file_dt else None
            file_vs_lua_diff = None
            if file_unix and lua_end_unix:
                file_vs_lua_diff = abs(file_unix - int(lua_end_unix))

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

                if lua_start_unix and lua_end_unix:
                    wall_clock = int(lua_end_unix) - int(lua_start_unix)
                    lua_value += f"\n**Wall-clock:** {wall_clock} sec (start→end)"
                if lua_warmup_start_unix and lua_end_unix:
                    warmup_wall = int(lua_end_unix) - int(lua_warmup_start_unix)
                    lua_value += f"\n**Wall-clock+Warmup:** {warmup_wall} sec"
                if lua_warmup_seconds:
                    lua_value += f"\n**Warmup:** {lua_warmup_seconds} sec"

                if lua_end_reason:
                    lua_value += f"\n**End Reason:** {lua_end_reason}"
                if match_confidence:
                    lua_value += f"\n**Match:** {match_confidence}"

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

            # Filename timestamp section (3rd source)
            if file_dt and file_unix:
                file_value = f"**Timestamp:** {file_dt.isoformat(sep=' ', timespec='seconds')}"
                file_value += f"\n**Unix:** {file_unix}"
                if file_vs_lua_diff is not None:
                    file_value += f"\n**Diff vs Lua end:** {file_vs_lua_diff} sec"
            else:
                file_value = "⚠️ Could not parse round_date/round_time"

            embed.add_field(
                name="🧭 Filename Timestamp (round_date/round_time)",
                value=file_value,
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
                if file_vs_lua_diff is not None:
                    if file_vs_lua_diff < 90:
                        analysis_parts.append("**File timestamp alignment:** ✅")
                    else:
                        analysis_parts.append(f"**File timestamp alignment:** ⚠️ {file_vs_lua_diff}s off")
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
