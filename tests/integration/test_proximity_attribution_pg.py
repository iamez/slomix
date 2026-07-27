"""PostgreSQL regression coverage for proximity attribution SQL assembly.

The live outage was caused by joining a bare condition after ``FROM`` without
the ``WHERE`` keyword. A fake database accepts arbitrary strings and cannot
catch that class of defect, so this module executes the helper's generated SQL
against an isolated real PostgreSQL schema.
"""

import os
import sys
import uuid
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

asyncpg = pytest.importorskip("asyncpg")

from website.backend.routers.proximity_helpers import (  # noqa: E402
    _round_quality_gate_sql,
    attribution_breakdown,
)

TEST_DB = {
    "host": os.getenv("POSTGRES_TEST_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_TEST_PORT", "5432")),
    "database": os.getenv("POSTGRES_TEST_DATABASE", "etlegacy_test"),
    "user": os.getenv("POSTGRES_TEST_USER", "etlegacy_user"),
    "password": os.getenv("POSTGRES_TEST_PASSWORD", "etlegacy_test_password"),
}


class _AsyncpgAdapter:
    def __init__(self, conn):
        self.conn = conn

    async def fetch_one(self, query, params=None):
        return await self.conn.fetchrow(query, *(params or ()))


async def _connect_or_skip():
    try:
        return await asyncpg.connect(timeout=5, **TEST_DB)
    except (TimeoutError, OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"test PostgreSQL unavailable: {exc}")


@pytest.fixture
async def pg():
    conn = await _connect_or_skip()
    namespace = f"proxattr_{uuid.uuid4().hex[:8]}"
    await conn.execute(f"CREATE SCHEMA {namespace}")
    await conn.execute(f"SET search_path TO {namespace}")
    await conn.execute(
        """
        CREATE TABLE rounds (
            id BIGINT PRIMARY KEY,
            is_bot_round BOOLEAN,
            is_valid BOOLEAN
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE combat_engagement (
            id BIGSERIAL PRIMARY KEY,
            session_date DATE NOT NULL,
            round_id BIGINT
        )
        """
    )
    yield conn
    await conn.execute(f"DROP SCHEMA {namespace} CASCADE")
    await conn.close()


@pytest.mark.asyncio
async def test_bare_leaderboard_scope_executes_and_reports_real_buckets(pg):
    await pg.executemany(
        "INSERT INTO rounds (id, is_bot_round, is_valid) VALUES ($1, $2, $3)",
        [
            (1, False, True),
            (2, True, True),
            (3, False, False),
        ],
    )
    await pg.executemany(
        "INSERT INTO combat_engagement (session_date, round_id) VALUES ($1, $2)",
        [
            (date(2026, 7, 27), 1),
            (date(2026, 7, 27), 1),
            (date(2026, 7, 27), 2),
            (date(2026, 7, 27), 3),
            (date(2026, 7, 27), None),
            (date(2026, 7, 26), 1),
        ],
    )

    gate = _round_quality_gate_sql("")
    result = await attribution_breakdown(
        _AsyncpgAdapter(pg),
        "combat_engagement",
        f"session_date = $1 AND {gate}",
        (date(2026, 7, 27),),
    )

    assert result == {
        "total_rows": 5,
        "linked_valid": 2,
        "linked_invalid_excluded": 2,
        "unlinked_accepted": 1,
        "attributable_coverage": 0.6667,
        "mode": "compatibility",
    }
