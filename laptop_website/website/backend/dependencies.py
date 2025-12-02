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
from website.backend.mock_database_adapter import create_mock_adapter
from bot.config import load_config

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.append(project_root)


async def get_db() -> AsyncGenerator[DatabaseAdapter, None]:
    try:
        config = load_config()
        db_type = os.getenv("DATABASE_TYPE", config.database_type).lower()
        adapter_kwargs = config.get_database_adapter_kwargs()
    except Exception:
        # Fallback if config fails to load
        db_type = os.getenv("DATABASE_TYPE", "mock").lower()
        adapter_kwargs = {}

    if db_type == "sqlite":
        db_adapter = create_local_adapter(**adapter_kwargs)
    elif db_type == "postgresql":
        # Use bot core adapter for PostgreSQL
        db_adapter = create_postgres_adapter(**adapter_kwargs)
    elif db_type == "mock":
        db_adapter = create_mock_adapter(**adapter_kwargs)
    else:
        # Default to mock if unknown in this environment
        print(f"Warning: Unknown DB type {db_type}, falling back to mock")
        db_adapter = create_mock_adapter(**adapter_kwargs)

    try:
        await db_adapter.connect()
        yield db_adapter
    finally:
        await db_adapter.close()
