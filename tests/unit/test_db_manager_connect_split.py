"""connect() must not mutate schema (Codex audit finding 3, PR by owner answer B8).

Opening a connection used to run _migrate_schema_if_needed() implicitly —
ALTERs and a duplicate-row DELETE could fire from a mere connect. Migration
is now the explicit migrate_schema() step.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _manager():
    from postgresql_database_manager import PostgreSQLDatabaseManager
    mgr = PostgreSQLDatabaseManager.__new__(PostgreSQLDatabaseManager)  # skip config load
    mgr.pool = None

    class Cfg:
        postgres_host = "127.0.0.1:5432"
        postgres_database = "x"
        postgres_user = "x"
        postgres_password = "x"  # noqa: S105 - dummy test cred

    mgr.config = Cfg()
    return mgr


@pytest.mark.asyncio
async def test_connect_does_not_run_migrations():
    mgr = _manager()
    with patch("postgresql_database_manager.asyncpg.create_pool",
               new=AsyncMock(return_value=object())):
        mgr._migrate_schema_if_needed = AsyncMock()  # noqa: SLF001
        await mgr.connect()
    mgr._migrate_schema_if_needed.assert_not_awaited()  # noqa: SLF001


@pytest.mark.asyncio
async def test_migrate_schema_is_the_explicit_path():
    mgr = _manager()
    mgr._migrate_schema_if_needed = AsyncMock()  # noqa: SLF001
    await mgr.migrate_schema()
    mgr._migrate_schema_if_needed.assert_awaited_once()  # noqa: SLF001
