"""
Local Database Adapter for Website Backend
Includes SQLite support for local development.
"""

import logging
from typing import Any, Optional, List, Tuple
from contextlib import asynccontextmanager

# Import base class from bot core
from bot.core.database_adapter import DatabaseAdapter

# SQLite support
try:
    import aiosqlite

    SQLITE_AVAILABLE = True
except ImportError:
    aiosqlite = None
    SQLITE_AVAILABLE = False

logger = logging.getLogger("LocalDatabaseAdapter")


class SQLiteAdapter(DatabaseAdapter):
    """SQLite database adapter using aiosqlite."""

    def __init__(self, db_path: str):
        """
        Initialize SQLite adapter.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        logger.info(f"📦 Local SQLite Adapter initialized: {db_path}")

    async def connect(self):
        """Initialize SQLite connection."""
        if not SQLITE_AVAILABLE:
            raise RuntimeError("aiosqlite not available - cannot connect to SQLite")
        pass

    async def close(self):
        """Close SQLite connection."""
        pass

    @asynccontextmanager
    async def connection(self):
        """Provide SQLite connection."""
        if not SQLITE_AVAILABLE:
            raise RuntimeError("aiosqlite not available")

        async with aiosqlite.connect(self.db_path) as conn:
            yield conn

    async def execute(self, query: str, params: Optional[Tuple] = None):
        """Execute query on SQLite."""
        async with self.connection() as conn:
            await conn.execute(query, params or ())
            await conn.commit()

    async def fetch_one(
        self, query: str, params: Optional[Tuple] = None
    ) -> Optional[Any]:
        """Fetch single row from SQLite."""
        async with self.connection() as conn:
            async with conn.execute(query, params or ()) as cursor:
                row = await cursor.fetchone()
                return row

    async def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Any]:
        """Fetch all rows from SQLite."""
        async with self.connection() as conn:
            async with conn.execute(query, params or ()) as cursor:
                rows = await cursor.fetchall()
                return rows

    async def fetch_val(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Fetch single value from SQLite."""
        async with self.connection() as conn:
            async with conn.execute(query, params or ()) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None


def create_local_adapter(db_type: str = "sqlite", **kwargs) -> DatabaseAdapter:
    """
    Factory function to create LOCAL database adapter (SQLite).
    """
    if db_type.lower() == "sqlite":
        return SQLiteAdapter(db_path=kwargs["db_path"])
    else:
        raise ValueError(
            f"Local adapter factory only supports 'sqlite', got: {db_type}"
        )
