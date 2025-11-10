"""
Database Abstraction Layer for SQLite and PostgreSQL
Provides transparent switching between database backends without code changes.
"""
import logging
from typing import Any, Optional, List, Tuple
from abc import ABC, abstractmethod
import aiosqlite
from contextlib import asynccontextmanager

# Optional: asyncpg for PostgreSQL support (only needed if using PostgreSQL)
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

logger = logging.getLogger('DatabaseAdapter')


class DatabaseAdapter(ABC):
    """Abstract base class for database adapters."""
    
    @abstractmethod
    async def connect(self):
        """Initialize database connection/pool."""
        pass
    
    @abstractmethod
    async def close(self):
        """Close database connection/pool."""
        pass
    
    @abstractmethod
    @asynccontextmanager
    async def connection(self):
        """Context manager for database connections."""
        pass
    
    @abstractmethod
    async def execute(self, query: str, params: Optional[Tuple] = None):
        """Execute a query without returning results."""
        pass
    
    @abstractmethod
    async def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Any]:
        """Fetch a single row."""
        pass
    
    @abstractmethod
    async def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Any]:
        """Fetch all rows."""
        pass
    
    @abstractmethod
    async def fetch_val(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Fetch a single value from first row."""
        pass
    
    def translate_query(self, query: str) -> str:
        """Translate query syntax if needed (override in subclasses)."""
        return query


class SQLiteAdapter(DatabaseAdapter):
    """SQLite database adapter using aiosqlite."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection = None
        logger.info(f"📦 SQLite Adapter initialized: {db_path}")
    
    async def connect(self):
        """Initialize SQLite connection."""
        # SQLite doesn't need explicit connection pool
        logger.info(f"✅ SQLite ready: {self.db_path}")
    
    async def close(self):
        """Close SQLite connection if exists."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("🔌 SQLite connection closed")
    
    @asynccontextmanager
    async def connection(self):
        """Provide SQLite connection context manager."""
        conn = await aiosqlite.connect(self.db_path)
        try:
            yield conn
        finally:
            await conn.close()
    
    async def execute(self, query: str, params: Optional[Tuple] = None):
        """Execute query on SQLite."""
        async with self.connection() as conn:
            await conn.execute(query, params or ())
            await conn.commit()
    
    async def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Any]:
        """Fetch one row from SQLite."""
        async with self.connection() as conn:
            cursor = await conn.execute(query, params or ())
            return await cursor.fetchone()
    
    async def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Any]:
        """Fetch all rows from SQLite."""
        async with self.connection() as conn:
            cursor = await conn.execute(query, params or ())
            return await cursor.fetchall()
    
    async def fetch_val(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Fetch single value from SQLite."""
        row = await self.fetch_one(query, params)
        return row[0] if row else None


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL database adapter using asyncpg."""
    
    def __init__(self, host: str, port: int, database: str, user: str, password: str,
                 min_pool_size: int = 5, max_pool_size: int = 20):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        self._pool = None
        
        # Check if asyncpg is available
        if not ASYNCPG_AVAILABLE:
            raise ImportError(
                "asyncpg is not installed. Install it with: pip install asyncpg>=0.29.0"
            )
        
        logger.info(f"🐘 PostgreSQL Adapter initialized: {user}@{host}:{port}/{database}")
    
    async def connect(self):
        """Initialize PostgreSQL connection pool."""
        if not ASYNCPG_AVAILABLE:
            raise ImportError("asyncpg is required for PostgreSQL support")
        
        self._pool = await asyncpg.create_pool(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
            min_size=self.min_pool_size,
            max_size=self.max_pool_size
        )
        logger.info(f"✅ PostgreSQL pool created: {self.min_pool_size}-{self.max_pool_size} connections")
    
    async def close(self):
        """Close PostgreSQL connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("🔌 PostgreSQL pool closed")
    
    @asynccontextmanager
    async def connection(self):
        """Provide PostgreSQL connection from pool."""
        if not self._pool:
            raise RuntimeError("PostgreSQL pool not initialized. Call connect() first.")
        async with self._pool.acquire() as conn:
            yield conn
    
    def translate_query(self, query: str) -> str:
        """
        Translate SQLite query syntax to PostgreSQL.
        Converts ? placeholders to $1, $2, $3, etc.
        """
        if '?' not in query:
            return query
        
        # Replace ? with $1, $2, $3...
        parts = query.split('?')
        translated = parts[0]
        for i, part in enumerate(parts[1:], 1):
            translated += f'${i}{part}'
        
        return translated
    
    async def execute(self, query: str, params: Optional[Tuple] = None):
        """Execute query on PostgreSQL."""
        query = self.translate_query(query)
        async with self.connection() as conn:
            await conn.execute(query, *(params or ()))
    
    async def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Any]:
        """Fetch one row from PostgreSQL."""
        query = self.translate_query(query)
        async with self.connection() as conn:
            return await conn.fetchrow(query, *(params or ()))
    
    async def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Any]:
        """Fetch all rows from PostgreSQL."""
        query = self.translate_query(query)
        async with self.connection() as conn:
            return await conn.fetch(query, *(params or ()))
    
    async def fetch_val(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Fetch single value from PostgreSQL."""
        query = self.translate_query(query)
        async with self.connection() as conn:
            return await conn.fetchval(query, *(params or ()))


def create_adapter(db_type: str, **kwargs) -> DatabaseAdapter:
    """
    Factory function to create appropriate database adapter.
    
    Args:
        db_type: 'sqlite' or 'postgresql'
        **kwargs: Database-specific connection parameters
        
    For SQLite:
        - db_path: Path to database file
        
    For PostgreSQL:
        - host, port, database, user, password
        - Optional: min_pool_size, max_pool_size
    """
    if db_type.lower() == 'sqlite':
        return SQLiteAdapter(kwargs['db_path'])
    elif db_type.lower() in ('postgresql', 'postgres'):
        return PostgreSQLAdapter(
            host=kwargs['host'],
            port=kwargs.get('port', 5432),
            database=kwargs['database'],
            user=kwargs['user'],
            password=kwargs['password'],
            min_pool_size=kwargs.get('min_pool_size', 5),
            max_pool_size=kwargs.get('max_pool_size', 20)
        )
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
