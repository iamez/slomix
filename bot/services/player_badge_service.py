"""
Player Badge Service - Achievement Badge Display
=================================================
Fetches and formats player achievement badges for display in session stats.

Provides emoji badges based on player lifetime achievements:

**Core Achievements:**
- Kill milestones: 🎯 (1K) 💀 (5K) ☠️ (10K) 👑 (20K)
- Game milestones: 🎮 (50) 🕹️ (500) 🏆 (5K) ⭐ (10K) 💎 (30K)
- K/D milestones: 📉 (-0.5) ⚰️ (0.0) ⚖️ (1.0) 📈 (1.5) 🔥 (2.0) ⚡ (2.5) 💯 (3.0)

**Phase 1: Support & Objectives:**
- Revives given: 💉 (100) 🏥 (500) ⚕️ (5K)
- Times revived: 🔄 (100) ♻️ (500) 🔁 (3K)
- Dynamites planted: 💣 (50) 🧨 (200) 💥 (1K)
- Dynamites defused: 🛡️ (50) 🔰 (200) 🏛️ (1K)
- Objectives (stolen+returned): 🚩 (25) 🎖️ (250) 🏅 (2.5K)

**Future Phase 2:**
- Record holders (most kills in round/map/month/year)
- Weapon mastery (MP40/Thompson accuracy)
- DPM records
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger("bot.services.player_badge_service")


class PlayerBadgeService:
    """Service for fetching and formatting player achievement badges"""

    # Achievement thresholds (from AchievementSystem)
    KILL_MILESTONES = {
        1000: "🎯",
        5000: "💀",
        10000: "☠️",
        20000: "👑",
    }

    GAME_MILESTONES = {
        50: "🎮",
        500: "🕹️",
        5000: "🏆",
        10000: "⭐",
        30000: "💎",
    }

    KD_MILESTONES = {
        -0.5: "📉",
        0.0: "⚰️",
        1.0: "⚖️",
        1.5: "📈",
        2.0: "🔥",
        2.5: "⚡",
        3.0: "💯",
    }

    # Phase 1: Support & Objective Milestones
    REVIVE_MILESTONES = {
        100: "💉",
        500: "🏥",
        5000: "⚕️",
    }

    TIMES_REVIVED_MILESTONES = {
        100: "🔄",
        500: "♻️",
        3000: "🔁",
    }

    DYNAMITE_PLANTED_MILESTONES = {
        50: "💣",
        200: "🧨",
        1000: "💥",
    }

    DYNAMITE_DEFUSED_MILESTONES = {
        50: "🛡️",
        200: "🔰",
        1000: "🏛️",
    }

    OBJECTIVE_MILESTONES = {
        25: "🚩",
        250: "🎖️",
        2500: "🏅",
    }

    def __init__(self, db_adapter):
        """
        Initialize the PlayerBadgeService.

        Args:
            db_adapter: Database adapter for queries
        """
        self.db_adapter = db_adapter

    async def get_player_badges(self, player_guid: str) -> str:
        """
        Get all achievement badges for a player.

        Args:
            player_guid: Player's ET GUID

        Returns:
            String of emoji badges (e.g., "💀🏆📈" or "" if no achievements)
        """
        try:
            # Get player lifetime stats including support/objectives
            query = """
                SELECT
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths,
                    COUNT(DISTINCT p.round_id) as total_games,
                    CASE
                        WHEN SUM(p.deaths) > 0
                        THEN CAST(SUM(p.kills) AS REAL) / SUM(p.deaths)
                        ELSE SUM(p.kills)
                    END as overall_kd,
                    SUM(p.revives_given) as total_revives,
                    SUM(p.times_revived) as total_times_revived,
                    SUM(p.dynamites_planted) as total_dyns_planted,
                    SUM(p.dynamites_defused) as total_dyns_defused,
                    (SUM(p.objectives_stolen) + SUM(p.objectives_returned)) as total_objectives
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid = ?
                  AND r.round_number IN (1, 2)
                  AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            """

            # Use parameterized query for both SQLite and PostgreSQL
            result = await self.db_adapter.fetch_one(query, (player_guid,))

            if not result or result[0] is None:
                return ""

            (kills, deaths, games, kd_ratio, revives, times_revived,
             dyns_planted, dyns_defused, objectives) = result

            badges = []

            # Core achievements (kills, games, K/D)
            kill_badge = self._get_highest_milestone(kills or 0, self.KILL_MILESTONES)
            if kill_badge:
                badges.append(kill_badge)

            game_badge = self._get_highest_milestone(games or 0, self.GAME_MILESTONES)
            if game_badge:
                badges.append(game_badge)

            if games >= 20:
                kd_badge = self._get_highest_milestone(kd_ratio or 0, self.KD_MILESTONES)
                if kd_badge:
                    badges.append(kd_badge)

            # Phase 1: Support & Objective achievements
            revive_badge = self._get_highest_milestone(revives or 0, self.REVIVE_MILESTONES)
            if revive_badge:
                badges.append(revive_badge)

            revived_badge = self._get_highest_milestone(times_revived or 0, self.TIMES_REVIVED_MILESTONES)
            if revived_badge:
                badges.append(revived_badge)

            dyn_plant_badge = self._get_highest_milestone(dyns_planted or 0, self.DYNAMITE_PLANTED_MILESTONES)
            if dyn_plant_badge:
                badges.append(dyn_plant_badge)

            dyn_defuse_badge = self._get_highest_milestone(dyns_defused or 0, self.DYNAMITE_DEFUSED_MILESTONES)
            if dyn_defuse_badge:
                badges.append(dyn_defuse_badge)

            obj_badge = self._get_highest_milestone(objectives or 0, self.OBJECTIVE_MILESTONES)
            if obj_badge:
                badges.append(obj_badge)

            # Stack duplicate badges (e.g., 🎯 appears in kills, games, and objectives)
            return self._format_badges_with_stacking(badges)

        except Exception as e:
            logger.error(f"Error fetching badges for {player_guid}: {e}", exc_info=True)
            return ""

    def _get_highest_milestone(self, value: float, milestones: Dict[int, str]) -> Optional[str]:
        """
        Get the highest milestone achieved for a given value.

        Args:
            value: Current player value (kills, games, K/D)
            milestones: Dictionary of thresholds and their emoji badges

        Returns:
            Emoji badge for highest milestone achieved, or None
        """
        highest = None
        for threshold, badge in sorted(milestones.items(), reverse=True):
            if value >= threshold:
                highest = badge
                break
        return highest

    def _format_badges_with_stacking(self, badges: List[str]) -> str:
        """
        Format badges with stacking notation for duplicates.

        If the same emoji appears multiple times (e.g., 🎯 from kills, games, and objectives),
        show it once with a count: 🎯x3

        Args:
            badges: List of badge emojis

        Returns:
            Formatted badge string with stacking (e.g., "🎯x3💀🏆x2")
        """
        if not badges:
            return ""

        # Count occurrences of each badge
        badge_counts = {}
        for badge in badges:
            badge_counts[badge] = badge_counts.get(badge, 0) + 1

        # Format with stacking notation
        formatted = []
        for badge, count in badge_counts.items():
            if count > 1:
                formatted.append(f"{badge}x{count}")
            else:
                formatted.append(badge)

        return "".join(formatted)

    async def get_player_badges_batch(self, player_guids: List[str]) -> Dict[str, str]:
        """
        Get badges for multiple players in a single query.

        Args:
            player_guids: List of player GUIDs

        Returns:
            Dictionary mapping GUID -> badge string
        """
        if not player_guids:
            return {}

        try:
            # Build placeholders for IN clause (safe: no user input in placeholder string)
            placeholders = ",".join("?" * len(player_guids))

            # Safe: placeholders are "?" only, user data passed via parameterized tuple
            query = f"""
                SELECT
                    p.player_guid,
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths,
                    COUNT(DISTINCT p.round_id) as total_games,
                    CASE
                        WHEN SUM(p.deaths) > 0
                        THEN CAST(SUM(p.kills) AS REAL) / SUM(p.deaths)
                        ELSE SUM(p.kills)
                    END as overall_kd,
                    SUM(p.revives_given) as total_revives,
                    SUM(p.times_revived) as total_times_revived,
                    SUM(p.dynamites_planted) as total_dyns_planted,
                    SUM(p.dynamites_defused) as total_dyns_defused,
                    (SUM(p.objectives_stolen) + SUM(p.objectives_returned)) as total_objectives
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid IN ({placeholders})
                  AND r.round_number IN (1, 2)
                  AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                GROUP BY p.player_guid
            """  # nosec B608

            results = await self.db_adapter.fetch_all(query, tuple(player_guids))

            badge_map = {}
            for row in results:
                (guid, kills, deaths, games, kd_ratio, revives, times_revived,
                 dyns_planted, dyns_defused, objectives) = row
                badges = []

                # Core achievements
                kill_badge = self._get_highest_milestone(kills or 0, self.KILL_MILESTONES)
                if kill_badge:
                    badges.append(kill_badge)

                game_badge = self._get_highest_milestone(games or 0, self.GAME_MILESTONES)
                if game_badge:
                    badges.append(game_badge)

                if games >= 20:
                    kd_badge = self._get_highest_milestone(kd_ratio or 0, self.KD_MILESTONES)
                    if kd_badge:
                        badges.append(kd_badge)

                # Phase 1: Support & Objective achievements
                revive_badge = self._get_highest_milestone(revives or 0, self.REVIVE_MILESTONES)
                if revive_badge:
                    badges.append(revive_badge)

                revived_badge = self._get_highest_milestone(times_revived or 0, self.TIMES_REVIVED_MILESTONES)
                if revived_badge:
                    badges.append(revived_badge)

                dyn_plant_badge = self._get_highest_milestone(dyns_planted or 0, self.DYNAMITE_PLANTED_MILESTONES)
                if dyn_plant_badge:
                    badges.append(dyn_plant_badge)

                dyn_defuse_badge = self._get_highest_milestone(dyns_defused or 0, self.DYNAMITE_DEFUSED_MILESTONES)
                if dyn_defuse_badge:
                    badges.append(dyn_defuse_badge)

                obj_badge = self._get_highest_milestone(objectives or 0, self.OBJECTIVE_MILESTONES)
                if obj_badge:
                    badges.append(obj_badge)

                badge_map[guid] = self._format_badges_with_stacking(badges)

            return badge_map

        except Exception as e:
            logger.error(f"Error fetching badges batch: {e}", exc_info=True)
            return {}
