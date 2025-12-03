"""
Player Formatter Service - Global utility for consistent player display
========================================================================

This service provides consistent player formatting across ALL bot commands:
- Achievement badges (🏥 medic, 🔧 engineer, 🎯 sharpshooter, etc.)
- Custom display names for linked players
- Fallback to in-game names

Usage in any command:
    from bot.services.player_formatter import PlayerFormatter

    formatter = PlayerFormatter(db_adapter)
    formatted_name = await formatter.format_player(player_guid, player_name)
    # Returns: "CustomName 🏥🔧" or "PlayerName 🎯"

    # Batch format (more efficient)
    players = await formatter.format_players(player_list)
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("bot.services.player_formatter")


class PlayerFormatter:
    """Global service for formatting player names with badges and custom names"""

    def __init__(self, db_adapter, badge_service=None):
        """
        Initialize the player formatter

        Args:
            db_adapter: Database adapter for queries
            badge_service: Optional PlayerBadgeService instance (created if not provided)
        """
        self.db_adapter = db_adapter
        self._display_name_cache = {}

        # Delegate badge logic to PlayerBadgeService
        if badge_service is None:
            from bot.services.player_badge_service import PlayerBadgeService
            badge_service = PlayerBadgeService(db_adapter)
        self.badge_service = badge_service

    async def get_player_badges(self, player_guid: str, session_stats: Optional[Dict] = None) -> str:
        """
        Get achievement badges for a player.

        Delegates to PlayerBadgeService for consistent badge logic across the bot.

        Args:
            player_guid: Player GUID
            session_stats: Optional pre-fetched stats dict (ignored, kept for API compatibility)

        Returns:
            String of badge emojis (e.g., "💀🏆📈") or empty string
        """
        return await self.badge_service.get_player_badges(player_guid)

    async def get_display_name(self, player_guid: str, fallback_name: str) -> str:
        """
        Get custom display name or fallback to in-game name

        Args:
            player_guid: Player GUID
            fallback_name: In-game name to use if no custom name set

        Returns:
            Display name string
        """
        # Check cache first
        if player_guid in self._display_name_cache:
            cached = self._display_name_cache[player_guid]
            return cached if cached else fallback_name

        try:
            result = await self.db_adapter.fetch_one("""
                SELECT display_name
                FROM player_links
                WHERE player_guid = ? AND display_name IS NOT NULL
            """, (player_guid,))

            if result and result[0]:
                self._display_name_cache[player_guid] = result[0]
                return result[0]
            else:
                self._display_name_cache[player_guid] = None
                return fallback_name

        except Exception as e:
            logger.debug(f"No custom display name for {player_guid}: {e}")
            return fallback_name

    async def format_player(
        self,
        player_guid: str,
        player_name: str,
        include_badges: bool = True,
        session_stats: Optional[Dict] = None
    ) -> str:
        """
        Format a single player name with custom name and badges

        Args:
            player_guid: Player GUID
            player_name: In-game player name
            include_badges: Whether to include achievement badges (default: True)
            session_stats: Optional pre-fetched stats for badges

        Returns:
            Formatted player string: "CustomName 🏥🔧" or "PlayerName"
        """
        # Get custom display name or use in-game name
        display_name = await self.get_display_name(player_guid, player_name)

        # Get badges if requested
        badges = ""
        if include_badges:
            badges = await self.get_player_badges(player_guid, session_stats)
            if badges:
                badges = f" {badges}"

        return f"{display_name}{badges}"

    async def format_players_batch(
        self,
        players: List[Tuple[str, str]],
        include_badges: bool = True
    ) -> Dict[str, str]:
        """
        Format multiple players efficiently (batched queries)

        Args:
            players: List of (player_guid, player_name) tuples
            include_badges: Whether to include achievement badges

        Returns:
            Dict mapping player_guid to formatted name string
        """
        if not players:
            return {}

        result = {}

        # Batch fetch display names
        guids = [p[0] for p in players]
        placeholders = ','.join(['?' for _ in guids])

        try:
            display_names = await self.db_adapter.fetch_all("""
                SELECT player_guid, display_name
                FROM player_links
                WHERE player_guid IN ({placeholders})
                AND display_name IS NOT NULL
            """, tuple(guids))

            display_name_map = {row[0]: row[1] for row in display_names}
        except Exception as e:
            logger.error(f"Error batch fetching display names: {e}")
            display_name_map = {}

        # Batch fetch stats for badges if requested
        badge_map = {}
        if include_badges:
            try:
                stats = await self.db_adapter.fetch_all("""
                    SELECT
                        player_guid,
                        SUM(revives_given) as total_revives,
                        SUM(constructions) as total_constructions,
                        SUM(headshot_kills) as total_headshots,
                        SUM(kills) as total_kills,
                        SUM(dynamites_planted) as total_dynamites,
                        SUM(mega_kills) as total_mg_kills
                    FROM player_comprehensive_stats
                    WHERE player_guid IN ({placeholders})
                    GROUP BY player_guid
                """, tuple(guids))

                for row in stats:
                    guid = row[0]
                    session_stats = {
                        'revives': row[1] or 0,
                        'constructions': row[2] or 0,
                        'headshots': row[3] or 0,
                        'kills': row[4] or 0,
                        'dynamites': row[5] or 0,
                        'mg_kills': row[6] or 0
                    }
                    badge_map[guid] = await self.get_player_badges(guid, session_stats)
            except Exception as e:
                logger.error(f"Error batch fetching badges: {e}")

        # Format each player
        for guid, name in players:
            display_name = display_name_map.get(guid, name)
            badges = badge_map.get(guid, '') if include_badges else ''
            result[guid] = f"{display_name}{' ' + badges if badges else ''}"

        return result

    def clear_cache(self):
        """Clear the internal caches (call after database updates)"""
        self._badge_cache.clear()
        self._display_name_cache.clear()
        logger.debug("Player formatter caches cleared")
