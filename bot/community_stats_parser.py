#!/usr/bin/env python3
"""
C0RNP0RN3.LUA Format Parser
Correctly parses the actual weapon format used by c0rnp0rn3.lua
"""

import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import discord

from bot.stats import StatsCalculator
from bot.core.round_contract import (
    normalize_side_value,
    score_confidence_state,
    derive_stopwatch_contract,
)

logger = logging.getLogger(__name__)

# =============================================================================
# FILENAME FORMAT: YYYY-MM-DD-HHMMSS-<map_name>-round-<N>.txt
# Example: 2025-10-02-232818-erdenberg_t2-round-2.txt
#
# The timestamp (first 17 characters) is used for:
# - Deduplication (file_tracker.py)
# - Round 1/Round 2 pairing (differential calculation)
# - Session identification (match_id generation)
#
# ROUND 2 DIFFERENTIAL CALCULATION:
# Round 2 files contain CUMULATIVE stats from both rounds.
# To get Round 2-only stats: R2_cumulative - R1 = R2_only
# =============================================================================

# =============================================================================
# R2-ONLY FIELDS (Jan 2026 Discovery)
# These fields in R2 stats files are ALREADY differential (R2-only values).
# ET:Legacy Lua resets these variables between rounds, so R2 file contains
# R2-only performance, NOT cumulative R1+R2 totals.
# DO NOT subtract R1 from these - use R2 value directly!
# =============================================================================
R2_ONLY_FIELDS = {
    # --- Originally identified (correct) ---
    'xp',                   # TAB[9] - XP THIS round
    'death_spree',          # TAB[11] - Death spree THIS round (topshots[2])
    'kill_assists',         # TAB[12] - Kill assists THIS round (topshots[3])
    'headshot_kills',       # TAB[14] - Headshot kills THIS round (topshots[5])
    'objectives_stolen',    # TAB[15] - Objectives stolen THIS round (topshots[6])
    'dynamites_planted',    # TAB[17] - Dynamites planted THIS round (topshots[8])
    'times_revived',        # TAB[19] - Times revived THIS round (topshots[10])
    'useful_kills',         # TAB[27] - Useful kills THIS round (topshots[15])
    'revives_given',        # TAB[37] - Revives given THIS round (topshots[20])
    # --- Lua resets these in et_InitGame() (topshots[]/multikills[] arrays) ---
    'killing_spree',        # TAB[10] - topshots[1]
    'kill_steals',          # TAB[13] - topshots[4]
    'objectives_returned',  # TAB[16] - topshots[7]
    'dynamites_defused',    # TAB[18] - topshots[9]
    'denied_playtime',      # TAB[28] - topshots[16]
    'multikill_2x',         # TAB[29] - multikills[1]
    'multikill_3x',         # TAB[30] - multikills[2]
    'multikill_4x',         # TAB[31] - multikills[3]
    'multikill_5x',         # TAB[32] - multikills[4]
    'multikill_6x',         # TAB[33] - multikills[5]
    'useless_kills',        # TAB[34] - topshots[17]
    'full_selfkills',       # TAB[35] - topshots[18]
    'repairs_constructions', # TAB[36] - topshots[19]
    'time_dead_minutes',    # TAB[25] - from death_time_total (resets per round)
}

# C0RNP0RN3.LUA weapon enumeration (the actual format used)
C0RNP0RN3_WEAPONS = {
    0: "WS_KNIFE",
    1: "WS_KNIFE_KBAR",
    2: "WS_LUGER",
    3: "WS_COLT",
    4: "WS_MP40",
    5: "WS_THOMPSON",
    6: "WS_STEN",
    7: "WS_FG42",
    8: "WS_PANZERFAUST",
    9: "WS_BAZOOKA",
    10: "WS_FLAMETHROWER",
    11: "WS_GRENADE",
    12: "WS_MORTAR",
    13: "WS_MORTAR2",
    14: "WS_DYNAMITE",
    15: "WS_AIRSTRIKE",
    16: "WS_ARTILLERY",
    17: "WS_SATCHEL",
    18: "WS_GRENADELAUNCHER",
    19: "WS_LANDMINE",
    20: "WS_MG42",
    21: "WS_BROWNING",
    22: "WS_CARBINE",
    23: "WS_KAR98",
    24: "WS_GARAND",
    25: "WS_K43",
    26: "WS_MP34",
    27: "WS_SYRINGE",
}


def _parse_side_fields(header_parts: List[str]) -> tuple[int, int, Dict[str, Any]]:
    """
    Parse defender/winner side fields and return diagnostics for fallback reasons.

    Current parser defaults are preserved for compatibility:
    - defender_team defaults to 1 (Axis)
    - winner_team defaults to 0 (unknown)
    """
    defender_raw = header_parts[4].strip() if len(header_parts) > 4 else None
    winner_raw = header_parts[5].strip() if len(header_parts) > 5 else None

    diagnostics = {
        "header_field_count": len(header_parts),
        "defender_team_raw": defender_raw,
        "winner_team_raw": winner_raw,
        "reasons": [],
    }

    defender_team = 1
    if not defender_raw:
        diagnostics["reasons"].append("defender_missing")
    elif not defender_raw.isdigit():
        diagnostics["reasons"].append("defender_non_numeric")
    else:
        defender_team = int(defender_raw)
        if defender_team not in (1, 2):
            diagnostics["reasons"].append("defender_out_of_range")

    winner_team = 0
    if not winner_raw:
        diagnostics["reasons"].append("winner_missing")
    elif not winner_raw.isdigit():
        diagnostics["reasons"].append("winner_non_numeric")
    else:
        winner_team = int(winner_raw)
        if winner_team not in (0, 1, 2):
            diagnostics["reasons"].append("winner_out_of_range")

    return defender_team, winner_team, diagnostics


class C0RNP0RN3StatsParser:
    """Parse stats files generated by c0rnp0rn3.lua with stylish Discord formatting"""

    def __init__(self, round_match_window_minutes: int = 45):
        """
        Initialize the stats parser.

        Args:
            round_match_window_minutes: Maximum time gap (in minutes) between R1 and R2
                                        for them to be considered part of the same match.
                                        Default 45 min. Should be less than session_gap_minutes (60).
        """
        # R1-R2 matching window (configurable, was hardcoded as 30)
        self.round_match_window_minutes = round_match_window_minutes

        # Weapon emojis for Discord formatting
        self.weapon_emojis = {
            'WS_MP40': '🔫',
            'WS_THOMPSON': '⚡',
            'WS_LUGER': '🎯',
            'WS_COLT': '🔰',
            'WS_PANZERFAUST': '🚀',
            'WS_GRENADELAUNCHER': '💥',
            'WS_GRENADE': '💣',
            'WS_KNIFE': '🗡️',
            'WS_SYRINGE': '💉',
            'WS_FG42': '🎪',
            'WS_KAR98': '🎯',
            'WS_GARAND': '⭐',
            'WS_STEN': '🔧',
        }

        self.team_colors = {1: 0xFF4444, 2: 0x4444FF}  # Axis - Red  # Allies - Blue

        # Omni-bot detection (prefix can be overridden via BOT_NAME_REGEX)
        bot_regex = os.getenv("BOT_NAME_REGEX", r"^\[BOT\]")
        try:
            self.bot_name_pattern = re.compile(bot_regex, re.IGNORECASE)
        except re.error:
            self.bot_name_pattern = re.compile(r"^\[BOT\]", re.IGNORECASE)

    def strip_color_codes(self, text: str) -> str:
        """Remove ET Legacy color codes from text (^0-^9, ^a-^z, etc.)"""
        if not text:
            return ""
        return re.sub(r'\^[0-9a-zA-Z]', '', text)

    def is_bot_name(self, clean_name: str) -> bool:
        """Detect Omni-bot names via prefix (default: [BOT])"""
        if not clean_name:
            return False
        return bool(self.bot_name_pattern.match(clean_name.strip()))

    def parse_time_to_seconds(self, time_str: str) -> int:
        """Convert time string (MM:SS or M:SS) to seconds"""
        try:
            if not time_str:
                return 0
            text = str(time_str).strip()
            if ':' in text:
                parts = text.split(':')
                minutes = int(parts[0])
                seconds = int(parts[1])
                return minutes * 60 + seconds
            if '.' in text:
                # Decimal minutes (e.g., "20.00", "5.25")
                minutes = float(text)
                return int(minutes * 60)
            return int(text)
        except BaseException:
            return 0

    def format_accuracy_bar(self, accuracy: float) -> str:
        """Create a visual accuracy bar with blocks"""
        filled = int(accuracy / 10)  # 10% per bar
        empty = 10 - filled
        return f"{'█' * filled}{'░' * empty} {accuracy:.1f}%"

    def format_kd_ratio(self, kills: int, deaths: int) -> str:
        """Format K/D ratio with performance indicators"""
        kd = StatsCalculator.calculate_kd(kills, deaths)

        if kd >= 2.0:
            indicator = "🔥"
        elif kd >= 1.5:
            indicator = "⚡"
        elif kd >= 1.0:
            indicator = "⚔️"
        else:
            indicator = "📈"

        return f"{indicator} {kills}K/{deaths}D ({kd:.2f})"

    def create_stylish_round_embed(self, stats_data: Dict[str, Any]):
        """Create a compact icon-based Discord embed for round results (matches !last_session style)"""

        map_name = stats_data.get('map_name', 'Unknown')
        round_num = stats_data.get('round_num', 1)
        outcome = stats_data.get('round_outcome', 'Unknown')
        mvp_name = stats_data.get('mvp', 'Unknown')
        players = stats_data.get('players', [])
        actual_time = stats_data.get('actual_time', 'Unknown')

        # Choose embed color based on outcome
        if outcome == 'Fullhold':
            color = 0xFF6B35  # Orange for fullhold
            outcome_emoji = '[D]'
        else:
            color = 0x00D2FF  # Blue for completed
            outcome_emoji = '[V]'

        # Create header description
        header = f"🗺️ **{map_name}** • Round {round_num} • {outcome_emoji} {outcome} • ⏱️ {actual_time}"

        embed = discord.Embed(
            title="",
            description=header,
            color=color,
            timestamp=discord.utils.utcnow(),
        )

        # Add top 3 performers in compact format
        if players:
            sorted_players = sorted(players, key=lambda x: x['kd_ratio'], reverse=True)
            top_3 = sorted_players[:3]

            medals = ["🥇", "🥈", "🥉"]

            for i, player in enumerate(top_3):
                medal = medals[i] if i < 3 else "🏅"
                team_indicator = "🔴" if player['team'] == 1 else "🔵"

                # Get stats from objective_stats
                obj_stats = player.get('objective_stats', {})

                # Basic stats
                name = player['name']
                kills = player.get('kills', 0)
                deaths = player.get('deaths', 0)
                kd_ratio = player.get('kd_ratio', 0)

                # Extended stats
                gibs = obj_stats.get('gibs', 0)
                revives_given = obj_stats.get('revives_given', 0)
                times_revived = obj_stats.get('times_revived', 0)
                damage_given = obj_stats.get('damage_given', 0)
                damage_received = obj_stats.get('damage_received', 0)
                useful_kills = obj_stats.get('useful_kills', 0)
                dpm = obj_stats.get('dpm', 0)
                time_dead_mins = obj_stats.get('time_dead_minutes', 0)
                denied_mins = obj_stats.get('denied_playtime', 0) / 60.0 if obj_stats.get('denied_playtime') else 0
                headshots = obj_stats.get('headshot_kills', 0)

                # Multikills
                double_kills = obj_stats.get('multikill_2x', 0)
                triple_kills = obj_stats.get('multikill_3x', 0)
                quad_kills = obj_stats.get('multikill_4x', 0)
                penta_kills = obj_stats.get('multikill_5x', 0)
                mega_kills = obj_stats.get('multikill_6x', 0)

                # Weapon stats for accuracy
                weapon_stats = player.get('weapon_stats', {})
                total_hits = sum(w['hits'] for w in weapon_stats.values())
                total_shots = sum(w['shots'] for w in weapon_stats.values())
                acc = (total_hits / total_shots * 100) if total_shots > 0 else 0
                hs_rate = (headshots / total_hits * 100) if total_hits > 0 else 0

                # Format damage (show in K if over 1000)
                dmg_given_display = f"{damage_given/1000:.1f}K" if damage_given >= 1000 else f"{damage_given}"
                dmg_recv_display = f"{damage_received/1000:.1f}K" if damage_received >= 1000 else f"{damage_received}"

                # Format times
                time_dead_display = f"{int(time_dead_mins)}:{int((time_dead_mins % 1) * 60):02d}"
                denied_display = f"{int(denied_mins)}:{int((denied_mins % 1) * 60):02d}"

                # Build player field (4-line compact format)
                mvp_badge = " (MVP)" if name == mvp_name else ""
                player_text = f"{medal} {team_indicator} **{name}**{mvp_badge}\n"
                player_text += f"⏱️ `{actual_time}` • 💪 `{dpm:.0f} DPM` • 📊 `{dmg_given_display}⬆/{dmg_recv_display}⬇` • 🎯 `{acc:.1f}% ACC ({total_hits}/{total_shots})`\n"
                player_text += f"⚔️ `{kills}K/{deaths}D/{gibs}G ({kd_ratio:.2f} KD)` • 💉 `{revives_given}↑/{times_revived}↓` • 🎯 `{useful_kills} UK` • 📈 `{headshots} HS ({hs_rate:.1f}%)`\n"

                # Line 4: Multikills (conditional) + death stats
                multikills_text = ""
                if double_kills or triple_kills or quad_kills or penta_kills or mega_kills:
                    multikill_parts = []
                    if double_kills: multikill_parts.append(f"{double_kills} DOUBLE")
                    if triple_kills: multikill_parts.append(f"{triple_kills} TRIPLE")
                    if quad_kills: multikill_parts.append(f"{quad_kills} QUAD")
                    if penta_kills: multikill_parts.append(f"{penta_kills} PENTA")
                    if mega_kills: multikill_parts.append(f"{mega_kills} MEGA")
                    multikills_text = f"🔥 `{' • '.join(multikill_parts)}` • "

                player_text += f"{multikills_text}💀 `{time_dead_display}` • ⏳ `{denied_display}`"

                embed.add_field(name="\u200b", value=player_text, inline=False)

        embed.set_footer(text="ET:Legacy Community Stats • c0rnp0rn3.lua")

        return embed

    def create_detailed_player_stats(self, player: Dict[str, Any]) -> str:
        """Create detailed player stats in the beloved format"""

        name = player['name']
        team = player['team']
        kills = player['kills']
        deaths = player['deaths']
        kd_ratio = player['kd_ratio']
        headshots = player.get('headshots', 0)
        damage_given = player.get('damage_given', 0)
        damage_received = player.get('damage_received', 0)

        # Build the detailed stats string
        stats_text = f"🎯 {name} (Team {team})\n"
        stats_text += f"   Overall: {kills}K/{deaths}D (K/D: {kd_ratio:.2f})\n"
        stats_text += f"   Total Headshots: {headshots}\n"
        stats_text += f"   💊 Damage: {damage_given} dealt / {damage_received} received\n"

        # Add weapon performance section
        weapon_stats = player.get('weapon_stats', {})
        if weapon_stats:
            stats_text += "   🔫 Weapon Performance:\n"

            # Focus on key weapons
            focus_weapons = [
                'WS_MP40',
                'WS_THOMPSON',
                'WS_LUGER',
                'WS_COLT',
                'WS_PANZERFAUST',
                'WS_GRENADELAUNCHER',
            ]

            for weapon in focus_weapons:
                if weapon in weapon_stats:
                    w = weapon_stats[weapon]
                    if w['shots'] > 0 or w['kills'] > 0:
                        weapon_name = weapon.replace('WS_', '')
                        # Build a safe formatted line (avoid multi-line f-string that was broken)
                        stats_text += (
                            f"      {weapon_name}: {w['accuracy']:.1f}% acc "
                            f"({w['hits']}/{w['shots']}) | {w['kills']}K/{w['deaths']}D | {w['headshots']} HS\n"
                        )

        stats_text += "-" * 60
        return stats_text

    def parse_stats_file(self, file_path: str) -> Dict[str, Any]:
        """Parse c0rnp0rn3.lua stats file with Round 2 differential calculation"""
        try:
            # Check if this is a Round 2 file and needs differential calculation
            if self.is_round_2_file(file_path):
                return self.parse_round_2_with_differential(file_path)
            else:
                return self.parse_regular_stats_file(file_path)

        except Exception as e:
            logger.error(f"Error parsing stats file {file_path}: {e}")
            return self._get_error_result(f"exception: {str(e)}")

    def is_round_2_file(self, file_path: str) -> bool:
        """Detect if this is a Round 2 file by filename pattern"""
        filename = os.path.basename(file_path)
        return "-round-2.txt" in filename

    def find_corresponding_round_1_file(self, round_2_file_path: str) -> Optional[str]:
        """
        Find the corresponding Round 1 file for a Round 2 file

        Strategy:
        1. Try EXACT match (same timestamp) - for same-session rounds
        2. Try same-day match (within 30 min before) - for most cases
        3. Try previous-day match (midnight-crossing) - for sessions crossing midnight
        """
        import glob
        from datetime import datetime, timedelta

        filename = os.path.basename(round_2_file_path)
        directory = os.path.dirname(round_2_file_path)

        # Extract date, time, map from Round 2 filename: YYYY-MM-DD-HHMMSS-mapname-round-2.txt
        parts = filename.split('-')
        if len(parts) < 6:
            return None

        date = '-'.join(parts[:3])  # YYYY-MM-DD
        time_part = parts[3]  # HHMMSS
        map_name = '-'.join(parts[4:-2])  # everything between time and "round-2.txt"

        # Check both the same directory and local_stats directory
        search_dirs = [directory]
        if not directory.endswith("local_stats"):
            search_dirs.append("local_stats")

        # STEP 1: Try EXACT match (same timestamp prefix) - rounds from same session
        exact_pattern = f"{date}-{time_part}-{map_name}-round-1.txt"
        logger.debug(f"  → Looking for exact match: {exact_pattern}")

        for search_dir in search_dirs:
            if os.path.exists(search_dir):
                exact_path = os.path.join(search_dir, exact_pattern)
                if os.path.exists(exact_path):
                    logger.debug("  → ✅ Found exact match (same session)")
                    return exact_path

        # STEP 2: Try same-day match (different timestamp, same date)
        potential_files = []
        same_day_pattern = f"{date}-*-{map_name}-round-1.txt"
        logger.debug(f"  → Looking for same-day match: {same_day_pattern}")

        for search_dir in search_dirs:
            if os.path.exists(search_dir):
                pattern_path = os.path.join(search_dir, same_day_pattern)
                found = glob.glob(pattern_path)
                if found:
                    logger.debug(f"  → Found {len(found)} same-day Round 1 file(s)")
                potential_files.extend(found)

        # STEP 3: If no same-day files, check previous date (midnight-crossing)
        if not potential_files:
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                prev_date = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
                prev_pattern = f"{prev_date}-*-{map_name}-round-1.txt"

                logger.debug(f"  → No same-day found, checking previous date: {prev_pattern}")

                for search_dir in search_dirs:
                    if os.path.exists(search_dir):
                        pattern_path = os.path.join(search_dir, prev_pattern)
                        found = glob.glob(pattern_path)
                        if found:
                            logger.debug(f"  → Found {len(found)} previous-day file(s) (midnight-crossing)")
                        potential_files.extend(found)
            except ValueError:  # nosec B110
                pass  # Invalid date format, skip this file

        if not potential_files:
            return None

        # Find the best Round 1: closest before Round 2, within 30 minutes
        try:
            r2_datetime = datetime.strptime(f"{date} {time_part}", '%Y-%m-%d %H%M%S')
        except (ValueError, IndexError):
            return None

        best_r1_file = None
        best_r1_datetime = None
        # Use configurable window (default 45 min, was hardcoded as 30)
        max_time_diff = self.round_match_window_minutes

        for r1_file in potential_files:
            r1_filename = os.path.basename(r1_file)
            r1_parts = r1_filename.split('-')
            if len(r1_parts) >= 4:
                try:
                    r1_date = '-'.join(r1_parts[:3])  # YYYY-MM-DD
                    r1_time = r1_parts[3]  # HHMMSS
                    r1_datetime = datetime.strptime(f"{r1_date} {r1_time}", '%Y-%m-%d %H%M%S')

                    # Round 1 must be BEFORE Round 2
                    if r1_datetime < r2_datetime:
                        time_diff = (r2_datetime - r1_datetime).total_seconds() / 60

                        # Accept if within time window
                        if time_diff <= max_time_diff:
                            if best_r1_datetime is None or r1_datetime > best_r1_datetime:
                                best_r1_datetime = r1_datetime
                                best_r1_file = r1_file
                                logger.debug(f"  → ✅ Match found: {r1_filename} ({time_diff:.1f} min before)")
                        else:
                            logger.debug(f"  → ❌ Rejected: {r1_filename} ({time_diff:.1f} min gap - too old)")
                except ValueError:
                    continue

        return best_r1_file

    def parse_round_2_with_differential(self, round_2_file_path: str) -> Dict[str, Any]:
        """
        Parse Round 2 file with differential calculation to get Round 2-only stats

        ALSO stores the cumulative data as 'match_summary' for easy access to total match stats.
        """
        logger.info(f"[R2] Detected Round 2 file: {os.path.basename(round_2_file_path)}")

        # Find corresponding Round 1 file
        round_1_file_path = self.find_corresponding_round_1_file(round_2_file_path)
        if not round_1_file_path:
            logger.warning(f"Could not find Round 1 file for {os.path.basename(round_2_file_path)}")
            logger.warning("   Parsing as regular file (treating as Round 2)")
            # Parse as regular file but force round_num to 2
            result = self.parse_regular_stats_file(round_2_file_path)
            result['round_num'] = 2  # Force Round 2 even if header says otherwise
            return result

        logger.info(f"[R1] Found Round 1 file: {os.path.basename(round_1_file_path)}")

        # Parse both files
        round_1_result = self.parse_regular_stats_file(round_1_file_path)
        round_2_cumulative_result = self.parse_regular_stats_file(round_2_file_path)

        if not round_1_result['success'] or not round_2_cumulative_result['success']:
            logger.error("Error parsing one of the round files")
            return self._get_error_result("failed to parse round files")

        # Calculate differential stats (Round 2 ONLY = Round 2 cumulative - Round 1)
        round_2_only_result = self.calculate_round_2_differential(
            round_1_result, round_2_cumulative_result
        )

        # 🆕 ATTACH R1 FILENAME so importer can use R1's timestamp for match_id
        round_2_only_result['r1_filename'] = os.path.basename(round_1_file_path)

        # 🆕 ATTACH MATCH SUMMARY (cumulative R2 data) to the result
        # This will be stored as round_number=0 for easy querying
        match_summary = round_2_cumulative_result.copy()
        match_summary['round_num'] = 0  # Special round number for match summary
        match_summary['is_match_summary'] = True

        # Attach match summary to the Round 2 differential result
        round_2_only_result['match_summary'] = match_summary

        logger.info(
            f"[OK] Successfully calculated Round 2-only stats for {len(round_2_only_result['players'])} players"
        )
        logger.debug("[MATCH] Attached match summary with cumulative stats from both rounds")
        return round_2_only_result

    def _detect_player_counter_reset(
        self,
        r1_player: Dict[str, Any],
        r2_player: Dict[str, Any],
    ) -> List[str]:
        """
        Detect per-player non-cumulative R2 counters.

        In cumulative mode, R2 values should never be lower than R1 for the same player.
        If they drop, assume this player reset/reconnected and use safe R2-raw fallback.
        """
        dropped_fields: List[str] = []

        r1_obj = r1_player.get('objective_stats', {}) or {}
        r2_obj = r2_player.get('objective_stats', {}) or {}

        checks = [
            ("kills", r1_player.get('kills', 0), r2_player.get('kills', 0)),
            ("deaths", r1_player.get('deaths', 0), r2_player.get('deaths', 0)),
            ("damage_given", r1_player.get('damage_given', 0), r2_player.get('damage_given', 0)),
            ("damage_received", r1_player.get('damage_received', 0), r2_player.get('damage_received', 0)),
            (
                "objective.time_played_minutes",
                r1_obj.get('time_played_minutes', 0),
                r2_obj.get('time_played_minutes', 0),
            ),
            (
                "objective.damage_given",
                r1_obj.get('damage_given', 0),
                r2_obj.get('damage_given', 0),
            ),
            (
                "objective.damage_received",
                r1_obj.get('damage_received', 0),
                r2_obj.get('damage_received', 0),
            ),
        ]

        for field_name, r1_value, r2_value in checks:
            try:
                if float(r2_value) < float(r1_value):
                    dropped_fields.append(field_name)
            except Exception:
                continue

        return dropped_fields

    def calculate_round_2_differential(
        self, round_1_data: Dict[str, Any], round_2_cumulative_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate Round 2-only stats by subtracting Round 1 from Round 2 cumulative"""

        # Create player lookup for Round 1 stats
        round_1_players = {player['name']: player for player in round_1_data['players']}

        round_2_only_players = []

        for r2_player in round_2_cumulative_data['players']:
            player_name = r2_player['name']
            r1_player = round_1_players.get(player_name)

            if not r1_player:
                # Player only in Round 2, use cumulative stats as-is
                # Keep raw time fields for validation/logging.
                r2_copy = r2_player.copy()
                r2_obj = r2_player.get('objective_stats', {})
                r2_copy['objective_stats_raw'] = {
                    'time_played_minutes_r2': r2_obj.get('time_played_minutes', 0),
                    'time_dead_minutes_r2': r2_obj.get('time_dead_minutes', 0),
                    'time_dead_ratio_r2': r2_obj.get('time_dead_ratio', 0),
                    'denied_playtime_r2': r2_obj.get('denied_playtime', 0),
                }
                round_2_only_players.append(r2_copy)
                continue

            reset_fields = self._detect_player_counter_reset(r1_player, r2_player)
            use_r2_raw = len(reset_fields) > 0
            if use_r2_raw:
                r1_obj = r1_player.get('objective_stats', {}) or {}
                r2_obj = r2_player.get('objective_stats', {}) or {}
                logger.warning(
                    "[R2 RESET FALLBACK] player=%s fields=%s mode=use_r2_raw "
                    "r1_time=%.2f r2_time=%.2f",
                    player_name,
                    ",".join(reset_fields),
                    float(r1_obj.get('time_played_minutes', 0) or 0),
                    float(r2_obj.get('time_played_minutes', 0) or 0),
                )

            # Calculate differential for this player
            kills = max(0, r2_player['kills']) if use_r2_raw else max(0, r2_player['kills'] - r1_player['kills'])
            deaths = max(0, r2_player['deaths']) if use_r2_raw else max(0, r2_player['deaths'] - r1_player['deaths'])
            headshots = (
                max(0, r2_player.get('headshots', 0))
                if use_r2_raw
                else max(0, r2_player.get('headshots', 0) - r1_player.get('headshots', 0))
            )
            damage_given = (
                max(0, r2_player.get('damage_given', 0))
                if use_r2_raw
                else max(0, r2_player.get('damage_given', 0) - r1_player.get('damage_given', 0))
            )
            damage_received = (
                max(0, r2_player.get('damage_received', 0))
                if use_r2_raw
                else max(0, r2_player.get('damage_received', 0) - r1_player.get('damage_received', 0))
            )

            differential_player = {
                # FIX: Include GUID for database operations
                'guid': r2_player.get('guid', 'UNKNOWN'),
                'name': player_name,
                'team': r2_player['team'],
                'kills': kills,
                'deaths': deaths,
                'headshots': headshots,
                'damage_given': damage_given,
                'damage_received': damage_received,
                'weapon_stats': {},
                'objective_stats': {},  # Will populate below
                'r2_counter_reset_fallback': use_r2_raw,
                'r2_counter_reset_fields': reset_fields,
            }

            # FIX: Preserve objective_stats from Round 2 cumulative (includes time!)
            # For Round 2, we want the differential of objective stats
            r2_obj = r2_player.get('objective_stats', {})
            r1_obj = r1_player.get('objective_stats', {})

            # Calculate differential objective stats
            # CRITICAL FIX (Jan 30, 2026): ET:Legacy has MIXED field behavior!
            # - Some fields are cumulative (R1+R2 total) - need subtraction
            # - Some fields are R2-only (already differential) - use directly
            for key in r2_obj:
                if key in R2_ONLY_FIELDS:
                    # These fields are ALREADY R2-only in the stats file
                    # ET:Legacy Lua resets these variables between rounds
                    # DO NOT subtract R1 - use R2 value directly!
                    differential_player['objective_stats'][key] = r2_obj[key]
                elif key == 'time_played_minutes':
                    # Time played IS cumulative - subtract R1 to get R2-only
                    r2_time = r2_obj.get('time_played_minutes', 0)
                    r1_time = r1_obj.get('time_played_minutes', 0)
                    diff_minutes = max(0, r2_time) if use_r2_raw else max(0, r2_time - r1_time)
                    differential_player['objective_stats']['time_played_minutes'] = diff_minutes
                elif isinstance(r2_obj[key], (int, float)):
                    # Cumulative numeric fields - subtract R1 to get R2-only value
                    if use_r2_raw:
                        differential_player['objective_stats'][key] = max(0, r2_obj.get(key, 0))
                    else:
                        differential_player['objective_stats'][key] = max(
                            0, r2_obj.get(key, 0) - r1_obj.get(key, 0)
                        )
                else:
                    # For non-numeric, use R2 value
                    differential_player['objective_stats'][key] = r2_obj[key]

            # Preserve raw (cumulative) time fields for validation/logging
            differential_player['objective_stats_raw'] = {
                'time_played_minutes_r1': r1_obj.get('time_played_minutes', 0),
                'time_played_minutes_r2': r2_obj.get('time_played_minutes', 0),
                'time_dead_minutes_r1': r1_obj.get('time_dead_minutes', 0),
                'time_dead_minutes_r2': r2_obj.get('time_dead_minutes', 0),
                'time_dead_ratio_r1': r1_obj.get('time_dead_ratio', 0),
                'time_dead_ratio_r2': r2_obj.get('time_dead_ratio', 0),
                'denied_playtime_r1': r1_obj.get('denied_playtime', 0),
                'denied_playtime_r2': r2_obj.get('denied_playtime', 0),
            }

            # Recompute time_dead_ratio after differential (avoid ratio subtraction)
            diff_time_minutes = differential_player['objective_stats'].get('time_played_minutes', 0)
            diff_dead_minutes = differential_player['objective_stats'].get('time_dead_minutes', 0)
            if diff_time_minutes and diff_time_minutes > 0:
                differential_player['objective_stats']['time_dead_ratio'] = round(
                    (diff_dead_minutes / diff_time_minutes) * 100, 1
                )
            else:
                differential_player['objective_stats']['time_dead_ratio'] = 0.0

            # NEW: Calculate time in SECONDS for R2 differential
            # Use time from objective_stats (lua-rounded minutes)
            diff_minutes = diff_time_minutes
            diff_seconds = int(diff_minutes * 60)  # Convert minutes to seconds

            differential_player['time_played_seconds'] = diff_seconds
            differential_player['time_played_minutes'] = diff_minutes  # Backward compat

            # Create time_display (MM:SS format)
            minutes = diff_seconds // 60
            seconds = diff_seconds % 60
            differential_player['time_display'] = f"{minutes}:{seconds:02d}"

            # Calculate differential weapon stats
            for weapon_name, r2_weapon in r2_player.get('weapon_stats', {}).items():
                r1_weapon = r1_player.get('weapon_stats', {}).get(
                    weapon_name, {'hits': 0, 'shots': 0, 'kills': 0, 'deaths': 0, 'headshots': 0}
                )

                if use_r2_raw:
                    differential_weapon = {
                        'hits': max(0, r2_weapon.get('hits', 0)),
                        'shots': max(0, r2_weapon.get('shots', 0)),
                        'kills': max(0, r2_weapon.get('kills', 0)),
                        'deaths': max(0, r2_weapon.get('deaths', 0)),
                        'headshots': max(0, r2_weapon.get('headshots', 0)),
                    }
                else:
                    differential_weapon = {
                        'hits': max(0, r2_weapon['hits'] - r1_weapon['hits']),
                        'shots': max(0, r2_weapon['shots'] - r1_weapon['shots']),
                        'kills': max(0, r2_weapon['kills'] - r1_weapon['kills']),
                        'deaths': max(0, r2_weapon['deaths'] - r1_weapon['deaths']),
                        'headshots': max(0, r2_weapon['headshots'] - r1_weapon['headshots']),
                    }

                # Calculate accuracy for differential stats
                if differential_weapon['shots'] > 0:
                    differential_weapon['accuracy'] = (
                        differential_weapon['hits'] / differential_weapon['shots']
                    ) * 100
                else:
                    differential_weapon['accuracy'] = 0.0

                differential_player['weapon_stats'][weapon_name] = differential_weapon

            # Calculate K/D ratio for differential stats
            if differential_player['deaths'] > 0:
                differential_player['kd_ratio'] = (
                    differential_player['kills'] / differential_player['deaths']
                )
            else:
                differential_player['kd_ratio'] = differential_player['kills']

            # Calculate DPM using R2 differential time (in SECONDS!)
            diff_seconds = differential_player.get('time_played_seconds', 0)
            if diff_seconds > 0:
                # DPM = (damage * 60) / seconds
                differential_player['dpm'] = (
                    differential_player['damage_given'] * 60
                ) / diff_seconds
            else:
                differential_player['dpm'] = 0.0

            # Calculate efficiency for differential stats
            total_kills = differential_player['kills']
            total_deaths = differential_player['deaths']
            differential_player['efficiency'] = (
                total_kills / (total_kills + total_deaths) * 100
                if (total_kills + total_deaths) > 0
                else 0
            )

            # Calculate overall accuracy from weapon stats differential
            total_hits = sum(w.get('hits', 0) for w in differential_player['weapon_stats'].values())
            total_shots = sum(w.get('shots', 0) for w in differential_player['weapon_stats'].values())
            differential_player['accuracy'] = (total_hits / total_shots * 100) if total_shots > 0 else 0.0
            differential_player['shots_total'] = total_shots
            differential_player['hits_total'] = total_hits

            # FIX: Recalculate headshots from differential weapon stats
            # Don't use the subtracted value from line 443, use the sum of differential weapons
            total_headshots = sum(w.get('headshots', 0) for w in differential_player['weapon_stats'].values())
            differential_player['headshots'] = total_headshots

            diff_time_minutes = differential_player['objective_stats'].get('time_played_minutes', 0)
            diff_dead_minutes = differential_player['objective_stats'].get('time_dead_minutes', 0)

            # [TIME DEBUG] Log Round 2 differential values + raw cumulative for validation
            diff_denied = differential_player['objective_stats'].get('denied_playtime', 0)
            raw = differential_player.get('objective_stats_raw', {})
            logger.info(
                f"[TIME DEBUG] {player_name} R2 DIFF: "
                f"played={diff_time_minutes:.2f}m dead={diff_dead_minutes:.2f}m "
                f"ratio={differential_player['objective_stats'].get('time_dead_ratio', 0):.1f}% "
                f"denied={diff_denied}s | "
                f"RAW R1: played={raw.get('time_played_minutes_r1', 0):.2f}m "
                f"dead={raw.get('time_dead_minutes_r1', 0):.2f}m "
                f"ratio={raw.get('time_dead_ratio_r1', 0):.1f}% denied={raw.get('denied_playtime_r1', 0)}s | "
                f"RAW R2: played={raw.get('time_played_minutes_r2', 0):.2f}m "
                f"dead={raw.get('time_dead_minutes_r2', 0):.2f}m "
                f"ratio={raw.get('time_dead_ratio_r2', 0):.1f}% denied={raw.get('denied_playtime_r2', 0)}s"
            )

            round_2_only_players.append(differential_player)

        # Calculate new MVP based on Round 2-only stats
        mvp = self.calculate_mvp(round_2_only_players)

        # Return Round 2-only result with proper metadata
        # NOTE: We keep winner_team for R2 to support header-based scoring.
        score_confidence = score_confidence_state(
            round_2_cumulative_data.get('defender_team'),
            round_2_cumulative_data.get('winner_team'),
            reasons=(round_2_cumulative_data.get('side_parse_diagnostics', {}) or {}).get('reasons', []),
            fallback_used=False,
        )
        stopwatch_contract = derive_stopwatch_contract(
            2,
            round_2_cumulative_data.get('map_time'),
            round_2_cumulative_data.get('actual_time'),
        )
        return {
            'success': True,
            'map_name': round_2_cumulative_data['map_name'],
            'round_num': 2,  # Always Round 2
            'defender_team': round_2_cumulative_data['defender_team'],
            'winner_team': round_2_cumulative_data.get('winner_team', 0),
            'side_parse_diagnostics': round_2_cumulative_data.get('side_parse_diagnostics', {}),
            'score_confidence': score_confidence,
            'map_time': round_2_cumulative_data['map_time'],
            'actual_time': round_2_cumulative_data['actual_time'],
            'round_outcome': round_2_cumulative_data['round_outcome'],
            'round_stopwatch_state': stopwatch_contract['round_stopwatch_state'],
            'time_to_beat_seconds': stopwatch_contract['time_to_beat_seconds'],
            'next_timelimit_minutes': stopwatch_contract['next_timelimit_minutes'],
            'players': round_2_only_players,
            'mvp': mvp,
            'total_players': len(round_2_only_players),
            'timestamp': datetime.now().isoformat(),
            'differential_calculation': True,  # Flag to indicate this was calculated
        }

    def parse_regular_stats_file(self, file_path: str) -> Dict[str, Any]:
        """Parse c0rnp0rn3.lua stats file (original implementation)"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            if len(lines) < 2:
                return self._get_error_result("insufficient lines")

            # Parse header
            header_line = lines[0].strip()
            header_parts = header_line.split('\\')

            if len(header_parts) < 8:
                return self._get_error_result("invalid header format")

            header_parts[0]
            map_name = header_parts[1]
            header_parts[2]
            round_num = int(header_parts[3]) if header_parts[3].isdigit() else 1
            defender_team, winner_team, side_parse_diagnostics = _parse_side_fields(header_parts)
            map_time = header_parts[6]
            actual_time = header_parts[7] if len(header_parts) > 7 else "Unknown"

            if side_parse_diagnostics["reasons"]:
                logger.warning(
                    "[SIDE DIAG] map=%s round=%s defender_raw=%s winner_raw=%s reasons=%s",
                    map_name,
                    round_num,
                    side_parse_diagnostics.get("defender_team_raw"),
                    side_parse_diagnostics.get("winner_team_raw"),
                    ",".join(side_parse_diagnostics["reasons"]),
                )

            # Check for NEW lua format: 9th field = actual playtime in seconds
            actual_playtime_seconds = None
            if len(header_parts) >= 9:
                try:
                    # New format has exact playtime in seconds as 9th field
                    actual_playtime_seconds = float(header_parts[8])
                except (ValueError, IndexError):
                    actual_playtime_seconds = None

            # Parse players
            players = []
            for line in lines[1:]:
                if line.strip() and '\\' in line:
                    player_data = self.parse_player_line(line)
                    if player_data:
                        players.append(player_data)

            # Bot/human counts (for bot-only session labeling)
            bot_player_count = sum(1 for p in players if p.get('is_bot'))
            human_player_count = max(0, len(players) - bot_player_count)
            is_bot_round = bot_player_count > 0 and human_player_count == 0

            # Calculate time in SECONDS (primary storage format)
            if actual_playtime_seconds is not None:
                # NEW FORMAT: Use exact seconds from header field 9
                round_time_seconds = int(actual_playtime_seconds)
            else:
                # OLD FORMAT: Parse MM:SS from header field 8
                round_time_seconds = self.parse_time_to_seconds(actual_time)
                if round_time_seconds == 0:
                    round_time_seconds = 300  # Default 5 minutes if unknown

            # Calculate DPM for all players using SECONDS
            # NOTE: In stopwatch mode, all players play the full round duration (teams locked)
            for player in players:
                damage_given = player.get('damage_given', 0)

                # Store time in SECONDS (integer)
                # In stopwatch: everyone plays full round, so round_time_seconds is correct
                player['time_played_seconds'] = round_time_seconds

                # Create display format (MM:SS)
                minutes = round_time_seconds // 60
                seconds = round_time_seconds % 60
                player['time_display'] = f"{minutes}:{seconds:02d}"

                # Calculate DPM: (damage * 60) / seconds = damage per 60 seconds
                if round_time_seconds > 0:
                    player['dpm'] = (damage_given * 60) / round_time_seconds
                else:
                    player['dpm'] = 0.0

                # Backward compatibility: keep decimal minutes (deprecated)
                player['time_played_minutes'] = round_time_seconds / 60.0

            # Calculate MVP
            mvp = self.calculate_mvp(players)

            # Determine round outcome
            round_outcome = self.determine_round_outcome(map_time, actual_time, round_num)
            score_confidence = score_confidence_state(
                defender_team,
                winner_team,
                reasons=side_parse_diagnostics.get('reasons', []),
                fallback_used=False,
            )
            stopwatch_contract = derive_stopwatch_contract(round_num, map_time, actual_time)

            return {
                'success': True,
                'map_name': map_name,
                'round_num': round_num,
                'defender_team': defender_team,
                'winner_team': winner_team,
                'winner_team_normalized': normalize_side_value(winner_team, allow_unknown=True),
                'defender_team_normalized': normalize_side_value(defender_team, allow_unknown=True),
                'side_parse_diagnostics': side_parse_diagnostics,
                'score_confidence': score_confidence,
                'map_time': map_time,
                'actual_time': actual_time,
                'round_outcome': round_outcome,
                'round_stopwatch_state': stopwatch_contract['round_stopwatch_state'],
                'time_to_beat_seconds': stopwatch_contract['time_to_beat_seconds'],
                'next_timelimit_minutes': stopwatch_contract['next_timelimit_minutes'],
                'players': players,
                'mvp': mvp,
                'total_players': len(players),
                'bot_player_count': bot_player_count,
                'human_player_count': human_player_count,
                'is_bot_round': is_bot_round,
                'timestamp': datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error parsing stats file {file_path}: {e}")
            return self._get_error_result(f"exception: {str(e)}")

    def parse_player_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single player line using c0rnp0rn3.lua format"""
        try:
            # Split by backslash for basic info: guid\name\rounds\team\stats
            parts = line.split('\\')
            if len(parts) < 5:
                return None

            guid = parts[0]
            raw_name = parts[1]
            clean_name = self.strip_color_codes(raw_name)
            is_bot = self.is_bot_name(clean_name)
            rounds = int(parts[2]) if parts[2].isdigit() else 0
            team = int(parts[3]) if parts[3].isdigit() else 0
            stats_section = parts[4]

            # Parse stats section using c0rnp0rn3 format
            # Split weapon stats (space-separated) from extended stats (TAB-separated)
            if '\t' in stats_section:
                weapon_section, extended_section = stats_section.split('\t', 1)
                stats_parts = weapon_section.split()
            else:
                stats_parts = stats_section.split()
                extended_section = None

            # Minimum validation: at least weapon mask (1 field) + 1 weapon (5 fields) = 6 fields
            # Changed from 30 to fix bug where players with fewer weapons were dropped
            if len(stats_parts) < 6:
                return None

            weapon_mask = int(stats_parts[0])

            # Extract weapon statistics using c0rnp0rn3 weapon mapping
            weapon_stats = {}
            total_kills = 0
            total_deaths = 0
            total_headshots = 0
            stats_index = 1  # Start after weapon mask

            # Process each weapon (0-27) using c0rnp0rn3 mapping
            for weapon_id in range(28):
                if weapon_mask & (1 << weapon_id):  # Check if weapon bit is set
                    weapon_name = C0RNP0RN3_WEAPONS.get(weapon_id, f"UNKNOWN_{weapon_id}")

                    if stats_index + 4 < len(stats_parts):
                        hits = int(stats_parts[stats_index])
                        shots = int(stats_parts[stats_index + 1])
                        kills = int(stats_parts[stats_index + 2])
                        deaths = int(stats_parts[stats_index + 3])
                        headshots = int(stats_parts[stats_index + 4])

                        accuracy = (hits / shots * 100) if shots > 0 else 0

                        weapon_stats[weapon_name] = {
                            'hits': hits,
                            'shots': shots,
                            'kills': kills,
                            'deaths': deaths,
                            'headshots': headshots,
                            'accuracy': accuracy,
                        }

                        total_kills += kills
                        total_deaths += deaths
                        total_headshots += headshots

                        stats_index += 5

            # Calculate additional metrics
            kd_ratio = total_kills / total_deaths if total_deaths > 0 else total_kills

            # Calculate totals
            total_shots = sum(w['shots'] for w in weapon_stats.values())
            total_hits = sum(w['hits'] for w in weapon_stats.values())
            total_accuracy = (total_hits / total_shots * 100) if total_shots > 0 else 0

            # Extract additional stats (after weapon data)
            # After weapon stats come TAB-separated fields (0-35) = 36 fields
            additional_stats = {}
            objective_stats = {}  # NEW: Store objective/support stats

            if extended_section:
                # Extended stats are already TAB-separated
                tab_fields = extended_section.split('\t')

                # Helper: safe cast functions to avoid IndexError/ValueError
                def safe_int(lst, idx, default=0):
                    try:
                        return int(lst[idx])
                    except Exception:
                        return default

                def safe_float(lst, idx, default=0.0):
                    try:
                        return float(lst[idx])
                    except Exception:
                        return default

                # Populate additional_stats and objective_stats using safe accessors
                try:
                    additional_stats = {
                        'damage_given': safe_int(tab_fields, 0),
                        'damage_received': safe_int(tab_fields, 1),
                        'team_damage_given': safe_int(tab_fields, 2),
                        'team_damage_received': safe_int(tab_fields, 3),
                        'gibs': safe_int(tab_fields, 4),
                        'self_kills': safe_int(tab_fields, 5),
                        'team_kills': safe_int(tab_fields, 6),
                        'team_gibs': safe_int(tab_fields, 7),
                        'time_played_percent': safe_float(tab_fields, 8),
                    }

                    objective_stats = {
                        'damage_given': safe_int(tab_fields, 0),
                        'damage_received': safe_int(tab_fields, 1),
                        'team_damage_given': safe_int(tab_fields, 2),
                        'team_damage_received': safe_int(tab_fields, 3),
                        'gibs': safe_int(tab_fields, 4),
                        'self_kills': safe_int(tab_fields, 5),
                        'team_kills': safe_int(tab_fields, 6),
                        'team_gibs': safe_int(tab_fields, 7),
                        'time_played_percent': safe_float(tab_fields, 8),
                        'xp': safe_int(tab_fields, 9),
                        'killing_spree': safe_int(tab_fields, 10),
                        'death_spree': safe_int(tab_fields, 11),
                        'kill_assists': safe_int(tab_fields, 12),
                        'kill_steals': safe_int(tab_fields, 13),
                        'headshot_kills': safe_int(tab_fields, 14),
                        'objectives_stolen': safe_int(tab_fields, 15),
                        'objectives_returned': safe_int(tab_fields, 16),
                        'dynamites_planted': safe_int(tab_fields, 17),
                        'dynamites_defused': safe_int(tab_fields, 18),
                        'times_revived': safe_int(tab_fields, 19),
                        'bullets_fired': safe_int(tab_fields, 20),
                        'dpm': safe_float(tab_fields, 21),
                        'time_played_minutes': safe_float(tab_fields, 22),
                        'tank_meatshield': safe_float(tab_fields, 23),
                        'time_dead_ratio': safe_float(tab_fields, 24),
                        'time_dead_minutes': safe_float(tab_fields, 25),
                        'kd_ratio': safe_float(tab_fields, 26),
                        'useful_kills': safe_int(tab_fields, 27),
                        'denied_playtime': safe_int(tab_fields, 28),
                        'multikill_2x': safe_int(tab_fields, 29),
                        'multikill_3x': safe_int(tab_fields, 30),
                        'multikill_4x': safe_int(tab_fields, 31),
                        'multikill_5x': safe_int(tab_fields, 32),
                        'multikill_6x': safe_int(tab_fields, 33),
                        'useless_kills': safe_int(tab_fields, 34),
                        'full_selfkills': safe_int(tab_fields, 35),
                        'repairs_constructions': safe_int(tab_fields, 36),
                        'revives_given': safe_int(tab_fields, 37),
                    }

                    # [TIME DEBUG] Log raw values from Lua for debugging time stat issues
                    logger.info(f"[TIME DEBUG] {clean_name} RAW from Lua: "
                        f"time_played_min={safe_float(tab_fields, 22)}, "
                        f"time_dead_ratio={safe_float(tab_fields, 24)}, "
                        f"time_dead_min={safe_float(tab_fields, 25)}, "
                        f"denied_playtime_sec={safe_int(tab_fields, 28)}")

                except Exception as e:
                    # Defensive fallback: ensure we always have at least basic numbers
                    logger.warning(f"Could not fully parse extended fields, falling back: {e}")
                    additional_stats = {
                        'damage_given': safe_int(tab_fields, 0),
                        'damage_received': safe_int(tab_fields, 1),
                    }

            # Calculate efficiency
            efficiency = 0
            if (total_kills + total_deaths) > 0:
                efficiency = total_kills / (total_kills + total_deaths) * 100

            # ⚠️ CRITICAL DISTINCTION - DO NOT CONFUSE THESE TWO:
            # 1. player['headshots'] = Sum of all weapon headshot HITS (shots that hit head, may not kill)
            # 2. objective_stats['headshot_kills'] = TAB field 14 (kills where FINAL BLOW was to head)
            # These are DIFFERENT stats! Database stores headshot_kills, NOT weapon sum.
            # Validated Nov 3, 2025: 100% accuracy confirmed.

            return {
                'guid': guid[:8],  # Truncate GUID
                'clean_name': clean_name,  # ✅ FIXED: Use clean_name
                'name': clean_name,  # Keep both for compatibility
                'raw_name': raw_name,
                'is_bot': is_bot,
                'team': team,
                'rounds': rounds,
                'kills': total_kills,
                'deaths': total_deaths,
                'headshots': total_headshots,  # Sum of weapon headshot HITS (not kills!)
                'kd_ratio': kd_ratio,
                'shots_total': total_shots,
                'hits_total': total_hits,
                'accuracy': total_accuracy,
                'damage_given': additional_stats.get('damage_given', 0),
                'damage_received': additional_stats.get('damage_received', 0),
                'dpm': objective_stats.get('dpm', 0.0),
                'weapon_stats': weapon_stats,
                'efficiency': efficiency,
                'objective_stats': objective_stats,  # Contains headshot_KILLS (TAB field 14)
            }

        except Exception as e:
            logger.warning(f"Error parsing player line: {e}")
            return None

    def calculate_mvp(self, players: List[Dict[str, Any]]) -> Optional[str]:
        """Calculate MVP based on K/D ratio, efficiency, and damage"""
        if not players:
            return None

        best_player = None
        best_score = 0

        for player in players:
            # MVP scoring: K/D ratio + efficiency + damage factor
            kd_score = player['kd_ratio'] * 10
            efficiency_score = player['efficiency']
            damage_score = player['damage_given'] / 100

            total_score = kd_score + efficiency_score + damage_score

            if total_score > best_score:
                best_score = total_score
                best_player = player

        return best_player['name'] if best_player else None

    def determine_round_outcome(self, map_time: str, actual_time: str, round_num: int) -> str:
        """Determine if round was fullhold based on time comparison

        NOTE: In Round 2, actual_time of "0:00" appears in 19.6% of files.
        This likely indicates the g_nextTimeLimit cvar was reset/not set.
        We treat this as "Unknown" to preserve data integrity.
        See dev/TIME_FORMAT_ANALYSIS.md for details.
        """
        try:
            map_seconds = self.parse_time_to_seconds(map_time)
            actual_seconds = (
                self.parse_time_to_seconds(actual_time) if actual_time != "Unknown" else 600
            )

            # Special case: Round 2 with 0:00 actual_time
            # This appears in ~20% of Round 2 files, meaning unclear
            if round_num == 2 and actual_time == "0:00":
                return "Unknown"

            time_diff = map_seconds - actual_seconds

            if time_diff <= 30:  # Within 30 seconds = time ran out
                return "Fullhold"
            else:
                return "Completed"

        except BaseException:
            return "Unknown"

    def _get_error_result(self, error_type: str) -> Dict[str, Any]:
        """Return standardized error result"""
        return {
            'success': False,
            'error': error_type,
            'map_name': 'Unknown',
            'round_num': 0,
            'side_parse_diagnostics': {
                'header_field_count': 0,
                'defender_team_raw': None,
                'winner_team_raw': None,
                'reasons': [f"parse_error:{error_type}"],
            },
            'score_confidence': 'missing',
            'round_stopwatch_state': None,
            'time_to_beat_seconds': None,
            'next_timelimit_minutes': None,
            'players': [],
            'mvp': None,
            'total_players': 0,
            'timestamp': datetime.now().isoformat(),
        }


def test_c0rnporn3_parser():
    """Test the c0rnp0rn3 parser"""
    parser = C0RNP0RN3StatsParser()

    test_file = "2025-09-30-220944-etl_sp_delivery-round-2.txt"
    result = parser.parse_stats_file(test_file)

    logger.info("=== C0RNP0RN3.LUA Parser Test ===")
    logger.info(f"Success: {result['success']}")
    logger.info(f"Map: {result['map_name']} Round {result['round_num']}")
    logger.info(f"Players: {result['total_players']}")
    logger.info(f"MVP: {result['mvp']}")
    logger.info(f"Outcome: {result['round_outcome']}")

    logger.info("Top 3 Players:")
    sorted_players = sorted(result['players'], key=lambda x: x['kd_ratio'], reverse=True)
    for i, player in enumerate(sorted_players[:3], 1):
        logger.info(
            f"  {i}. {player['name']}: {player['kills']}K/{player['deaths']}D (K/D: {player['kd_ratio']:.2f})"
        )

        # Show weapon breakdown for MP40/Thompson/Luger/Colt
        focus_weapons = ['WS_MP40', 'WS_THOMPSON', 'WS_LUGER', 'WS_COLT']
        for weapon in focus_weapons:
            if weapon in player['weapon_stats']:
                w = player['weapon_stats'][weapon]
                if w['shots'] > 0:
                    weapon_name = weapon.replace('WS_', '')
                    logger.info(
                        f"     {weapon_name}: {w['accuracy']:.1f}% acc "
                        f"({w['hits']}/{w['shots']}) | {w['kills']}K/{w['deaths']}D | {w['headshots']} HS"
                    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    test_c0rnporn3_parser()
