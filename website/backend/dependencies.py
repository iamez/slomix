import os
import sys
from typing import AsyncGenerator

# Import base class and Postgres adapter from bot core
from bot.core.database_adapter import (
    DatabaseAdapter,
    create_adapter as create_postgres_adapter,
)

# Import local SQLite adapter
from website.backend.local_database_adapter import create_local_adapter
from bot.config import load_config

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.append(project_root)


# Global singleton connection pool
_db_pool: DatabaseAdapter = None


async def init_db_pool():
    """Initialize the database connection pool once at startup"""
    global _db_pool

    if _db_pool is not None:
        return _db_pool

    config = load_config()
    db_type = os.getenv("DATABASE_TYPE", config.database_type).lower()
    adapter_kwargs = config.get_database_adapter_kwargs()

    if db_type == "sqlite":
        _db_pool = create_local_adapter(**adapter_kwargs)
    elif db_type == "postgresql":
        _db_pool = create_postgres_adapter(**adapter_kwargs)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

    await _db_pool.connect()
    print(f"✅ Database pool initialized ({db_type})")
    return _db_pool


async def close_db_pool():
    """Close the database connection pool at shutdown"""
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None
        print("✅ Database pool closed")


async def get_db() -> AsyncGenerator[DatabaseAdapter, None]:
    """Dependency that yields the shared database pool"""
    # Initialize if not already done (shouldn't happen if main.py startup event works)
    if _db_pool is None:
        await init_db_pool()

    yield _db_pool
    # Don't close here - pool stays open for reuse!
