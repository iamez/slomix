"""
EndStats Aggregator Service
============================

Aggregates endstats awards and VS stats across gaming sessions for cumulative
display in the !last_session command.

This service:
- Aggregates award values (sums) across multiple rounds
- Counts how many times each player won each award type
- Aggregates VS stats (player vs player kill/death matchups)
- Handles GUID resolution for players who change names
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

# Import award categories from endstats parser
from bot.endstats_parser import AWARD_CATEGORIES

logger = logging.getLogger("bot.services.endstats_aggregator")

# Category display configuration (emoji, display name, priority)
CATEGORY_DISPLAY = {
    "combat": ("Combat", 1),
    "skills": ("Skills", 2),
    "weapons": ("Weapons", 3),
    "timing": ("Timing", 4),
    "teamwork": ("Teamwork", 5),
    "objectives": ("Objectives", 6),
    "deaths": ("Deaths", 7),
}


class EndstatsAggregator:
    """Aggregate endstats awards and VS stats across gaming sessions."""

    def __init__(self, db_adapter):
        """Initialize the endstats aggregator.

        Args:
            db_adapter: Database adapter for async queries
        """
        self.db = db_adapter
        logger.debug("EndstatsAggregator initialized")

    async def check_endstats_available(self, session_ids: List[int]) -> Tuple[bool, int, int]:
        """Check if endstats data exists for any round in the session.

        Args:
            session_ids: List of round IDs in the session

        Returns:
            Tuple of (has_data, rounds_with_endstats, total_rounds)
        """
        if not session_ids:
            return False, 0, 0

        placeholders = ",".join(["$" + str(i + 1) for i in range(len(session_ids))])
        query = f"""
            SELECT COUNT(DISTINCT round_id) as rounds_with_endstats
            FROM round_awards
            WHERE round_id IN ({placeholders})
        """
        result = await self.db.fetch_one(query, tuple(session_ids))
        rounds_with_endstats = result[0] if result else 0
        total_rounds = len(session_ids)

        return rounds_with_endstats > 0, rounds_with_endstats, total_rounds

    async def aggregate_session_awards(
        self, session_ids: List[int], session_ids_str: str
    ) -> Dict[str, List[Tuple[str, str, float, int]]]:
        """Aggregate awards across session rounds.

        Groups awards by award_name, summing numeric values and counting wins.
        Uses GUID for player grouping to handle name changes.

        Args:
            session_ids: List of round IDs in the session
            session_ids_str: Comma-separated string of round IDs for SQL

        Returns:
            Dict mapping award_name to list of (player_guid, player_name, total_value, win_count)
        """
        if not session_ids:
            return {}

        # Use PostgreSQL $1, $2 parameterized queries
        placeholders = ",".join(["$" + str(i + 1) for i in range(len(session_ids))])

        query = f"""
            SELECT
                ra.award_name,
                COALESCE(ra.player_guid, pcs.player_guid) as player_guid,
                MAX(COALESCE(ra.player_name, pcs.player_name)) as player_name,
                SUM(ra.award_value_numeric) as total_value,
                COUNT(*) as win_count
            FROM round_awards ra
            LEFT JOIN player_comprehensive_stats pcs
                ON ra.round_id = pcs.round_id AND ra.player_name = pcs.player_name
            WHERE ra.round_id IN ({placeholders})
                AND ra.award_value_numeric IS NOT NULL
            GROUP BY ra.award_name, COALESCE(ra.player_guid, pcs.player_guid)
            ORDER BY ra.award_name, total_value DESC
        """

        results = await self.db.fetch_all(query, tuple(session_ids))

        # Group by award name
        awards_by_name: Dict[str, List[Tuple[str, str, float, int]]] = {}
        for row in results:
            award_name = row[0]
            player_guid = row[1] or "unknown"
            player_name = row[2] or "Unknown"
            total_value = row[3] or 0.0
            win_count = row[4] or 0

            if award_name not in awards_by_name:
                awards_by_name[award_name] = []
            awards_by_name[award_name].append((player_guid, player_name, total_value, win_count))

        return awards_by_name

    async def aggregate_session_vs_stats(
        self, session_ids: List[int], session_ids_str: str
    ) -> List[Tuple[str, str, int, int]]:
        """Aggregate VS stats (player vs player matchups) across session rounds.

        Args:
            session_ids: List of round IDs in the session
            session_ids_str: Comma-separated string of round IDs for SQL

        Returns:
            List of (player_guid, player_name, total_kills, total_deaths) sorted by kills DESC
        """
        if not session_ids:
            return []

        placeholders = ",".join(["$" + str(i + 1) for i in range(len(session_ids))])

        query = f"""
            SELECT
                COALESCE(vs.player_guid, pcs.player_guid) as player_guid,
                MAX(COALESCE(vs.player_name, pcs.player_name)) as player_name,
                SUM(vs.kills) as total_kills,
                SUM(vs.deaths) as total_deaths
            FROM round_vs_stats vs
            LEFT JOIN player_comprehensive_stats pcs
                ON vs.round_id = pcs.round_id AND vs.player_name = pcs.player_name
            WHERE vs.round_id IN ({placeholders})
            GROUP BY COALESCE(vs.player_guid, pcs.player_guid)
            ORDER BY total_kills DESC
            LIMIT 5
        """

        results = await self.db.fetch_all(query, tuple(session_ids))

        vs_stats = []
        for row in results:
            player_guid = row[0] or "unknown"
            player_name = row[1] or "Unknown"
            total_kills = row[2] or 0
            total_deaths = row[3] or 0
            vs_stats.append((player_guid, player_name, total_kills, total_deaths))

        return vs_stats

    def _categorize_awards(
        self, awards_by_name: Dict[str, List[Tuple[str, str, float, int]]]
    ) -> Dict[str, Dict[str, List[Tuple[str, str, float, int]]]]:
        """Categorize awards by their category from AWARD_CATEGORIES.

        Args:
            awards_by_name: Dict of award_name -> player data

        Returns:
            Dict of category -> award_name -> player data
        """
        categorized: Dict[str, Dict[str, List[Tuple[str, str, float, int]]]] = {}

        # Build reverse lookup: award_name -> category
        award_to_category = {}
        for category, award_list in AWARD_CATEGORIES.items():
            for award_name in award_list:
                award_to_category[award_name] = category

        for award_name, players in awards_by_name.items():
            category = award_to_category.get(award_name, "other")
            if category not in categorized:
                categorized[category] = {}
            categorized[category][award_name] = players

        return categorized

    def _format_value(self, value: float, award_name: str) -> str:
        """Format award value for display.

        Args:
            value: Numeric value
            award_name: Award name for context

        Returns:
            Formatted string (e.g., "3.2K", "52%", "2:30")
        """
        name_lc = award_name.lower()

        # Accuracy awards: show as percentage
        if "accuracy" in name_lc:
            return f"{value:.0f}%"

        # Time-related awards: show as m:ss
        if "time" in name_lc or "spawn" in name_lc:
            minutes = int(value // 60)
            seconds = int(value % 60)
            return f"{minutes}:{seconds:02d}"

        # Ratio awards
        if "ratio" in name_lc:
            return f"{value:.2f}"

        # Damage-related awards: show in K format
        if "damage" in name_lc:
            if value >= 1000:
                return f"{value/1000:.1f}K"

        # Default formatting
        if value >= 1000:
            return f"{value/1000:.1f}K"
        if value == int(value):
            return str(int(value))
        return f"{value:.1f}"

    def build_round_awards_display(
        self,
        awards: List[Dict[str, Any]],
        *,
        max_per_category: Optional[int] = 2,
        max_total: Optional[int] = 30,
    ) -> str:
        """
        Build a readable per-round awards display.

        Args:
            awards: List of award dicts with keys: name, player, value, numeric
            max_per_category: Limit awards per category (None for all)
            max_total: Hard cap on total lines (None for unlimited)
        """
        if not awards:
            return "*No awards recorded for this round*"

        # Build reverse lookup: award_name -> category
        award_to_category = {}
        for category, award_list in AWARD_CATEGORIES.items():
            for award_name in award_list:
                award_to_category[award_name] = category

        categorized: Dict[str, List[Dict[str, Any]]] = {}
        for award in awards:
            category = award_to_category.get(award.get("name"), "other")
            categorized.setdefault(category, []).append(award)

        # Sort categories by display priority, then "other" last
        ordered_categories = sorted(
            [c for c in categorized.keys() if c in CATEGORY_DISPLAY],
            key=lambda c: CATEGORY_DISPLAY[c][1],
        )
        if "other" in categorized:
            ordered_categories.append("other")

        lines: List[str] = []
        total_lines = 0

        for category in ordered_categories:
            awards_list = categorized.get(category, [])
            if not awards_list:
                continue

            display_name = CATEGORY_DISPLAY.get(category, ("Other", 999))[0]
            lines.append(f"**{display_name}**")
            total_lines += 1

            # Keep stable ordering
            awards_list = sorted(
                awards_list,
                key=lambda a: (a.get("name") or "", a.get("numeric") or 0),
            )

            count = 0
            for award in awards_list:
                if max_per_category is not None and count >= max_per_category:
                    break
                award_name = award.get("name") or "Unknown"
                player = award.get("player") or "Unknown"
                numeric = award.get("numeric")
                value = award.get("value")
                if numeric is not None:
                    formatted = self._format_value(float(numeric), award_name)
                else:
                    formatted = value or ""
                lines.append(f"• {award_name}: `{player}` ({formatted})")
                count += 1
                total_lines += 1
                if max_total is not None and total_lines >= max_total:
                    lines.append("• …and more")
                    return "\n".join(lines)

        return "\n".join(lines)

    async def aggregate_session_endstats(
        self, session_ids: List[int], session_ids_str: str
    ) -> Dict[str, Any]:
        """Aggregate all endstats data for a session.

        This is the main entry point for the LastSessionCog.

        Args:
            session_ids: List of round IDs in the session
            session_ids_str: Comma-separated string of round IDs for SQL

        Returns:
            Dict with:
                - has_data: bool
                - rounds_with_endstats: int
                - total_rounds: int
                - awards_by_category: categorized award data
                - vs_stats: list of top VS performers
        """
        # Check availability first
        has_data, rounds_with_endstats, total_rounds = await self.check_endstats_available(
            session_ids
        )

        if not has_data:
            return {"has_data": False}

        # Aggregate awards and VS stats
        awards_by_name = await self.aggregate_session_awards(session_ids, session_ids_str)
        vs_stats = await self.aggregate_session_vs_stats(session_ids, session_ids_str)

        # Categorize awards
        awards_by_category = self._categorize_awards(awards_by_name)

        return {
            "has_data": True,
            "rounds_with_endstats": rounds_with_endstats,
            "total_rounds": total_rounds,
            "awards_by_category": awards_by_category,
            "vs_stats": vs_stats,
        }

    def build_awards_display(
        self, awards_by_category: Dict[str, Dict[str, List[Tuple[str, str, float, int]]]],
        max_categories: int = 4,
        max_awards_per_category: int = 2
    ) -> str:
        """Build compact display string for awards.

        Args:
            awards_by_category: Categorized award data
            max_categories: Maximum categories to show
            max_awards_per_category: Maximum awards per category

        Returns:
            Formatted string for Discord embed field
        """
        if not awards_by_category:
            return ""

        lines = []

        # Sort categories by priority
        sorted_categories = sorted(
            awards_by_category.keys(),
            key=lambda c: CATEGORY_DISPLAY.get(c, (c, 99))[1]
        )

        for category in sorted_categories[:max_categories]:
            if category not in CATEGORY_DISPLAY:
                continue

            display_name, _ = CATEGORY_DISPLAY[category]
            awards = awards_by_category[category]

            # Get top award for this category (by total value)
            top_awards = []
            for award_name, players in list(awards.items())[:max_awards_per_category]:
                if players:
                    top_player = players[0]  # Already sorted by value DESC
                    player_name = top_player[1]
                    total_value = top_player[2]
                    win_count = top_player[3]

                    formatted_value = self._format_value(total_value, award_name)
                    top_awards.append(f"{player_name} ({formatted_value}, {win_count}x)")

            if top_awards:
                lines.append(f"**{display_name}:** {', '.join(top_awards)}")

        return "\n".join(lines)

    def build_vs_stats_display(self, vs_stats: List[Tuple[str, str, int, int]]) -> str:
        """Build compact display string for VS stats.

        Args:
            vs_stats: List of (player_guid, player_name, total_kills, total_deaths)

        Returns:
            Formatted string for Discord embed field
        """
        if not vs_stats:
            return ""

        parts = []
        for _, player_name, kills, deaths in vs_stats[:5]:
            parts.append(f"{player_name} {kills}K/{deaths}D")

        return " | ".join(parts)
