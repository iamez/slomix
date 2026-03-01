"""
File Repository - Data access layer for processed files

Handles all database queries related to file tracking and processing status.
Implements the Repository Pattern to separate data access from business logic.
"""

import logging
from datetime import datetime
from typing import Set

logger = logging.getLogger("bot.repositories.file_repository")


class FileRepository:
    """Repository for processed files data access"""

    def __init__(self, db_adapter, config):
        """
        Initialize file repository

        Args:
            db_adapter: Database adapter (PostgreSQL or SQLite)
            config: Bot configuration object
        """
        self.db_adapter = db_adapter
        self.config = config

    async def get_processed_filenames(self) -> Set[str]:
        """
        Get all successfully processed filenames from database.

        Used once at startup to populate the in-memory cache.
        After startup, use get_newly_processed_filenames() for incremental updates.

        Returns:
            Set[str]: Set of filenames that were successfully processed
        """
        try:
            if self.config.database_type == "sqlite":
                query = "SELECT filename FROM processed_files WHERE success = 1"
            else:
                query = "SELECT filename FROM processed_files WHERE success = true"

            rows = await self.db_adapter.fetch_all(query)
            filenames = {row[0] for row in rows}

            logger.debug(f"Loaded {len(filenames)} processed filenames from database")
            return filenames

        except Exception as e:
            logger.error(f"Error loading processed filenames: {e}")
            return set()

    async def get_newly_processed_filenames(self, since: datetime) -> Set[str]:
        """
        Get filenames processed since a given timestamp (incremental delta).

        Returns only new entries, avoiding a full table scan on every cycle.

        Args:
            since: Only return filenames processed after this timestamp

        Returns:
            Set[str]: Set of newly processed filenames
        """
        try:
            if self.config.database_type == "sqlite":
                query = "SELECT filename FROM processed_files WHERE success = 1 AND processed_at > ?"
            else:
                query = "SELECT filename FROM processed_files WHERE success = true AND processed_at > $1"

            rows = await self.db_adapter.fetch_all(query, (since,))
            filenames = {row[0] for row in rows}

            if filenames:
                logger.debug(f"Found {len(filenames)} newly processed filenames since {since}")
            return filenames

        except Exception as e:
            logger.error(f"Error loading newly processed filenames: {e}")
            return set()
