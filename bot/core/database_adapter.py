"""
Database Abstraction Layer for PostgreSQL
Simplified to PostgreSQL-only (SQLite support removed)
"""
import logging
from typing import Any, Optional, List, Tuple
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager

# PostgreSQL support
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False
    raise ImportError("asyncpg is required for PostgreSQL support. Install with: pip install asyncpg")

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


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL database adapter using asyncpg connection pooling."""

    def __init__(self, host: str, port: int, database: str, user: str, password: str,
                 min_pool_size: int = 2, max_pool_size: int = 10,
                 ssl_mode: str = 'disable', ssl_cert: str = '', ssl_key: str = '', ssl_root_cert: str = ''):
        """
        Initialize PostgreSQL adapter.

        Args:
            host: PostgreSQL host (e.g., 'localhost' or 'localhost:5432')
            port: PostgreSQL port (default 5432)
            database: Database name
            user: Database user
            password: Database password
            min_pool_size: Minimum pool connections (default 2, reduced from 5)
            max_pool_size: Maximum pool connections (default 10, reduced from 20)
            ssl_mode: SSL mode (disable, require, verify-ca, verify-full)
            ssl_cert: Path to client certificate file
            ssl_key: Path to client private key file
            ssl_root_cert: Path to root certificate file
        """
        # Handle host:port in host string
        if ':' in host:
            host, port_str = host.split(':', 1)
            port = int(port_str)

        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        self.ssl_mode = ssl_mode
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.ssl_root_cert = ssl_root_cert
        self.pool = None

        ssl_status = "SSL disabled" if ssl_mode == 'disable' else f"SSL mode: {ssl_mode}"
        logger.info(f"📦 PostgreSQL Adapter initialized: {host}:{port}/{database} ({ssl_status})")

    async def connect(self):
        """Initialize PostgreSQL connection pool."""
        if not ASYNCPG_AVAILABLE:
            raise RuntimeError("asyncpg not available - cannot connect to PostgreSQL")

        try:
            # Configure SSL if enabled
            ssl_context = None
            if self.ssl_mode and self.ssl_mode != 'disable':
                import ssl as ssl_module

                if self.ssl_mode == 'require':
                    # Require SSL but don't verify certificate
                    ssl_context = ssl_module.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl_module.CERT_NONE
                    logger.info("   SSL: Required (no verification)")

                elif self.ssl_mode in ('verify-ca', 'verify-full'):
                    # Verify certificate authority
                    if self.ssl_root_cert:
                        ssl_context = ssl_module.create_default_context(cafile=self.ssl_root_cert)
                    else:
                        ssl_context = ssl_module.create_default_context()

                    if self.ssl_mode == 'verify-full':
                        ssl_context.check_hostname = True
                        logger.info("   SSL: Full verification (cert + hostname)")
                    else:
                        ssl_context.check_hostname = False
                        logger.info("   SSL: CA verification")

                    ssl_context.verify_mode = ssl_module.CERT_REQUIRED

            self.pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                ssl=ssl_context,
                min_size=self.min_pool_size,
                max_size=self.max_pool_size,
                command_timeout=60
            )
            logger.info(f"✅ PostgreSQL pool created: {self.host}:{self.port}/{self.database}")
            logger.info(f"   Pool size: {self.min_pool_size}-{self.max_pool_size} connections")
        except Exception as e:
            logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
            raise

    async def close(self):
        """Close PostgreSQL connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("🔌 PostgreSQL pool closed")

    @asynccontextmanager
    async def connection(self):
        """Provide PostgreSQL connection from pool."""
        if not self.pool:
            await self.connect()

        conn = await self.pool.acquire()
        try:
            yield conn
        finally:
            await self.pool.release(conn)

    async def execute(self, query: str, params: Optional[Tuple] = None):
        """Execute query on PostgreSQL."""
        # Translate ? placeholders to $1, $2, etc.
        query = self._translate_placeholders(query)

        async with self.connection() as conn:
            await conn.execute(query, *(params or ()))

    async def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Any]:
        """Fetch single row from PostgreSQL."""
        # Translate ? placeholders to $1, $2, etc.
        query = self._translate_placeholders(query)

        async with self.connection() as conn:
            row = await conn.fetchrow(query, *(params or ()))
            return tuple(row.values()) if row else None

    async def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Any]:
        """Fetch all rows from PostgreSQL."""
        # Translate ? placeholders to $1, $2, etc.
        query = self._translate_placeholders(query)

        async with self.connection() as conn:
            rows = await conn.fetch(query, *(params or ()))
            return [tuple(row.values()) for row in rows]

    async def fetch_val(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Fetch single value from PostgreSQL."""
        # Translate ? placeholders to $1, $2, etc.
        query = self._translate_placeholders(query)

        async with self.connection() as conn:
            return await conn.fetchval(query, *(params or ()))

    def _translate_placeholders(self, query: str) -> str:
        """
        Translate SQLite-style ? placeholders to PostgreSQL $1, $2, etc.

        This allows code to use ? placeholders (portable) while using PostgreSQL.
        """
        if '?' not in query:
            return query

        # Replace ? with $1, $2, $3, etc.
        result = []
        param_num = 1
        i = 0
        while i < len(query):
            if query[i] == '?':
                result.append(f'${param_num}')
                param_num += 1
            else:
                result.append(query[i])
            i += 1

        return ''.join(result)

    def translate_query(self, query: str) -> str:
        """
        Translate SQLite-specific SQL to PostgreSQL.

        Common translations:
        - ? → $1, $2, $3 (handled by _translate_placeholders)
        - CAST(x AS INTEGER) → x::INTEGER
        - SUBSTR() → SUBSTRING()
        """
        return self._translate_placeholders(query)


def create_adapter(db_type: str = 'postgresql', **kwargs) -> DatabaseAdapter:
    """
    Factory function to create PostgreSQL database adapter.

    Args:
        db_type: Must be 'postgresql' or 'postgres' (SQLite removed)
        **kwargs: PostgreSQL connection parameters
            - host: PostgreSQL host
            - port: PostgreSQL port (default 5432)
            - database: Database name
            - user: Database user
            - password: Database password
            - min_pool_size: Min connections (default 2)
            - max_pool_size: Max connections (default 10)

    Returns:
        PostgreSQLAdapter instance

    Raises:
        ValueError: If db_type is not postgresql
    """
    if db_type.lower() not in ('postgresql', 'postgres'):
        raise ValueError(
            f"Unsupported database type: {db_type}. "
            f"This bot now requires PostgreSQL. "
            f"Set database_type='postgresql' in your config."
        )

    return PostgreSQLAdapter(
        host=kwargs['host'],
        port=kwargs.get('port', 5432),
        database=kwargs['database'],
        user=kwargs['user'],
        password=kwargs['password'],
        min_pool_size=kwargs.get('min_pool_size', 2),  # Reduced from 5 (small scale)
        max_pool_size=kwargs.get('max_pool_size', 10)  # Reduced from 20 (small scale)
    )
