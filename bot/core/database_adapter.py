"""
Database Abstraction Layer for PostgreSQL
Simplified to PostgreSQL-only (SQLite support removed)
"""
import asyncio
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
    async def execute(self, query: str, params: Optional[Tuple] = None, *extra):
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
                 min_pool_size: int = 5, max_pool_size: int = 20,
                 ssl_mode: str = 'disable', ssl_cert: str = '', ssl_key: str = '', ssl_root_cert: str = ''):
        """
        Initialize PostgreSQL adapter.

        Args:
            host: PostgreSQL host (e.g., 'localhost' or 'localhost:5432')
            port: PostgreSQL port (default 5432)
            database: Database name
            user: Database user
            password: Database password
            min_pool_size: Minimum pool connections (default 5 for 14 cogs + tasks)
            max_pool_size: Maximum pool connections (default 20 for concurrent load)
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
        self._pool_lock = asyncio.Lock()  # Prevents race condition on pool init

        ssl_status = "SSL disabled" if ssl_mode == 'disable' else f"SSL mode: {ssl_mode}"
        logger.debug(f"📦 PostgreSQL Adapter initialized: {host}:{port}/{database} ({ssl_status})")

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
                command_timeout=120  # 2 minutes for complex aggregation queries
            )
            logger.debug(f"✅ PostgreSQL pool created: {self.host}:{self.port}/{self.database}")
            logger.info(f"✅ PostgreSQL pool created (pool size: {self.min_pool_size}-{self.max_pool_size})")
        except Exception as e:
            # Redact connection details from error message to avoid leaking credentials
            error_type = type(e).__name__
            logger.error(f"❌ Failed to connect to PostgreSQL at {self.host}:{self.port}/{self.database}: {error_type}")
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
        # Thread-safe pool initialization with double-check locking
        if not self.pool:
            async with self._pool_lock:
                if not self.pool:  # Double-check after acquiring lock
                    await self.connect()

        conn = await self.pool.acquire()
        try:
            yield conn
        finally:
            await self.pool.release(conn)

    async def execute(self, query: str, params: Optional[Tuple] = None, *extra):
        """Execute query on PostgreSQL."""
        # Translate ? placeholders to $1, $2, etc.
        if extra:
            if params is None:
                params = extra
            elif isinstance(params, (list, tuple)):
                params = tuple(params) + tuple(extra)
            else:
                params = (params,) + tuple(extra)
        elif params is not None and not isinstance(params, (list, tuple)):
            params = (params,)

        query = self._translate_placeholders(query)
        params = self._normalize_params(params)

        async with self.connection() as conn:
            await conn.execute(query, *(params or ()))

    async def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Any]:
        """Fetch single row from PostgreSQL."""
        # Translate ? placeholders to $1, $2, etc.
        query = self._translate_placeholders(query)
        params = self._normalize_params(params)

        async with self.connection() as conn:
            row = await conn.fetchrow(query, *(params or ()))
            return tuple(row.values()) if row else None

    async def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Any]:
        """Fetch all rows from PostgreSQL."""
        # Translate ? placeholders to $1, $2, etc.
        query = self._translate_placeholders(query)
        params = self._normalize_params(params)

        async with self.connection() as conn:
            rows = await conn.fetch(query, *(params or ()))
            return [tuple(row.values()) for row in rows]

    async def fetch_val(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Fetch single value from PostgreSQL."""
        # Translate ? placeholders to $1, $2, etc.
        query = self._translate_placeholders(query)
        params = self._normalize_params(params)

        async with self.connection() as conn:
            return await conn.fetchval(query, *(params or ()))

    def _normalize_params(self, params: Optional[Tuple]) -> Optional[Tuple]:
        """
        Normalize query params for asyncpg.
        Keep native date/datetime objects intact so asyncpg can bind them correctly.
        """
        return params

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
            "This bot now requires PostgreSQL. "
            "Set database_type='postgresql' in your config."
        )

    return PostgreSQLAdapter(
        host=kwargs['host'],
        port=kwargs.get('port', 5432),
        database=kwargs['database'],
        user=kwargs['user'],
        password=kwargs['password'],
        min_pool_size=kwargs.get('min_pool_size', 5),   # 5 for 14 cogs + tasks
        max_pool_size=kwargs.get('max_pool_size', 20)   # 20 for concurrent load
    )


async def ensure_player_name_alias(db_adapter: DatabaseAdapter, config=None) -> bool:
    """
    Create TEMP VIEW alias for player_name column compatibility.

    Handles schema differences where tables use 'name' or 'clean_name'
    instead of 'player_name'. This is a compatibility shim for legacy
    schema variations.

    Args:
        db_adapter: DatabaseAdapter instance (PostgreSQLAdapter)
        config: Optional config object with database_type attribute.
                Falls back to 'postgresql' if not provided.

    Returns:
        bool: True if alias was created, False if not needed or failed.

    Note:
        Errors are logged but not raised to avoid breaking callers.
        This function is designed to be called before queries that
        expect a 'player_name' column.
    """
    try:
        # Determine database type
        db_type = getattr(config, 'database_type', 'postgresql').lower()

        # Get column names for player_comprehensive_stats table
        if db_type == 'sqlite':
            columns = await db_adapter.fetch_all(
                "PRAGMA table_info(player_comprehensive_stats)"
            )
            col_names = [col[1] for col in columns]
        else:  # PostgreSQL
            columns = await db_adapter.fetch_all("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'player_comprehensive_stats'
            """)
            col_names = [col[0] for col in columns]

        # Check if player_name already exists - no alias needed
        if 'player_name' in col_names:
            return False

        # Determine source column for alias
        source_column = None
        if 'clean_name' in col_names:
            source_column = 'clean_name'
        elif 'name' in col_names:
            source_column = 'name'

        if not source_column:
            logger.debug("No suitable source column for player_name alias")
            return False

        # Create temporary view (SQLite only - PostgreSQL schema should have player_name)
        if db_type == 'sqlite':
            # nosec B608 - source_column is hardcoded ('name' or 'player_name'), not user input
            await db_adapter.execute(f"""
                CREATE TEMP VIEW IF NOT EXISTS player_comprehensive_stats_alias AS
                SELECT *, {source_column} AS player_name
                FROM player_comprehensive_stats
            """)
            logger.debug(f"Created player_name alias from {source_column}")
            return True
        else:
            # PostgreSQL: Schema should already have player_name column
            logger.debug("PostgreSQL alias handling - schema should have player_name")
            return False

    except Exception as e:
        logger.debug(f"Player name alias setup: {e}")
        return False
