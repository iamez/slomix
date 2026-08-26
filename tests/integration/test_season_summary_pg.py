"""Season-summary SQL against real PostgreSQL — the active_days regression.

The 2026-08-26 dev restart surfaced `column "player_name" does not exist`:
the active_days query selects FROM rounds but carried a pasted bot filter
(player_name NOT LIKE ... + a NOT EXISTS referencing
player_comprehensive_stats) that only makes sense on pcs. The endpoint
answered 200 with active_days silently null — which is why the stub-DB
contract test (test_api_response_contracts) could not see it: a stub never
parses SQL. Only a real PostgreSQL does, so this test runs the actual
endpoint against an isolated schema and asserts the VALUE, not the field.

Pattern follows tests/integration/test_round_validity_insert_pg.py:
POSTGRES_TEST_* env (CI service container), one throwaway schema per run.
"""

import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

asyncpg = pytest.importorskip("asyncpg")
httpx = pytest.importorskip("httpx")

from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from shared.season_manager import SeasonManager  # noqa: E402
from website.backend.dependencies import get_db  # noqa: E402
from website.backend.routers.records_seasons import router as records_seasons_router  # noqa: E402

TEST_DB = {
    "host": os.getenv("POSTGRES_TEST_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_TEST_PORT", "5432")),
    "database": os.getenv("POSTGRES_TEST_DATABASE", "etlegacy_test"),
    "user": os.getenv("POSTGRES_TEST_USER", "etlegacy_user"),
    "password": os.getenv("POSTGRES_TEST_PASSWORD", "etlegacy_test_password"),
}

# Only the columns the summary endpoint's SQL actually references — the
# point is that PostgreSQL PARSES every query, not schema completeness.
_DDL = """
    CREATE TABLE rounds (
        id SERIAL PRIMARY KEY,
        round_date TEXT,
        round_number INTEGER,
        map_name TEXT,
        gaming_session_id INTEGER,
        round_status TEXT DEFAULT 'completed',
        is_valid BOOLEAN NOT NULL DEFAULT TRUE
    );
    CREATE TABLE player_comprehensive_stats (
        id SERIAL PRIMARY KEY,
        round_id INTEGER,
        round_date TEXT,
        round_number INTEGER,
        player_guid TEXT,
        player_name TEXT,
        kills INTEGER DEFAULT 0
    );
"""


class _PgAdapter:
    """Thin fetch_val/fetch_one/fetch_all over one asyncpg connection."""

    def __init__(self, conn):
        self._conn = conn

    async def fetch_val(self, query, params=None):
        return await self._conn.fetchval(query, *(params or ()))

    async def fetch_one(self, query, params=None):
        row = await self._conn.fetchrow(query, *(params or ()))
        return tuple(row) if row is not None else None

    async def fetch_all(self, query, params=None):
        rows = await self._conn.fetch(query, *(params or ()))
        return [tuple(r) for r in rows]


@pytest.mark.asyncio
async def test_active_days_is_counted_not_silently_null():
    try:
        conn = await asyncpg.connect(**TEST_DB)
    except (OSError, asyncpg.InvalidCatalogNameError) as exc:
        # No server listening / no etlegacy_test database = the local-dev
        # case, SKIP like the sibling _pg tests. Anything else (bad
        # credentials, protocol errors) must FAIL — on CI a misconfigured
        # database would otherwise silently skip this regression test.
        pytest.skip(f"Test database unavailable: {exc}")
    schema = f"season_summary_{uuid.uuid4().hex[:12]}"
    try:
        await conn.execute(f'CREATE SCHEMA "{schema}"')
        await conn.execute(f'SET search_path TO "{schema}"')
        await conn.execute(_DDL)

        # Seed on the season's own start date — taken from the same
        # SeasonManager the endpoint uses, so the row is inside the window
        # by construction (date.today() would race quarter boundaries and
        # trips ruff DTZ011 besides).
        sm = SeasonManager()
        today = sm.get_season_dates(sm.get_current_season())[0].strftime("%Y-%m-%d")
        await conn.execute(
            "INSERT INTO rounds (round_date, round_number, map_name, gaming_session_id)"
            " VALUES ($1, 1, 'supply', 7)",
            today,
        )
        await conn.execute(
            "INSERT INTO player_comprehensive_stats"
            " (round_id, round_date, round_number, player_guid, player_name, kills)"
            " VALUES (1, $1, 1, 'ABCDEF12', 'vid', 3)",
            today,
        )

        app = FastAPI()
        app.include_router(records_seasons_router, prefix="/api")
        app.dependency_overrides[get_db] = lambda: _PgAdapter(conn)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            response = await client.get("/api/seasons/current/summary")

        assert response.status_code == 200
        body = response.json()
        totals = body["totals"]
        # The regression shape: every query raised on the broken clause, the
        # endpoint still said 200, and these all collapsed to 0/None. Assert
        # VALUES — "field present" was already green while the page lied.
        assert totals["rounds"] == 1
        assert totals["active_days"] == 1, (
            "active_days lost — the rounds query must not carry a player filter"
        )
        assert totals["players"] == 1
        assert totals["kills"] == 3
    finally:
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await conn.close()
