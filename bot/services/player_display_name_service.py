"""
Player Display Name Service
============================
Manages custom display names for linked players.

Display Name Priority:
1. Custom display_name (if set by player)
2. Most recent alias from player_aliases
3. Fallback to player_comprehensive_stats.player_name

Players must be linked (discord_id) to set custom names.
"""

import logging
from typing import Dict, List, Tuple
from datetime import datetime

logger = logging.getLogger("bot.services.player_display_name_service")


class PlayerDisplayNameService:
    """Service for managing player display names"""

    def __init__(self, db_adapter):
        """
        Initialize the PlayerDisplayNameService.

        Args:
            db_adapter: Database adapter for queries
        """
        self.db_adapter = db_adapter

    async def get_display_name(self, player_guid: str) -> str:
        """
        Get the display name for a player.

        Priority:
        1. Custom display_name from player_links (if linked and set)
        2. Most recent alias from player_aliases
        3. Fallback to any player_name from stats

        Args:
            player_guid: Player's ET GUID

        Returns:
            Display name string
        """
        try:
            # Check if player is linked and has custom display_name
            link_query = """
                SELECT display_name, display_name_source
                FROM player_links
                WHERE player_guid = ?
            """
            link_result = await self.db_adapter.fetch_one(link_query, (player_guid,))

            if link_result and link_result[0]:
                # Player has custom display name set
                return link_result[0]

            # Get most recent alias
            alias_query = """
                SELECT alias
                FROM player_aliases
                WHERE guid = ?
                ORDER BY last_seen DESC
                LIMIT 1
            """
            alias_result = await self.db_adapter.fetch_one(alias_query, (player_guid,))

            if alias_result and alias_result[0]:
                return alias_result[0]

            # Fallback to any name from stats
            stats_query = """
                SELECT player_name
                FROM player_comprehensive_stats
                WHERE player_guid = ?
                LIMIT 1
            """
            stats_result = await self.db_adapter.fetch_one(stats_query, (player_guid,))

            if stats_result and stats_result[0]:
                return stats_result[0]

            # Ultimate fallback
            return "Unknown Player"

        except Exception as e:
            logger.error(f"Error getting display name for {player_guid}: {e}", exc_info=True)
            return "Unknown Player"

    async def get_display_names_batch(self, player_guids: List[str]) -> Dict[str, str]:
        """
        Get display names for multiple players efficiently.

        Args:
            player_guids: List of player GUIDs

        Returns:
            Dictionary mapping GUID -> display name
        """
        if not player_guids:
            return {}

        try:
            # Build placeholders for IN clause (safe: no user input in placeholder string)
            placeholders = ",".join("?" * len(player_guids))

            # Get all custom display names
            # Safe: placeholders are "?" only, user data passed via tuple
            link_query = f"""
                SELECT player_guid, display_name
                FROM player_links
                WHERE player_guid IN ({placeholders})
                  AND display_name IS NOT NULL
            """  # nosec B608
            link_results = await self.db_adapter.fetch_all(link_query, tuple(player_guids))
            display_names = {row[0]: row[1] for row in link_results}

            # Get most recent aliases for players without custom names
            remaining_guids = [guid for guid in player_guids if guid not in display_names]

            if remaining_guids:
                # Build placeholders for remaining GUIDs (safe: no user input)
                alias_placeholders = ",".join("?" * len(remaining_guids))
                # Safe: placeholders are "?" only, user data passed via tuple
                alias_query = f"""
                    SELECT DISTINCT ON (guid) guid, alias
                    FROM player_aliases
                    WHERE guid IN ({alias_placeholders})
                    ORDER BY guid, last_seen DESC
                """  # nosec B608
                # Note: DISTINCT ON is PostgreSQL syntax
                # For SQLite, use a different approach
                try:
                    alias_results = await self.db_adapter.fetch_all(alias_query, tuple(remaining_guids))
                    for row in alias_results:
                        if row[0] not in display_names:
                            display_names[row[0]] = row[1]
                except Exception:
                    # Fallback for SQLite
                    for guid in remaining_guids:
                        if guid not in display_names:
                            name = await self.get_display_name(guid)
                            display_names[guid] = name

            # Ensure all GUIDs have a name
            for guid in player_guids:
                if guid not in display_names:
                    display_names[guid] = "Unknown Player"

            return display_names

        except Exception as e:
            logger.error(f"Error getting display names batch: {e}", exc_info=True)
            # Fallback: return empty dict, caller should handle
            return {}

    async def set_custom_display_name(
        self,
        discord_id: int,
        display_name: str
    ) -> Tuple[bool, str]:
        """
        Set a custom display name for a linked player.

        Args:
            discord_id: Discord user ID
            display_name: Custom name to set

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Validate name length
            if len(display_name) < 2:
                return False, "Display name must be at least 2 characters"
            if len(display_name) > 32:
                return False, "Display name must be 32 characters or less"

            # Check if player is linked
            check_query = """
                SELECT player_guid
                FROM player_links
                WHERE discord_id = ?
            """
            result = await self.db_adapter.fetch_one(check_query, (discord_id,))

            if not result:
                return False, "You must be linked to a player first. Use `!link` to link your account."

            # Update display name
            update_query = """
                UPDATE player_links
                SET display_name = ?,
                    display_name_source = 'custom',
                    display_name_updated_at = ?
                WHERE discord_id = ?
            """
            await self.db_adapter.execute(
                update_query,
                (display_name, datetime.now(), discord_id)
            )

            return True, f"Display name set to **{display_name}**"

        except Exception as e:
            logger.error(f"Error setting custom display name: {e}", exc_info=True)
            return False, f"Error setting display name: {e}"

    async def set_alias_display_name(
        self,
        discord_id: int,
        alias_name: str
    ) -> Tuple[bool, str]:
        """
        Set display name to one of player's aliases.

        Args:
            discord_id: Discord user ID
            alias_name: Alias to use as display name

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Get player GUID
            link_query = """
                SELECT player_guid
                FROM player_links
                WHERE discord_id = ?
            """
            link_result = await self.db_adapter.fetch_one(link_query, (discord_id,))

            if not link_result:
                return False, "You must be linked to a player first. Use `!link` to link your account."

            player_guid = link_result[0]

            # Check if alias exists for this player
            alias_query = """
                SELECT alias
                FROM player_aliases
                WHERE guid = ? AND LOWER(alias) = LOWER(?)
            """
            alias_result = await self.db_adapter.fetch_one(
                alias_query,
                (player_guid, alias_name)
            )

            if not alias_result:
                return False, f"Alias **{alias_name}** not found. Use `!myaliases` to see available aliases."

            # Use the exact alias from database (preserves capitalization)
            exact_alias = alias_result[0]

            # Update display name
            update_query = """
                UPDATE player_links
                SET display_name = ?,
                    display_name_source = 'alias',
                    display_name_updated_at = ?
                WHERE discord_id = ?
            """
            await self.db_adapter.execute(
                update_query,
                (exact_alias, datetime.now(), discord_id)
            )

            return True, f"Display name set to **{exact_alias}** (from your aliases)"

        except Exception as e:
            logger.error(f"Error setting alias display name: {e}", exc_info=True)
            return False, f"Error setting display name: {e}"

    async def reset_display_name(self, discord_id: int) -> Tuple[bool, str]:
        """
        Reset display name to auto (most recent alias).

        Args:
            discord_id: Discord user ID

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Check if player is linked
            check_query = """
                SELECT player_guid
                FROM player_links
                WHERE discord_id = ?
            """
            result = await self.db_adapter.fetch_one(check_query, (discord_id,))

            if not result:
                return False, "You must be linked to a player first."

            # Reset to NULL (auto mode)
            update_query = """
                UPDATE player_links
                SET display_name = NULL,
                    display_name_source = 'auto',
                    display_name_updated_at = ?
                WHERE discord_id = ?
            """
            await self.db_adapter.execute(
                update_query,
                (datetime.now(), discord_id)
            )

            return True, "Display name reset to automatic (most recent alias)"

        except Exception as e:
            logger.error(f"Error resetting display name: {e}", exc_info=True)
            return False, f"Error resetting display name: {e}"

    async def get_player_aliases(self, discord_id: int) -> Tuple[bool, List[Tuple[str, int, str]]]:
        """
        Get all aliases for a linked player.

        Args:
            discord_id: Discord user ID

        Returns:
            Tuple of (success: bool, aliases: List[(alias, times_seen, last_seen)])
        """
        try:
            # Get player GUID
            link_query = """
                SELECT player_guid
                FROM player_links
                WHERE discord_id = ?
            """
            link_result = await self.db_adapter.fetch_one(link_query, (discord_id,))

            if not link_result:
                return False, []

            player_guid = link_result[0]

            # Get all aliases
            alias_query = """
                SELECT alias, times_seen, last_seen
                FROM player_aliases
                WHERE guid = ?
                ORDER BY last_seen DESC
            """
            results = await self.db_adapter.fetch_all(alias_query, (player_guid,))

            return True, results

        except Exception as e:
            logger.error(f"Error getting player aliases: {e}", exc_info=True)
            return False, []
