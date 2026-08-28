"""The rivalries endpoints against real PostgreSQL — the 8-character GUID.

Every link in this product carries the 8-character canonical GUID: profiles,
leaderboards, the record book, the bot's Discord messages. The proximity
tables are keyed by the full 32, so `/api/rivalries/player/D8423F90` matched
nothing and answered `{nemesis: null, all_pairs: [], total_opponents: 0}` —
a perfectly well-formed way of saying "this player has no rivals" about a
player who has fourteen. Measured on dev 2026-08-28: 0 opponents by the
short id, 14 by the long one.

A stub DB cannot see this: it never applies `LEFT(victim_guid, 8)` to
anything. Only a real PostgreSQL does, so the resolution is asserted here,
against rows whose two GUID forms differ exactly as production's do.

Pattern follows tests/integration/test_season_summary_pg.py.
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

from website.backend.dependencies import get_db  # noqa: E402
from website.backend.routers.rivalries_router import router as rivalries_router  # noqa: E402

TEST_DB = {
    "host": os.getenv("POSTGRES_TEST_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_TEST_PORT", "5432")),
    "database": os.getenv("POSTGRES_TEST_DATABASE", "etlegacy_test"),
    "user": os.getenv("POSTGRES_TEST_USER", "etlegacy_user"),
    "password": os.getenv("POSTGRES_TEST_PASSWORD", "etlegacy_test_password"),
}

# Only what the rivalries SQL reads — and `kill_mod` and `map_name` are in
# here because the first version omitted them and PostgreSQL refused the
# weapon and per-map breakdowns outright, one after the other. Those refusals
# are the point of running against a real server: a stub returns an empty
# list for a column it has never heard of and calls that a pass.
_DDL = """
    CREATE TABLE proximity_kill_outcome (
        id SERIAL PRIMARY KEY,
        killer_guid TEXT,
        victim_guid TEXT,
        killer_guid_canonical TEXT,
        victim_guid_canonical TEXT,
        killer_name TEXT,
        victim_name TEXT,
        kill_mod INTEGER,
        map_name TEXT
    );
"""

VID32 = "D8423F90F045D9D3E2C0550811C5A899"
OLZ32 = "5D9891600C7948FF85709360E669D5A4"
VID8, OLZ8 = VID32[:8], OLZ32[:8]


class _PgAdapter:
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


async def _seed(conn):
    await conn.execute(_DDL)
    # vid kills .olz three times, .olz kills vid twice.
    for _ in range(3):
        await conn.execute(
            "INSERT INTO proximity_kill_outcome "
            "(killer_guid, victim_guid, killer_guid_canonical, victim_guid_canonical,"
            " killer_name, victim_name, kill_mod, map_name) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
            VID32, OLZ32, VID8, OLZ8, "vid", ".olz", 3, "supply",
        )
    for _ in range(2):
        await conn.execute(
            "INSERT INTO proximity_kill_outcome "
            "(killer_guid, victim_guid, killer_guid_canonical, victim_guid_canonical,"
            " killer_name, victim_name, kill_mod, map_name) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
            OLZ32, VID32, OLZ8, VID8, ".olz", "vid", 4, "supply",
        )


async def _client(conn):
    app = FastAPI()
    app.include_router(rivalries_router, prefix="/api")
    adapter = _PgAdapter(conn)
    app.dependency_overrides[get_db] = lambda: adapter
    # The routes carry a rate limiter that expects app state; the tests call
    # each route once, so a permissive stub keeps the decorator satisfied.
    app.state.limiter = getattr(app.state, "limiter", None)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_short_guid_finds_the_same_rivals_as_the_long_one():
    try:
        conn = await asyncpg.connect(**TEST_DB, timeout=5)
    except Exception as exc:
        if os.environ.get("CI"):
            raise
        pytest.skip(f"Test database unavailable: {exc}")
    schema = f"rivalries_{uuid.uuid4().hex[:12]}"
    try:
        await conn.execute(f'CREATE SCHEMA "{schema}"')
        await conn.execute(f'SET search_path TO "{schema}"')
        await _seed(conn)

        async with await _client(conn) as client:
            short = await client.get(f"/api/rivalries/player/{VID8}")
            long = await client.get(f"/api/rivalries/player/{VID32}")

        assert short.status_code == 200, short.text
        assert long.status_code == 200, long.text
        s, l = short.json(), long.json()

        # The heart of it: the two ids describe one player.
        assert s["resolved"] is True
        assert s["total_opponents"] == l["total_opponents"] == 1
        assert s["player_name"] == l["player_name"] == "vid"

    finally:
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await conn.close()


@pytest.mark.asyncio
async def test_an_id_with_no_rows_says_unresolved_rather_than_empty():
    try:
        conn = await asyncpg.connect(**TEST_DB, timeout=5)
    except Exception as exc:
        if os.environ.get("CI"):
            raise
        pytest.skip(f"Test database unavailable: {exc}")
    schema = f"rivalries_{uuid.uuid4().hex[:12]}"
    try:
        await conn.execute(f'CREATE SCHEMA "{schema}"')
        await conn.execute(f'SET search_path TO "{schema}"')
        await _seed(conn)

        async with await _client(conn) as client:
            unknown = await client.get("/api/rivalries/player/AAAAAAAA")

        body = unknown.json()
        # Both facts have the same shape — an empty list — so the flag is the
        # only thing that can tell "tracked, no rival" from "never tracked".
        assert body["resolved"] is False
        assert body["all_pairs"] == []
        assert body["total_opponents"] == 0
    finally:
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await conn.close()


@pytest.mark.asyncio
async def test_head_to_head_accepts_short_guids_on_both_sides():
    try:
        conn = await asyncpg.connect(**TEST_DB, timeout=5)
    except Exception as exc:
        if os.environ.get("CI"):
            raise
        pytest.skip(f"Test database unavailable: {exc}")
    schema = f"rivalries_{uuid.uuid4().hex[:12]}"
    try:
        await conn.execute(f'CREATE SCHEMA "{schema}"')
        await conn.execute(f'SET search_path TO "{schema}"')
        await _seed(conn)

        async with await _client(conn) as client:
            pair = await client.get(f"/api/rivalries/h2h/{VID8}/{OLZ8}")
            half = await client.get(f"/api/rivalries/h2h/{VID8}/AAAAAAAA")

        body = pair.json()
        assert body["resolved"] is True
        assert body["total"] == 5
        assert {body["p1_name"], body["p2_name"]} == {"vid", ".olz"}

        # And when one side is unknown, the answer names WHICH side: "no
        # data" about a pair is useless when one of the two never existed.
        missing = half.json()
        assert missing["resolved"] is False
        assert missing["unresolved"] == ["AAAAAAAA"]
    finally:
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await conn.close()
