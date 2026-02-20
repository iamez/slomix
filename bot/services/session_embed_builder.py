"""
Session Embed Builder - Creates Discord embeds for session displays

This service manages:
- Session overview embeds
- Team analytics embeds
- Team composition embeds
- DPM analytics embeds
- Weapon mastery embeds
- Special awards embeds
"""

import discord
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("bot.services.session_embed_builder")


class SessionEmbedBuilder:
    """Service for building Discord embeds for session data"""

    # Discord embed field value limit
    MAX_FIELD_VALUE = 1024

    def __init__(self, timing_shadow_service=None, show_timing_dual: bool = False):
        """Initialize the session embed builder"""
        self.timing_shadow_service = timing_shadow_service
        self.show_timing_dual = bool(show_timing_dual)

    @staticmethod
    def _safe_field_value(text: str, max_chars: int = 1024) -> str:
        """Truncate a field value to fit within Discord's 1024-char limit."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars - 4] + "\n..."

    @staticmethod
    def _chunk_field_lines(lines: List[str], separator: str = "\n", max_chars: int = 1024) -> List[str]:
        """Split lines into chunks that fit within Discord's field value limit.

        Each individual line that exceeds max_chars is truncated.
        Returns a list of joined chunks, each within the limit.
        """
        if not lines:
            return []

        chunks = []
        current = []

        for line in lines:
            safe_line = line if len(line) <= max_chars else line[:max_chars - 3] + "..."

            if not current:
                current = [safe_line]
                continue

            candidate = separator.join(current + [safe_line])
            if len(candidate) <= max_chars:
                current.append(safe_line)
            else:
                chunks.append(separator.join(current))
                current = [safe_line]

        if current:
            chunks.append(separator.join(current))

        return chunks

    @staticmethod
    def _format_delta_seconds(delta_seconds: int) -> str:
        """Format signed delta as MM:SS."""
        total = abs(int(delta_seconds or 0))
        minutes = total // 60
        seconds = total % 60
        if total == 0:
            return "0:00"
        sign = "+" if delta_seconds > 0 else "-"
        return f"{sign}{minutes}:{seconds:02d}"

    async def build_session_overview_embed(
        self,
        latest_date: str,
        all_players: List,
        maps_played: str,
        rounds_played: int,
        player_count: int,
        team_1_name: str,
        team_2_name: str,
        team_1_score: int,
        team_2_score: int,
        hardcoded_teams: bool,
        scoring_result: Optional[Dict] = None,
        player_badges: Optional[Dict[str, str]] = None,
        full_selfkills_available: bool = True,
        bot_session_summary: Optional[Dict[str, Any]] = None,
        timing_dual_by_guid: Optional[Dict[str, Dict[str, Any]]] = None,
        timing_dual_meta: Optional[Dict[str, Any]] = None,
        show_timing_dual: Optional[bool] = None,
    ) -> discord.Embed:
        """Build main session overview embed with all players and match score."""
        # Build description with match score
        desc = f"**{player_count} players** • **{rounds_played} rounds** • **Maps**: {maps_played}"
        effective_show_timing_dual = (
            self.show_timing_dual if show_timing_dual is None else bool(show_timing_dual)
        )
        timing_dual_by_guid = timing_dual_by_guid or {}
        timing_dual_meta = timing_dual_meta or {}

        # Optional bot-only / mixed session label
        if bot_session_summary:
            bot_rounds = bot_session_summary.get("bot_rounds", 0)
            total_rounds = bot_session_summary.get("total_rounds", 0)
            bot_only = bot_session_summary.get("bot_only", False)
            if bot_only and total_rounds > 0:
                desc += f"\n🤖 **BOT-ONLY SESSION** • Rounds: {bot_rounds}/{total_rounds}"
            elif bot_rounds > 0 and total_rounds > 0:
                desc += f"\n🤖 **Mixed Session** • Bot rounds: {bot_rounds}/{total_rounds}"
        if effective_show_timing_dual:
            desc += "\n⏱️ **Timing:** O=legacy, N=shadow (Δ=N-O)"
            rounds_total = int(timing_dual_meta.get("rounds_total", 0) or 0)
            rounds_with_telemetry = int(timing_dual_meta.get("rounds_with_telemetry", 0) or 0)
            if rounds_total > 0 and rounds_with_telemetry < rounds_total:
                desc += f" • Lua {rounds_with_telemetry}/{rounds_total} rounds"
            elif rounds_total > 0 and rounds_with_telemetry == 0:
                desc += " • fallback N=O"
        if hardcoded_teams and team_1_score + team_2_score > 0:
            if team_1_score == team_2_score:
                desc += f"\n\n🤝 **Match Result: {team_1_score} - {team_2_score} (PERFECT TIE)**"
            else:
                desc += f"\n\n🏆 **Match Result: {team_1_name} {team_1_score} - {team_2_score} {team_2_name}**"

            # Add map-by-map breakdown if available
            if scoring_result and 'maps' in scoring_result:
                desc += "\n\n**📊 Map Breakdown:**"
                for map_result in scoring_result['maps']:
                    map_name = map_result.get('map', 'Unknown')
                    counted = map_result.get('counted', True)
                    note = map_result.get('note') or map_result.get('description', '').strip()

                    if not counted:
                        reason = note or "Not counted"
                        desc += f"\n⚪ `{map_name}`: {reason}"
                        continue

                    # Support both old format (team1_points) and new format (team_a_points)
                    t1_pts = map_result.get('team_a_points', map_result.get('team1_points', 0))
                    t2_pts = map_result.get('team_b_points', map_result.get('team2_points', 0))

                    # Get timing info if available (new format)
                    t1_time = map_result.get('team_a_time', '')
                    t2_time = map_result.get('team_b_time', '')

                    # Use provided emoji or calculate based on points
                    winner_emoji = map_result.get('emoji', '')
                    if not winner_emoji:
                        if t1_pts > t2_pts:
                            winner_emoji = "🟢"
                        elif t2_pts > t1_pts:
                            winner_emoji = "🔴"
                        else:
                            winner_emoji = "🟡"

                    # Build display string
                    if t1_time and t2_time:
                        # New format with timing: "🟢 mp_decoy: puran (8:45) vs sWat (fullhold)"
                        desc += f"\n{winner_emoji} `{map_name}`: {team_1_name} ({t1_time}) vs {team_2_name} ({t2_time})"
                    else:
                        # Old format: just points
                        desc += f"\n{winner_emoji} `{map_name}`: {t1_pts}-{t2_pts}"

        embed = discord.Embed(
            title=f"📊 Session Summary: {latest_date}",
            description=desc,
            color=0x5865F2,
            timestamp=datetime.now()
        )

        # Build player summary - split into multiple fields to avoid 1024 char limit
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "1️⃣0️⃣", "1️⃣1️⃣", "1️⃣2️⃣"]
        players_per_field = 3  # 3 players per field to stay under 1024 chars
        
        for field_idx in range(0, len(all_players), players_per_field):
            field_text = ""
            field_players = all_players[field_idx:field_idx + players_per_field]
            
            for i, player in enumerate(field_players):
                global_idx = field_idx + i
                name, player_guid, kills, deaths, dpm, hits, shots = player[0:7]
                total_hs, hsk, total_seconds, total_time_dead, total_denied = player[7:12]
                total_gibs, total_revives_given, total_times_revived, total_damage_received, total_damage_given = player[12:17]
                total_useful_kills, total_double_kills, total_triple_kills, total_quad_kills = player[17:21]
                total_multi_kills, total_mega_kills = player[21:23]
                total_self_kills = player[23] if len(player) > 23 else 0
                total_full_selfkills = player[24] if len(player) > 24 else 0

                # Handle NULL values
                kills = kills or 0
                deaths = deaths or 0
                dpm = dpm or 0
                hits = hits or 0
                shots = shots or 0
                total_hs = total_hs or 0
                total_seconds = total_seconds or 0
                total_time_dead = total_time_dead or 0
                total_denied = total_denied or 0
                total_gibs = total_gibs or 0
                total_revives_given = total_revives_given or 0
                total_times_revived = total_times_revived or 0
                total_damage_received = total_damage_received or 0
                total_damage_given = total_damage_given or 0
                total_useful_kills = total_useful_kills or 0
                total_double_kills = total_double_kills or 0
                total_triple_kills = total_triple_kills or 0
                total_quad_kills = total_quad_kills or 0
                total_multi_kills = total_multi_kills or 0
                total_mega_kills = total_mega_kills or 0

                # Calculate metrics
                kd_ratio = kills / deaths if deaths > 0 else kills
                acc = (hits / shots * 100) if shots and shots > 0 else 0
                hs_rate = (total_hs / hits * 100) if hits and hits > 0 else 0

                # Format times
                minutes = int(total_seconds // 60)
                seconds = int(total_seconds % 60)
                time_display = f"{minutes}:{seconds:02d}"

                dead_minutes = int(total_time_dead // 60)
                dead_seconds = int(total_time_dead % 60)
                time_dead_display = f"{dead_minutes}:{dead_seconds:02d}"

                denied_minutes = int(total_denied // 60)
                denied_seconds = int(total_denied % 60)
                time_denied_display = f"{denied_minutes}:{denied_seconds:02d}"

                # Calculate time percentages (all values in seconds)
                if total_seconds > 0:
                    dead_pct = (total_time_dead / total_seconds) * 100
                    denied_pct = (total_denied / total_seconds) * 100
                else:
                    dead_pct = denied_pct = 0

                # Format damage (show in K if over 1000)
                if total_damage_given >= 1000:
                    dmg_given_display = f"{total_damage_given/1000:.1f}K"
                else:
                    dmg_given_display = f"{total_damage_given}"

                if total_damage_received >= 1000:
                    dmg_recv_display = f"{total_damage_received/1000:.1f}K"
                else:
                    dmg_recv_display = f"{total_damage_received}"

                # Three-line format: Name, Combat stats, Support stats
                if global_idx < len(medals):
                    medal = medals[global_idx]
                else:
                    # Generate number emoji for ranks beyond 12 (e.g., 13 → 1️⃣3️⃣)
                    rank_num = str(global_idx + 1)
                    emoji_digits = {'0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
                                   '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'}
                    medal = ''.join(emoji_digits[d] for d in rank_num)

                # Build multikills string (abbreviated)
                multikills_parts = []
                if total_double_kills > 0:
                    multikills_parts.append(f"{total_double_kills}DBL")
                if total_triple_kills > 0:
                    multikills_parts.append(f"{total_triple_kills}TPL")
                if total_quad_kills > 0:
                    multikills_parts.append(f"{total_quad_kills}QD")
                if total_multi_kills > 0:
                    multikills_parts.append(f"{total_multi_kills}PNT")
                if total_mega_kills > 0:
                    multikills_parts.append(f"{total_mega_kills}MGA")

                multikills_str = " ".join(multikills_parts) if multikills_parts else ""
                multikills_display = f" • {multikills_str}" if multikills_str else ""

                # Get achievement badges for this player
                badges = ""
                if player_badges and player_guid in player_badges:
                    badges = f" {player_badges[player_guid]}"

                # Line 1: Player name with badges
                field_text += f"{medal} **{name}**{badges}\n"

                # Line 2: Combat essentials (K/D, DPM, damage, accuracy, headshots)
                field_text += (
                    f"   {kills}K/{deaths}D/{total_gibs}G ({kd_ratio:.2f}) • "
                    f"{dpm:.0f} DPM • {dmg_given_display}⬆/{dmg_recv_display}⬇ • "
                    f"{acc:.1f}% ACC ({hits}/{shots}) • {total_hs} HS ({hs_rate:.1f}%)\n"
                )

                # Line 3: Support/meta stats (UK, revives, times, multikills)
                if effective_show_timing_dual:
                    timing_shadow = timing_dual_by_guid.get(player_guid, {})
                    dead_new = int(timing_shadow.get("new_time_dead_seconds", total_time_dead) or 0)
                    denied_new = int(timing_shadow.get("new_denied_seconds", total_denied) or 0)
                    dead_new = max(0, dead_new)
                    denied_new = max(0, denied_new)
                    dead_new_display = f"{int(dead_new // 60)}:{int(dead_new % 60):02d}"
                    denied_new_display = f"{int(denied_new // 60)}:{int(denied_new % 60):02d}"
                    dead_delta_display = self._format_delta_seconds(dead_new - int(total_time_dead))
                    denied_delta_display = self._format_delta_seconds(denied_new - int(total_denied))

                    missing_reason = (timing_shadow.get("missing_reason") or "").lower()
                    telemetry_note = ""
                    if missing_reason.startswith("no lua"):
                        telemetry_note = " ⚠️no-lua"
                    elif "partial" in missing_reason:
                        telemetry_note = " ⚠️partial"

                    field_text += (
                        f"   {total_useful_kills} UK • {total_self_kills} SK • {total_full_selfkills} FSK • "
                        f"{total_revives_given}↑/{total_times_revived}↓ • "
                        f"⏱{time_display} 💀O{time_dead_display}/N{dead_new_display}(Δ{dead_delta_display}) "
                        f"⏳O{time_denied_display}/N{denied_new_display}(Δ{denied_delta_display})"
                        f"{telemetry_note}{multikills_display}\n\n"
                    )
                else:
                    field_text += (
                        f"   {total_useful_kills} UK • {total_self_kills} SK • {total_full_selfkills} FSK • "
                        f"{total_revives_given}↑/{total_times_revived}↓ • "
                        f"⏱{time_display} 💀{time_dead_display}({dead_pct:.0f}%) "
                        f"⏳{time_denied_display}({denied_pct:.0f}%){multikills_display}\n\n"
                    )
            
            # Add field with appropriate name, chunk if needed
            if field_idx == 0:
                field_name = "🏆 All Players"
            else:
                field_name = "\u200b"  # Invisible character for continuation fields

            field_value = field_text.rstrip()
            if len(field_value) <= self.MAX_FIELD_VALUE:
                embed.add_field(name=field_name, value=field_value, inline=False)
            else:
                # Field exceeds limit even with 3 players — split into per-player chunks
                player_blocks = field_value.split("\n\n")
                chunks = self._chunk_field_lines(player_blocks, separator="\n\n", max_chars=self.MAX_FIELD_VALUE)
                for ci, chunk in enumerate(chunks):
                    name = field_name if ci == 0 else "\u200b"
                    embed.add_field(name=name, value=chunk, inline=False)

        footer = f"Round: {latest_date}"
        if not full_selfkills_available:
            footer += " • FSK unavailable (missing column)"
        if effective_show_timing_dual:
            rounds_total = int(timing_dual_meta.get("rounds_total", 0) or 0)
            rounds_with_telemetry = int(timing_dual_meta.get("rounds_with_telemetry", 0) or 0)
            reason = timing_dual_meta.get("reason") or ""
            if rounds_total > 0 and rounds_with_telemetry < rounds_total:
                footer += f" • Lua timing {rounds_with_telemetry}/{rounds_total}"
            elif rounds_total > 0 and rounds_with_telemetry == 0:
                footer += " • Lua timing missing (N=O)"
            if reason and reason != "OK":
                footer += f" • {reason}"
        embed.set_footer(text=footer)
        return embed

    def _build_endstats_section(
        self, endstats_data: Dict[str, Any]
    ) -> Tuple[str, str]:
        """Build compact endstats summary for embed.

        Args:
            endstats_data: Aggregated endstats from EndstatsAggregator

        Returns:
            Tuple of (awards_text, vs_stats_text)
        """
        awards_text = ""
        vs_text = ""

        # Category display config
        category_display = {
            "combat": ("Combat", 1),
            "skills": ("Skills", 2),
            "weapons": ("Weapons", 3),
            "timing": ("Timing", 4),
            "teamwork": ("Teamwork", 5),
            "objectives": ("Objectives", 6),
            "deaths": ("Deaths", 7),
        }

        awards_by_category = endstats_data.get("awards_by_category", {})
        vs_stats = endstats_data.get("vs_stats", [])

        # Build awards text
        if awards_by_category:
            lines = []
            rounds_info = ""
            if endstats_data.get("rounds_with_endstats", 0) < endstats_data.get("total_rounds", 0):
                rounds_info = f" ({endstats_data['rounds_with_endstats']}/{endstats_data['total_rounds']} rounds)"

            # Sort categories by priority
            sorted_categories = sorted(
                [c for c in awards_by_category.keys() if c in category_display],
                key=lambda c: category_display[c][1]
            )

            for category in sorted_categories[:4]:  # Max 4 categories
                display_name, _ = category_display[category]
                awards = awards_by_category[category]

                # Get top 2 awards for this category
                top_awards = []
                for award_name, players in list(awards.items())[:2]:
                    if players:
                        top_player = players[0]  # Already sorted by value DESC
                        player_name = top_player[1]
                        total_value = top_player[2]
                        win_count = top_player[3]

                        formatted_value = self._format_endstats_value(total_value, award_name)
                        top_awards.append(f"{player_name} ({formatted_value}, {win_count}x)")

                if top_awards:
                    lines.append(f"**{display_name}:** {', '.join(top_awards)}")

            if lines:
                awards_text = "\n".join(lines) + rounds_info

        # Build VS stats text
        if vs_stats:
            parts = []
            for _, player_name, kills, deaths in vs_stats[:5]:
                parts.append(f"{player_name} {kills}K/{deaths}D")
            vs_text = " | ".join(parts)

        return awards_text, vs_text

    def _format_endstats_value(self, value: float, award_name: str) -> str:
        """Format award value for display.

        Args:
            value: Numeric value
            award_name: Award name for context

        Returns:
            Formatted string (e.g., "3.2K", "52%", "2:30")
        """
        if value is None:
            return "0"

        # Damage-related awards: show in K format
        if "damage" in award_name.lower():
            if value >= 1000:
                return f"{value/1000:.1f}K"
            return f"{int(value)}"

        # Accuracy awards: show as percentage
        if "accuracy" in award_name.lower():
            return f"{value:.0f}%"

        # Time-related awards: show as m:ss
        if "time" in award_name.lower() or "spawn" in award_name.lower():
            minutes = int(value // 60)
            seconds = int(value % 60)
            return f"{minutes}:{seconds:02d}"

        # Ratio awards
        if "ratio" in award_name.lower():
            return f"{value:.2f}"

        # Default: integer or float based on value
        if value >= 1000:
            return f"{value/1000:.1f}K"
        if value == int(value):
            return str(int(value))
        return f"{value:.1f}"

    async def build_session_endstats_embed(
        self, latest_date: str, endstats_data: Dict[str, Any]
    ) -> Optional[discord.Embed]:
        """Build a separate embed for cumulative session endstats.

        Args:
            latest_date: Session date string
            endstats_data: Aggregated endstats from EndstatsAggregator

        Returns:
            Discord embed with cumulative awards and VS stats, or None if no data
        """
        if not endstats_data or not endstats_data.get('has_data'):
            return None

        awards_by_category = endstats_data.get("awards_by_category", {})
        rounds_with = endstats_data.get("rounds_with_endstats", 0)
        total_rounds = endstats_data.get("total_rounds", 0)

        # Create embed
        embed = discord.Embed(
            title=f"Session Awards - {latest_date}",
            description=f"Cumulative awards from {rounds_with}/{total_rounds} rounds",
            color=0xFFD700,  # Gold
            timestamp=datetime.now()
        )

        # Category config with emojis
        category_config = {
            "combat": ("Combat", "1"),
            "skills": ("Skills", "2"),
            "weapons": ("Weapons", "3"),
            "timing": ("Timing", "4"),
            "teamwork": ("Teamwork", "5"),
            "objectives": ("Objectives", "6"),
            "deaths": ("Deaths", "7"),
        }

        # Build each category as a field
        for category, (display_name, priority) in sorted(category_config.items(), key=lambda x: x[1][1]):
            if category not in awards_by_category:
                continue

            awards = awards_by_category[category]
            if not awards:
                continue

            # Build field content - show top award per type
            lines = []
            for award_name, players in list(awards.items())[:4]:  # Max 4 awards per category
                if not players:
                    continue

                # Get top player for this award
                top = players[0]
                player_name = top[1]
                total_value = top[2]
                win_count = top[3]

                # Format the award name (shorten it)
                short_name = award_name.replace("Most ", "").replace("Highest ", "").replace("Best ", "")

                # Skip summed value for ratio/percentage awards (summing them is meaningless)
                award_lower = award_name.lower()
                if any(x in award_lower for x in ['ratio', 'accuracy', 'percent']):
                    # For ratios/percentages, just show win count
                    lines.append(f"**{short_name}**: {player_name} ({win_count}x)")
                else:
                    formatted_value = self._format_endstats_value(total_value, award_name)
                    lines.append(f"**{short_name}**: {player_name} ({formatted_value}, {win_count}x)")

            if lines:
                field_value = self._safe_field_value("\n".join(lines))
                embed.add_field(
                    name=f"{display_name}",
                    value=field_value,
                    inline=True
                )

        # NOTE: VS Stats removed from cumulative view - they are per-opponent matchups
        # and don't aggregate meaningfully across rounds. See per-round endstats for VS data.

        embed.set_footer(text="Aggregated from endstats.lua")
        return embed

    async def build_team_analytics_embed(
        self,
        latest_date: str,
        team_1_name: str,
        team_2_name: str,
        team_stats: List,
        team_1_mvp_stats: Optional[tuple],
        team_2_mvp_stats: Optional[tuple],
        team_1_score: int,
        team_2_score: int,
        hardcoded_teams: bool
    ) -> discord.Embed:
        """Build team analytics embed with stats and MVPs."""
        analytics_desc = "Comprehensive team performance comparison"
        if hardcoded_teams and team_1_score + team_2_score > 0:
            if team_1_score == team_2_score:
                analytics_desc += f"\n\n🤝 **Maps Won: {team_1_score} - {team_2_score} (PERFECT TIE)**"
            else:
                analytics_desc += f"\n\n🏆 **Maps Won: {team_1_score} - {team_2_score}**"

        embed = discord.Embed(
            title=f"⚔️ Team Analytics - {team_1_name} vs {team_2_name}",
            description=analytics_desc,
            color=0xED4245,
            timestamp=datetime.now()
        )

        # Team stats - separate fields for each team
        if len(team_stats) > 1:
            for team, kills, deaths, damage in team_stats:
                if team == 1:
                    current_team_name = team_1_name
                    emoji = "🔴"
                elif team == 2:
                    current_team_name = team_2_name
                    emoji = "🔵"
                else:
                    continue

                kd_ratio = kills / deaths if deaths > 0 else kills
                team_text = (
                    f"**Total Kills:** `{kills:,}`\n"
                    f"**Total Deaths:** `{deaths:,}`\n"
                    f"**K/D Ratio:** `{kd_ratio:.2f}`\n"
                    f"**Total Damage:** `{damage:,}`\n"
                )
                embed.add_field(name=f"{emoji} {current_team_name} Team Stats", value=team_text, inline=True)

        # Team MVPs
        if team_1_mvp_stats:
            player, kills, dpm, deaths, revives, gibs = team_1_mvp_stats
            kd = kills / deaths if deaths else kills
            team_1_mvp_text = (
                f"**{player}**\n"
                f"💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"
                f"💥 `{dpm:.0f} DPM`\n"
                f"💉 `{revives} Teammates Revived` • 🦴 `{gibs} Gibs`"
            )
            embed.add_field(name=f"🔴 {team_1_name} MVP", value=team_1_mvp_text, inline=True)

        if team_2_mvp_stats:
            player, kills, dpm, deaths, revives, gibs = team_2_mvp_stats
            kd = kills / deaths if deaths else kills
            team_2_mvp_text = (
                f"**{player}**\n"
                f"💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"
                f"💥 `{dpm:.0f} DPM`\n"
                f"💉 `{revives} Teammates Revived` • 🦴 `{gibs} Gibs`"
            )
            embed.add_field(name=f"🔵 {team_2_name} MVP", value=team_2_mvp_text, inline=True)

        embed.set_footer(text=f"Round: {latest_date}")
        return embed

    async def build_team_composition_embed(
        self,
        latest_date: str,
        team_1_name: str,
        team_2_name: str,
        team_1_players_list: List,
        team_2_players_list: List,
        total_rounds: int,
        total_maps: int,
        unique_maps: int,
        team_1_score: int,
        team_2_score: int,
        hardcoded_teams: bool,
        detection_confidence: str = 'high'
    ) -> discord.Embed:
        """Build team composition embed with rosters and session info.

        Args:
            detection_confidence: Team detection confidence ('high'/'medium'/'low')
                - high: All players consistent across session
                - medium: Mostly consistent with few variations
                - low: Inconsistent team assignments
        """
        # Confidence indicator emoji
        confidence_emoji = {
            'high': '✅',
            'medium': '⚠️',
            'low': '❌'
        }.get(detection_confidence, '❓')

        embed = discord.Embed(
            title="👥 Team Composition",
            description=(
                f"Player roster for {team_1_name} vs {team_2_name}\n"
                f"{confidence_emoji} **Detection Confidence:** {detection_confidence.upper()}\n"
                "🔄 indicates players who swapped teams during session"
            ),
            color=0x57F287,
            timestamp=datetime.now()
        )

        # Team 1 roster
        if team_1_players_list:
            team_1_text = f"**{len(team_1_players_list)} players**\n\n"
            for i, player in enumerate(team_1_players_list[:15], 1):
                team_1_text += f"{i}. {player}\n"
            if len(team_1_players_list) > 15:
                more_count = len(team_1_players_list) - 15
                team_1_text += f"\n*...and {more_count} more*"
            embed.add_field(name=f"🔴 {team_1_name} Roster", value=self._safe_field_value(team_1_text.rstrip()), inline=True)

        # Team 2 roster
        if team_2_players_list:
            team_2_text = f"**{len(team_2_players_list)} players**\n\n"
            for i, player in enumerate(team_2_players_list[:15], 1):
                team_2_text += f"{i}. {player}\n"
            if len(team_2_players_list) > 15:
                more_count = len(team_2_players_list) - 15
                team_2_text += f"\n*...and {more_count} more*"
            embed.add_field(name=f"🔵 {team_2_name} Roster", value=self._safe_field_value(team_2_text.rstrip()), inline=True)

        # Session info with match score
        session_info = f"📍 **{total_rounds} rounds** played ({total_maps} maps)\n"
        session_info += "🎮 **Format**: Stopwatch (2 rounds per map)\n"
        session_info += f"🗺️ **Unique map names**: {unique_maps}\n"

        if hardcoded_teams and team_1_score + team_2_score > 0:
            if team_1_score == team_2_score:
                session_info += f"\n🤝 **Maps Won**: {team_1_name} {team_1_score} - {team_2_score} {team_2_name} (TIE)"
            else:
                session_info += f"\n🏆 **Maps Won**: {team_1_name} {team_1_score} - {team_2_score} {team_2_name}"

        embed.add_field(name="📊 Round Info", value=session_info, inline=False)
        embed.set_footer(text=f"Round: {latest_date}")
        return embed

    async def build_dpm_analytics_embed(
        self,
        latest_date: str,
        dpm_leaders: List
    ) -> discord.Embed:
        """Build DPM analytics embed with leaderboard and insights."""
        embed = discord.Embed(
            title="💥 DPM Analytics - Damage Per Minute",
            description="Enhanced DPM with Kill/Death Details",
            color=0xFEE75C,
            timestamp=datetime.now()
        )

        # DPM Leaderboard
        if dpm_leaders:
            dpm_text = ""
            for i, (player, dpm, kills, deaths) in enumerate(dpm_leaders[:10], 1):
                kd = kills / deaths if deaths else kills
                dpm_text += f"{i}. **{player}**\n"
                dpm_text += f"   💥 `{dpm:.0f} DPM` • 💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"
            embed.add_field(name="🏆 Enhanced DPM Leaderboard", value=self._safe_field_value(dpm_text.rstrip()), inline=False)

            # DPM Insights
            avg_dpm = sum(p[1] for p in dpm_leaders) / len(dpm_leaders)
            highest_dpm = dpm_leaders[0][1] if dpm_leaders else 0
            leader_name = dpm_leaders[0][0] if dpm_leaders else "N/A"

            insights = (
                "📊 **Enhanced Session DPM Stats:**\n"
                f"• Average DPM: `{avg_dpm:.1f}`\n"
                f"• Highest DPM: `{highest_dpm:.0f}`\n"
                f"• DPM Leader: **{leader_name}**\n"
                "• Formula: `(Total Damage × 60) / Time Played (seconds)`"
            )
            embed.add_field(name="💥 DPM Insights", value=insights, inline=False)

        embed.set_footer(text="💥 Enhanced with Kill/Death Details")
        return embed

    async def build_weapon_mastery_embed(
        self,
        latest_date: str,
        player_weapons: List,
        player_revives_raw: List
    ) -> discord.Embed:
        """Build weapon mastery embed with per-player breakdown."""
        embed = discord.Embed(
            title="🔫 Weapon Mastery Breakdown",
            description="Top weapons and combat statistics",
            color=0x5865F2,
            timestamp=datetime.now()
        )

        # Group weapons by player
        player_weapon_map = {}
        for player, weapon, kills, hits, shots, hs in player_weapons:
            if player not in player_weapon_map:
                player_weapon_map[player] = []
            acc = (hits / shots * 100) if shots > 0 else 0
            hs_pct = (hs / hits * 100) if hits > 0 else 0
            weapon_clean = weapon.replace("WS_", "").replace("_", " ").title()
            player_weapon_map[player].append((weapon_clean, kills, acc, hs_pct, hs, hits, shots))

        # Convert revives data
        player_revives = {player: revives for player, revives in player_revives_raw}

        # Sort players by total kills
        player_totals = []
        for player, weapons in player_weapon_map.items():
            total_kills = sum(w[1] for w in weapons)
            player_totals.append((player, total_kills))
        player_totals.sort(key=lambda x: x[1], reverse=True)

        # Show all players and their weapons
        for player, total_kills in player_totals:
            weapons = player_weapon_map[player]
            revives = player_revives.get(player, 0)

            weapon_text = ""
            for weapon, kills, acc, hs_pct, hs, hits, shots in weapons:
                weapon_text += f"**{weapon}**: `{kills}K` • `{acc:.1f}% ACC` • `{hs} HS ({hs_pct:.1f}%)`\n"

            if revives > 0:
                weapon_text += f"\n💉 **Teammates Revived**: `{revives}`"

            embed.add_field(name=f"{player} ({total_kills} total kills)", value=self._safe_field_value(weapon_text), inline=False)

        embed.set_footer(text=f"Round: {latest_date}")
        return embed

    async def build_special_awards_embed(
        self,
        chaos_awards_data: List
    ) -> discord.Embed:
        """Build special awards embed with chaos stats."""
        embed = discord.Embed(
            title="🏆 SESSION SPECIAL AWARDS 🏆",
            description="*Celebrating excellence... and chaos!*",
            color=0xFFD700,  # Gold
            timestamp=datetime.now()
        )

        # Calculate awards
        awards = {
            "teamkill_king": {"player": None, "value": 0},
            "selfkill_master": {"player": None, "value": 0},
            "kill_thief": {"player": None, "value": 0},
            "spray_pray": {"player": None, "value": 0},
            "trigger_shy": {"player": None, "value": 999999},
            "damage_king": {"player": None, "value": 0},
            "glass_cannon": {"player": None, "value": 0},
            "engineer": {"player": None, "value": 0},
            "tank_shield": {"player": None, "value": 0},
            "respawn_king": {"player": None, "value": 0},
            "useless_king": {"player": None, "value": 0},
            "death_magnet": {"player": None, "value": 0},
            "worst_spree": {"player": None, "value": 0},
        }

        for row in chaos_awards_data:
            name = row[0]
            teamkills, selfkills, steals, bullets = row[1:5]
            kills, deaths, dmg_given, dmg_received = row[5:9]
            constructions, tank, useless = row[9:12]
            worst_spree, play_time = row[12:14]

            # Teamkill King
            if teamkills > awards["teamkill_king"]["value"]:
                awards["teamkill_king"] = {"player": name, "value": teamkills}

            # Self-Kill Master
            if selfkills > awards["selfkill_master"]["value"]:
                awards["selfkill_master"] = {"player": name, "value": selfkills}

            # Kill Thief
            if steals > awards["kill_thief"]["value"]:
                awards["kill_thief"] = {"player": name, "value": steals}

            # Spray & Pray
            if kills > 0 and bullets:
                bpk = bullets / kills
                if bpk > awards["spray_pray"]["value"]:
                    awards["spray_pray"] = {"player": name, "value": bpk}

            # Too Scared to Shoot
            if (kills >= 5 and bullets and
                    bullets < awards["trigger_shy"]["value"]):
                awards["trigger_shy"] = {"player": name, "value": bullets}

            # Damage Efficiency King
            if dmg_received > 0:
                eff = dmg_given / dmg_received

                if eff > awards["damage_king"]["value"]:
                    awards["damage_king"] = {"player": name, "value": eff}

            # Glass Cannon
            if dmg_received > awards["glass_cannon"]["value"]:
                awards["glass_cannon"] = {"player": name, "value": dmg_received}

            # Chief Engineer
            if constructions > awards["engineer"]["value"]:
                awards["engineer"] = {"player": name, "value": constructions}

            # Tank Shield
            if tank > awards["tank_shield"]["value"]:
                awards["tank_shield"] = {"player": name, "value": tank}

            # Respawn King
            if deaths > awards["respawn_king"]["value"]:
                awards["respawn_king"] = {"player": name, "value": deaths}

            # Most Useless Kills
            if useless > awards["useless_king"]["value"]:
                awards["useless_king"] = {"player": name, "value": useless}

            # Death Magnet
            if deaths > awards["death_magnet"]["value"]:
                awards["death_magnet"] = {"player": name, "value": deaths}

            # Worst Death Spree
            if worst_spree > awards["worst_spree"]["value"]:
                awards["worst_spree"] = {"player": name, "value": worst_spree}

        # Build awards text
        awards_text = []

        # Positive awards
        if awards["damage_king"]["value"] > 1.5:
            player = awards["damage_king"]["player"]
            ratio = awards["damage_king"]["value"]
            awards_text.append(f"💥 **Damage Efficiency King:** `{player}` ({ratio:.2f}x ratio)")

        if awards["engineer"]["value"] >= 1:
            player = awards["engineer"]["player"]
            count = int(awards["engineer"]["value"])
            awards_text.append(f"🔧 **Chief Engineer:** `{player}` ({count} repairs)")

        if awards["tank_shield"]["value"] >= 50:
            player = awards["tank_shield"]["player"]
            count = int(awards["tank_shield"]["value"])
            awards_text.append(f"🛡️ **Tank Shield:** `{player}` ({count} damage absorbed)")

        # Chaos awards
        if awards["teamkill_king"]["value"] >= 3:
            player = awards["teamkill_king"]["player"]
            count = int(awards["teamkill_king"]["value"])
            awards_text.append(f"🔴 **Teamkill King:** `{player}` ({count} teamkills)")

        if awards["selfkill_master"]["value"] >= 2:
            player = awards["selfkill_master"]["player"]
            count = int(awards["selfkill_master"]["value"])
            awards_text.append(f"💣 **Self-Destruct Master:** `{player}` ({count} self-kills)")

        if awards["kill_thief"]["value"] >= 5:
            player = awards["kill_thief"]["player"]
            count = int(awards["kill_thief"]["value"])
            awards_text.append(f"🦹 **Kill Thief:** `{player}` ({count} stolen kills)")

        if awards["spray_pray"]["value"] >= 50:
            player = awards["spray_pray"]["player"]
            bpk = awards["spray_pray"]["value"]
            awards_text.append(f"🔫 **Spray & Pray Champion:** `{player}` ({bpk:.0f} bullets/kill)")

        if awards["trigger_shy"]["value"] < 999999:
            player = awards["trigger_shy"]["player"]
            bullets = int(awards["trigger_shy"]["value"])
            awards_text.append(f"🎯 **Too Scared to Shoot:** `{player}` ({bullets} bullets total)")

        if awards["glass_cannon"]["value"] >= 1000:
            player = awards["glass_cannon"]["player"]
            dmg = int(awards["glass_cannon"]["value"])
            awards_text.append(f"🥊 **Glass Cannon:** `{player}` ({dmg:,} damage taken)")

        if awards["useless_king"]["value"] >= 3:
            player = awards["useless_king"]["player"]
            count = int(awards["useless_king"]["value"])
            awards_text.append(f"🤡 **Most Useless Kills:** `{player}` ({count} useless)")

        if awards["worst_spree"]["value"] >= 5:
            player = awards["worst_spree"]["player"]
            count = int(awards["worst_spree"]["value"])
            awards_text.append(f"💀 **Worst Death Spree:** `{player}` ({count} consecutive deaths)")

        if awards_text:
            embed.add_field(name="🎖️ Special Awards", value=self._safe_field_value("\n".join(awards_text)), inline=False)
        else:
            embed.add_field(name="🎖️ Special Awards", value="*No notable achievements this session*", inline=False)

        embed.set_footer(text="🏆 Excellence, Efficiency, and Chaos!")
        return embed

    # ═══════════════════════════════════════════════════════
    # PHASE 5: GRAPH GENERATION
    # ═══════════════════════════════════════════════════════
