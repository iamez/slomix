"""
Timing Comparison Service - Dev Channel Display

Compares timing data from two sources:
1. Stats file (c0rnp0rn7.lua) - Per-player timing but has surrender bug
2. Lua webhook (stats_discord_webhook.lua) - Accurate round timing but no per-player data

Posts comparison embeds to a dev channel for validation and analysis.
This runs SEPARATELY from main features - does not modify existing displays.

Usage:
    After a round is processed, call post_timing_comparison() to send
    a comparison embed to the configured dev channel.

NOTE: match_id linking issue exists:
    - rounds table: match_id from filename timestamp
    - lua_round_teams: match_id from round_end_unix
    These don't match! We prefer round_id when available, otherwise map_name + round_number + time window.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any

import discord

from bot.core.round_contract import normalize_end_reason

logger = logging.getLogger("bot.services.timing_comparison")


class TimingComparisonService:
    """Service for comparing stats file vs Lua webhook timing data."""

    def __init__(self, db_adapter, bot=None):
        """
        Initialize the timing comparison service.

        Args:
            db_adapter: Database adapter for queries
            bot: Bot instance for Discord channel access
        """
        self.db_adapter = db_adapter
        self.bot = bot

    @staticmethod
    def _derive_player_side(axis_rows: Any, allies_rows: Any) -> Tuple[int, str, str]:
        """
        Derive canonical side and display marker from aggregated team samples.

        Returns:
            (team_value, side_state, side_marker)
            team_value: 1 (Axis), 2 (Allies), 0 (mixed/unknown)
            side_state: axis|allies|mixed|unknown
            side_marker: [AX]|[AL]|[MX]|[--]
        """
        axis_count = int(axis_rows or 0)
        allies_count = int(allies_rows or 0)

        if axis_count > 0 and allies_count == 0:
            return 1, "axis", "[AX]"
        if allies_count > 0 and axis_count == 0:
            return 2, "allies", "[AL]"
        if axis_count > 0 and allies_count > 0:
            return 0, "mixed", "[MX]"
        return 0, "unknown", "[--]"

    async def post_timing_comparison(
        self,
        round_id: int,
        dev_channel_id: int
    ) -> bool:
        """
        Post timing comparison embed to dev channel.

        Args:
            round_id: Database ID of the round to compare
            dev_channel_id: Discord channel ID for dev output

        Returns:
            True if successfully posted, False otherwise
        """
        try:
            # Fetch stats file data
            stats_data = await self._fetch_stats_file_data(round_id)
            if not stats_data:
                logger.warning(f"No stats file data found for round {round_id}")
                return False

            # Fetch Lua webhook data (fuzzy match on map + round + time)
            lua_data = await self._fetch_lua_data(
                round_id,
                stats_data['map_name'],
                stats_data['round_number'],
                stats_data['round_date'],
                stats_data['round_time']
            )

            # Build comparison embed
            embed = self._build_comparison_embed(stats_data, lua_data)

            # Send to dev channel
            if self.bot:
                channel = self.bot.get_channel(dev_channel_id)
                if channel:
                    await channel.send(embed=embed)
                    logger.info(f"Posted timing comparison for round {round_id} to dev channel")
                    return True
                else:
                    logger.error(f"Dev channel {dev_channel_id} not found")
                    return False
            else:
                logger.warning("No bot instance - cannot send to Discord")
                return False

        except Exception as e:
            logger.error(f"Error posting timing comparison: {e}", exc_info=True)
            return False

    async def _fetch_stats_file_data(self, round_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch stats file timing data for a round.

        Returns round metadata + per-player timing from player_comprehensive_stats.
        """
        # Get round metadata
        round_query = """
            SELECT id, match_id, round_number, map_name, round_date, round_time,
                   actual_time, time_limit, winner_team, defender_team,
                   actual_duration_seconds, total_pause_seconds, end_reason
            FROM rounds
            WHERE id = ?
        """
        round_row = await self.db_adapter.fetch_one(round_query, (round_id,))
        if not round_row:
            return None

        (id_, match_id, round_number, map_name, round_date, round_time,
         actual_time, time_limit, winner_team, defender_team,
         actual_duration_seconds, total_pause_seconds, end_reason) = round_row

        # Parse actual_time to seconds (format: "MM:SS" or seconds)
        stats_duration_seconds = self._parse_time_to_seconds(actual_time)

        # Get per-player timing data
        player_query = """
            SELECT player_guid, MAX(player_name) as player_name,
                   SUM(time_played_seconds) as time_played,
                   SUM(time_dead_minutes) * 60 as time_dead_seconds,
                   AVG(time_dead_ratio) as time_dead_ratio,
                   SUM(damage_given) as damage_given,
                   CASE
                       WHEN SUM(time_played_seconds) > 0
                       THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                       ELSE 0
                   END as dpm,
                   SUM(CASE WHEN team = 1 THEN 1 ELSE 0 END) as axis_rows,
                   SUM(CASE WHEN team = 2 THEN 1 ELSE 0 END) as allies_rows
            FROM player_comprehensive_stats
            WHERE round_id = ?
            GROUP BY player_guid
            ORDER BY damage_given DESC
        """
        player_rows = await self.db_adapter.fetch_all(player_query, (round_id,))

        players = []
        for row in player_rows:
            guid, name, time_played, time_dead, dead_ratio, dmg, dpm, axis_rows, allies_rows = row
            team, side_state, side_marker = self._derive_player_side(axis_rows, allies_rows)
            players.append({
                'guid': guid,
                'name': name,
                'team': team,
                'side_state': side_state,
                'side_marker': side_marker,
                'time_played_seconds': time_played or 0,
                'time_dead_seconds': time_dead or 0,
                'time_dead_ratio': dead_ratio or 0,
                'damage_given': dmg or 0,
                'dpm': dpm or 0
            })

        return {
            'round_id': round_id,
            'match_id': match_id,
            'round_number': round_number,
            'map_name': map_name,
            'round_date': round_date,
            'round_time': round_time,
            'actual_time': actual_time,
            'stats_duration_seconds': stats_duration_seconds,
            'time_limit': time_limit,
            'winner_team': winner_team,
            'defender_team': defender_team,
            'players': players
        }

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

        Since match_id format differs, we match on:
        - Same map_name
        - Same round_number
        - captured_at within 10 minutes of round_time
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
                WHERE round_id = ?
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

        # Parse round_time to datetime for comparison (supports multiple formats)
        round_datetime = self._parse_round_datetime(round_date, round_time)
        if not round_datetime:
            logger.warning(f"Could not parse round datetime: {round_date} {round_time}")
            return None

        # Query lua_round_teams with time window
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
            WHERE map_name = ?
              AND round_number = ?
            ORDER BY captured_at DESC
            LIMIT 5
        """
        rows = await self.db_adapter.fetch_all(query, (map_name, round_number))

        if not rows:
            return None

        # Find best match by time proximity
        best_match = None
        min_diff = timedelta(hours=24)

        for row in rows:
            (id_, match_id, rn, mn, start_unix, end_unix, duration,
             pause_sec, pause_count, end_reason, winner, defender, timelimit,
             warmup_sec, warmup_start, pause_events,
             surr_team, surr_caller, axis_score, allies_score, captured_at) = row

            # Build candidate timestamps (prefer round_end_unix / round_start_unix)
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

            # Fallback to captured_at if present
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

    def _parse_round_datetime(self, round_date: str, round_time: str) -> Optional[datetime]:
        """Parse round date/time from multiple known formats."""
        date_str = str(round_date).strip() if round_date is not None else ""
        time_str = str(round_time).strip() if round_time is not None else ""

        # Case 1: round_date already includes HHMMSS (YYYY-MM-DD-HHMMSS)
        if re.match(r"^\d{4}-\d{2}-\d{2}-\d{6}$", date_str):
            try:
                return datetime.strptime(date_str, "%Y-%m-%d-%H%M%S")
            except ValueError:
                pass

        # Case 2: round_date includes time with colons
        if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", date_str):
            try:
                return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

        # Case 3: round_time provided as HH:MM:SS
        if time_str and ":" in time_str:
            try:
                return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

        # Case 4: round_time provided as HHMMSS
        if time_str and re.match(r"^\d{6}$", time_str):
            try:
                return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H%M%S")
            except ValueError:
                pass

        return None

    def _build_comparison_embed(
        self,
        stats_data: Dict[str, Any],
        lua_data: Optional[Dict[str, Any]]
    ) -> discord.Embed:
        """
        Build Discord embed comparing stats file vs Lua timing.
        """
        map_name = stats_data['map_name']
        round_number = stats_data['round_number']

        # Third timing anchor: filename timestamp (round_date/round_time)
        file_dt = self._parse_round_datetime(stats_data.get('round_date'), stats_data.get('round_time'))
        file_unix = int(file_dt.timestamp()) if file_dt else None

        # Determine color based on data availability
        if lua_data:
            # Compare durations
            stats_duration = stats_data['stats_duration_seconds']
            lua_duration = lua_data.get('lua_duration_seconds', 0) or 0
            diff = abs(stats_duration - lua_duration) if lua_duration else 0

            if diff > 60:  # >1 minute difference
                color = discord.Color.red()  # Significant discrepancy
                status = "⚠️ DISCREPANCY"
            elif diff > 30:
                color = discord.Color.orange()
                status = "⚡ MINOR DIFF"
            else:
                color = discord.Color.green()
                status = "✅ ALIGNED"
        else:
            color = discord.Color.greyple()
            status = "❓ NO LUA DATA"

        embed = discord.Embed(
            title=f"📊 TIMING COMPARISON - {map_name} R{round_number}",
            description=f"**Status:** {status}\n\n"
                       f"**Timing Legend:**\n"
                       f"⏱ **Playtime** = Actual gameplay (pauses excluded)\n"
                       f"🔥 **Warmup** = Pre-round warmup phase\n"
                       f"🕐 **Wall-clock** = Total elapsed time (includes pauses + warmup)",
            color=color,
            timestamp=datetime.now()
        )

        # Stats file timing
        stats_duration = stats_data['stats_duration_seconds']
        stats_time_str = self._format_seconds(stats_duration)

        embed.add_field(
            name="📄 Stats File",
            value=f"Duration: **{stats_time_str}** ({stats_duration}s)\n"
                  f"Time limit: {stats_data.get('time_limit', 'N/A')}",
            inline=True
        )

        # Lua webhook timing
        if lua_data:
            lua_duration = lua_data.get('lua_duration_seconds', 0) or 0
            lua_time_str = self._format_seconds(lua_duration)
            warmup = lua_data.get('warmup_seconds', 0)
            pauses = lua_data.get('total_pause_seconds', 0)
            pause_count = lua_data.get('pause_count', 0)
            end_reason = normalize_end_reason(lua_data.get('end_reason', 'unknown'))
            confidence = lua_data.get('match_confidence', 'unknown')
            # Surrender info
            surr_team = lua_data.get('surrender_team', 0)
            surr_text = ""
            if surr_team:
                team_name = "Axis" if surr_team == 1 else "Allies"
                surr_caller = lua_data.get('surrender_caller', '')
                surr_text = f"\n🏳️ Surrender: {team_name}"
                if surr_caller:
                    surr_text += f" (by {surr_caller})"

            embed.add_field(
                name="🎮 Lua Webhook",
                value=f"Playtime: **{lua_time_str}** ({lua_duration}s)\n"
                      f"Warmup: {warmup}s | Pauses: {pause_count} ({pauses}s)\n"
                      f"End: {end_reason} | Match: {confidence}{surr_text}",
                inline=True
            )

            # Difference
            diff = stats_duration - lua_duration
            diff_str = f"+{diff}s" if diff > 0 else f"{diff}s"
            correction_factor = lua_duration / stats_duration if stats_duration > 0 else 1.0

            embed.add_field(
                name="📐 Difference",
                value=f"Stats - Lua = **{diff_str}**\n"
                      f"Correction: ×{correction_factor:.3f}",
                inline=True
            )
        else:
            embed.add_field(
                name="🎮 Lua Webhook",
                value="❌ No matching Lua data found\n"
                      "(Webhook may not have fired or data not stored)",
                inline=True
            )
            embed.add_field(
                name="📐 Difference",
                value="N/A - cannot compare",
                inline=True
            )

        # Filename timestamp (round_date/round_time) as 3rd source
        if file_dt and file_unix:
            file_value = f"Timestamp: **{file_dt.isoformat(sep=' ', timespec='seconds')}**\n"
            file_value += f"Unix: {file_unix}"
            if lua_data and lua_data.get('round_end_unix'):
                file_diff = abs(file_unix - int(lua_data.get('round_end_unix')))
                file_value += f"\nDiff vs Lua end: **{file_diff}s**"
            embed.add_field(
                name="🧭 Filename Timestamp",
                value=file_value,
                inline=True
            )

        # Per-player times (from stats file)
        players = stats_data.get('players', [])[:10]  # Top 10
        if players:
            player_lines = []
            mixed_or_unknown_count = 0
            for p in players:
                time_played = self._format_seconds(int(p['time_played_seconds']))
                time_dead = self._format_seconds(int(p['time_dead_seconds']))
                dead_pct = p.get('time_dead_ratio', 0)
                dpm = p.get('dpm', 0)
                name = p['name'][:12]  # Truncate name
                side_marker = p.get('side_marker', '[--]')
                side_state = p.get('side_state', 'unknown')
                if side_state in ('mixed', 'unknown'):
                    mixed_or_unknown_count += 1

                # If we have Lua correction, show corrected times
                if lua_data and stats_duration > 0:
                    lua_duration = lua_data.get('lua_duration_seconds', 0) or stats_duration
                    factor = lua_duration / stats_duration if stats_duration else 1.0
                    corrected_played = int(p['time_played_seconds'] * factor)
                    corrected_dead = int(p['time_dead_seconds'] * factor)
                    player_lines.append(
                        f"{side_marker} `{name:<12}` ⏱{time_played}→{self._format_seconds(corrected_played)} "
                        f"💀{time_dead}→{self._format_seconds(corrected_dead)} ({dead_pct:.0f}%) "
                        f"DPM:{dpm:.0f}"
                    )
                else:
                    player_lines.append(
                        f"{side_marker} `{name:<12}` ⏱{time_played} 💀{time_dead} ({dead_pct:.0f}%) DPM:{dpm:.0f}"
                    )

            legend_text = "[AX]=Axis | [AL]=Allies | [MX]/[--]=mixed or unknown"
            if mixed_or_unknown_count:
                legend_text += f" ({mixed_or_unknown_count} ambiguous)"
            player_lines.append("")
            player_lines.append(f"🧭 {legend_text}")

            embed.add_field(
                name=f"👥 Per-Player Times ({len(players)} shown)",
                value="\n".join(player_lines) if player_lines else "No players",
                inline=False
            )

        # Footer
        embed.set_footer(
            text=f"Round ID: {stats_data['round_id']} | "
                 f"Date: {stats_data['round_date']} {stats_data['round_time']}"
        )

        return embed

    def _parse_time_to_seconds(self, time_str: str) -> int:
        """Convert time string (MM:SS or seconds) to integer seconds."""
        if not time_str:
            return 0

        try:
            text = str(time_str).strip()
            if ':' in text:
                parts = text.split(':')
                if len(parts) == 2:
                    return int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            if '.' in text:
                minutes = float(text)
                return int(minutes * 60)
            return int(float(text))
        except (ValueError, TypeError):
            return 0

    def _format_seconds(self, seconds: int) -> str:
        """Format seconds as MM:SS string."""
        if seconds <= 0:
            return "0:00"
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"


async def setup(bot):
    """Setup function for loading as a service."""
    pass  # Service is initialized directly, not as a cog
