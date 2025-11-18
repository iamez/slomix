"""
Player Badge Service - Achievement Badge Display
=================================================
Fetches and formats player achievement badges for display in session stats.

Provides emoji badges based on player lifetime achievements:
- Kill milestones: 🎯 💥 💀 ⚔️ ☠️ 👑
- Game milestones: 🎮 🎯 🏆 ⭐ 💎 👑
- K/D milestones: ⚖️ 📈 🔥 💯

Future expansions:
- Revive milestones
- Objective milestones
- Record holders (most kills in round/map/month/year)
- Weapon mastery (MP40/Thompson accuracy)
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger("bot.services.player_badge_service")


class PlayerBadgeService:
    """Service for fetching and formatting player achievement badges"""

    # Achievement thresholds (from AchievementSystem)
    KILL_MILESTONES = {
        100: "🎯",
        500: "💥",
        1000: "💀",
        2500: "⚔️",
        5000: "☠️",
        10000: "👑",
    }

    GAME_MILESTONES = {
        10: "🎮",
        50: "🎯",
        100: "🏆",
        250: "⭐",
        500: "💎",
        1000: "👑",
    }

    KD_MILESTONES = {
        1.0: "⚖️",
        1.5: "📈",
        2.0: "🔥",
        3.0: "💯",
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
            # Get player lifetime stats
            query = """
                SELECT
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths,
                    COUNT(DISTINCT p.round_id) as total_games,
                    CASE
                        WHEN SUM(p.deaths) > 0
                        THEN CAST(SUM(p.kills) AS REAL) / SUM(p.deaths)
                        ELSE SUM(p.kills)
                    END as overall_kd
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

            kills, deaths, games, kd_ratio = result

            badges = []

            # Get highest kill milestone
            kill_badge = self._get_highest_milestone(kills, self.KILL_MILESTONES)
            if kill_badge:
                badges.append(kill_badge)

            # Get highest game milestone
            game_badge = self._get_highest_milestone(games, self.GAME_MILESTONES)
            if game_badge:
                badges.append(game_badge)

            # Get highest K/D milestone (only if 20+ games)
            if games >= 20:
                kd_badge = self._get_highest_milestone(kd_ratio, self.KD_MILESTONES)
                if kd_badge:
                    badges.append(kd_badge)

            return "".join(badges)

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
            # Build placeholders for IN clause
            placeholders = ",".join("?" * len(player_guids))

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
                    END as overall_kd
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid IN ({placeholders})
                  AND r.round_number IN (1, 2)
                  AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                GROUP BY p.player_guid
            """

            results = await self.db_adapter.fetch_all(query, tuple(player_guids))

            badge_map = {}
            for row in results:
                guid, kills, deaths, games, kd_ratio = row
                badges = []

                # Get highest achievements
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

                badge_map[guid] = "".join(badges)

            return badge_map

        except Exception as e:
            logger.error(f"Error fetching badges batch: {e}", exc_info=True)
            return {}
