"""
File Repository - Data access layer for processed files

Handles all database queries related to file tracking and processing status.
Implements the Repository Pattern to separate data access from business logic.
"""

import logging
from typing import Set

logger = logging.getLogger("bot.repositories.file_repository")


class FileRepository:
    """Repository for processed files data access"""

    def __init__(self, db_adapter):
        """
        Initialize file repository

        Args:
            db_adapter: Database adapter (PostgreSQL or SQLite)
        """
        self.db_adapter = db_adapter

    async def get_processed_filenames(self) -> Set[str]:
        """
        Get all successfully processed filenames from database

        This is used by the cache refresher to keep the in-memory cache
        in sync with the database state.

        Returns:
            Set[str]: Set of filenames that were successfully processed

        Example:
            >>> filenames = await repo.get_processed_filenames()
            >>> print(filenames)
            {'2025-11-27-183045-goldrush-round-1.txt', ...}
        """
        try:
            # Query works for both SQLite and PostgreSQL
            # SQLite: success = 1 (integer)
            # PostgreSQL: success = true (boolean, but 1 works too)
            query = "SELECT filename FROM processed_files WHERE success = 1"
            rows = await self.db_adapter.fetch_all(query)

            # Convert rows to set of filenames
            filenames = {row[0] for row in rows}

            logger.debug(f"Loaded {len(filenames)} processed filenames from database")
            return filenames

        except Exception as e:
            logger.error(f"Error loading processed filenames: {e}")
            return set()  # Return empty set on error to allow bot to continue
