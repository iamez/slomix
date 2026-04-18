import logging
import os
import sys
from typing import AsyncGenerator

from fastapi import HTTPException, Request

from shared.config import load_config

# Import base class and Postgres adapter from bot core
from shared.database_adapter import (
    DatabaseAdapter,
)
from shared.database_adapter import (
    create_adapter as create_postgres_adapter,
)

# Import local SQLite adapter
from website.backend.local_database_adapter import create_local_adapter

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.append(project_root)


logger = logging.getLogger(__name__)

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
    logger.info("Database pool initialized (%s)", db_type)
    return _db_pool


async def close_db_pool():
    """Close the database connection pool at shutdown"""
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None
        logger.info("Database pool closed")


async def get_db() -> AsyncGenerator[DatabaseAdapter, None]:
    """Dependency that yields the shared database pool"""
    # Initialize if not already done (shouldn't happen if main.py startup event works)
    if _db_pool is None:
        await init_db_pool()

    yield _db_pool
    # Don't close here - pool stays open for reuse!


def get_db_pool() -> DatabaseAdapter:
    """Get the database pool directly (for background tasks)"""
    return _db_pool


# ---------------------------------------------------------------------------
# Authentication / authorization
# ---------------------------------------------------------------------------

def _configured_admin_ids() -> set[int]:
    """Read admin Discord IDs from env. Matches availability.py + planning.py."""
    ids: set[int] = set()
    for env_name in ("WEBSITE_ADMIN_DISCORD_IDS", "ADMIN_DISCORD_IDS", "OWNER_USER_ID"):
        raw = os.getenv(env_name, "")
        if not raw:
            continue
        for token in raw.split(","):
            token = token.strip()
            if token.isdigit():
                ids.add(int(token))
    return ids


def require_admin_user(request: Request) -> dict:
    """FastAPI dependency: require an authenticated Discord admin session.

    Returns the user dict on success; raises 401 (no session) or 403
    (session present but not in WEBSITE_ADMIN_DISCORD_IDS / ADMIN_DISCORD_IDS /
    OWNER_USER_ID).

    Mirrors the admin gate used by availability.py / planning.py so operational
    endpoints (diagnostics, monitoring) share one source of truth.
    """
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = None
    for key in ("id", "website_user_id"):
        raw = user.get(key)
        try:
            user_id = int(raw)
            break
        except (TypeError, ValueError):
            continue

    if user_id is None or user_id not in _configured_admin_ids():
        raise HTTPException(status_code=403, detail="Admin privileges required")

    return user
