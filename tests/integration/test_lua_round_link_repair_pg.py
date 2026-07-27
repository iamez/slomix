"""Execute migration 067 against the historical Lua mislink shape."""

# ruff: noqa: SLF001

import asyncio
import os
import re
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

asyncpg = pytest.importorskip("asyncpg")

from bot.cogs.proximity_mixins.relinker_mixin import (  # noqa: E402, PLC2701
    _RELINK_LUA_SPAWN_FROM_TEAMS_TEMPLATE,
    _RELINK_LUA_TEAMS_EXACT_TEMPLATE,
)
from bot.services.lua_round_storage_mixin import _LuaRoundStorageMixin  # noqa: E402
from scripts.apply_migrations import unwrap_outer_transaction  # noqa: E402

TEST_DB = {
    "host": os.getenv("POSTGRES_TEST_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_TEST_PORT", "5432")),
    "database": os.getenv("POSTGRES_TEST_DATABASE", "etlegacy_test"),
    "user": os.getenv("POSTGRES_TEST_USER", "etlegacy_user"),
    "password": os.getenv("POSTGRES_TEST_PASSWORD", "etlegacy_test_password"),
}


async def _connect_or_skip():
    try:
        return await asyncpg.connect(timeout=5, **TEST_DB)
    except (TimeoutError, OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"test PostgreSQL unavailable: {exc}")


@pytest.fixture
async def pg():
    conn = await _connect_or_skip()
    try:
        # Temporary tables are connection-local and shadow production tables,
        # so the service user can run this test without CREATE SCHEMA rights.
        await conn.execute(
            """
            CREATE TEMP TABLE rounds (
                id INTEGER PRIMARY KEY,
                map_name TEXT,
                round_number INTEGER,
                round_start_unix BIGINT
            );
            CREATE TEMP TABLE lua_round_teams (
                id SERIAL PRIMARY KEY,
                match_id TEXT NOT NULL,
                round_number INTEGER,
                map_name TEXT,
                round_start_unix BIGINT,
                round_end_unix BIGINT,
                axis_players JSONB,
                allies_players JSONB,
                actual_duration_seconds INTEGER,
                total_pause_seconds INTEGER,
                pause_count INTEGER,
                end_reason TEXT,
                winner_team INTEGER,
                defender_team INTEGER,
                time_limit_minutes INTEGER,
                lua_warmup_seconds INTEGER,
                lua_warmup_start_unix BIGINT,
                lua_pause_events JSONB,
                surrender_team INTEGER,
                surrender_caller_guid TEXT,
                surrender_caller_name TEXT,
                axis_score INTEGER,
                allies_score INTEGER,
                lua_version TEXT,
                captured_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                round_id INTEGER,
                UNIQUE(match_id, round_number)
            );
            CREATE TEMP TABLE lua_spawn_stats (
                id SERIAL PRIMARY KEY,
                match_id TEXT NOT NULL,
                round_number INTEGER NOT NULL,
                map_name TEXT,
                round_id INTEGER,
                round_end_unix BIGINT,
                player_guid TEXT,
                player_name TEXT,
                spawn_count INTEGER DEFAULT 0,
                death_count INTEGER DEFAULT 0,
                dead_seconds INTEGER DEFAULT 0,
                avg_respawn_seconds INTEGER DEFAULT 0,
                max_respawn_seconds INTEGER DEFAULT 0,
                captured_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(match_id, round_number, player_guid)
            );
            """
        )
        yield conn
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_refuses_dirty_state_then_enforces_guarded_repair(pg):
    await pg.executemany(
        "INSERT INTO rounds (id, map_name, round_number, round_start_unix) "
        "VALUES ($1, $2, $3, $4)",
        [
            (1, "supply", 1, 100),
            (2, "supply", 1, 200),
            (3, "supply", 1, 300),
            (4, "supply", 1, None),
            (5, "supply", 1, 400),
            (6, "depot", 1, 500),
            (7, "supply", 1, 500),
        ],
    )
    await pg.executemany(
        "INSERT INTO lua_round_teams "
        "(id, match_id, round_number, map_name, round_start_unix, round_id) "
        "VALUES ($1, $2, 1, 'supply', $3, $4)",
        [
            (1, "correct-one", 100, 1),
            (2, "wrong-but-exact", 300, 1),
            (3, "correct-two", 200, 2),
            (4, "wrong-no-target", 999, 2),
            (5, "linked-null-start", 400, 4),
            (6, "wrong-map", 500, 6),
            (7, "source-start-missing", None, 1),
        ],
    )
    await pg.executemany(
        "INSERT INTO lua_spawn_stats "
        "(id, match_id, round_number, map_name, round_id) "
        "VALUES ($1, $2, 1, $3, $4)",
        [
            (1, "correct-one", "supply", 1),
            (2, "wrong-but-exact", "supply", 1),
            (3, "wrong-no-target", "supply", 2),
            (4, "linked-null-start", "supply", None),
            (5, "no-team-row", "supply", 2),
            (6, "wrong-map", "supply", 6),
            (7, "source-start-missing", "supply", 1),
        ],
    )

    migration = Path("migrations/067_repair_lua_round_links.sql").read_text()
    body = unwrap_outer_transaction(migration)

    with pytest.raises(asyncpg.RaiseError, match="guarded Lua repair"):
        async with pg.transaction():
            await pg.execute(body)

    # The failed migration must not mutate the dirty source rows.
    assert await pg.fetchval(
        "SELECT round_id FROM lua_round_teams WHERE id = 2"
    ) == 1

    # Simulate the owner-only guarded repair. Migration 067 is allowed to
    # enforce its constraint only after both action sets are already clean.
    await pg.execute(
        """
        UPDATE lua_round_teams
        SET round_id = CASE id
            WHEN 1 THEN 1 WHEN 2 THEN 3 WHEN 3 THEN 2
            WHEN 5 THEN 5 WHEN 6 THEN 7 ELSE NULL END;
        UPDATE lua_spawn_stats
        SET round_id = CASE id
            WHEN 1 THEN 1 WHEN 2 THEN 3 WHEN 4 THEN 5
            WHEN 6 THEN 7 ELSE NULL END;
        """
    )
    await pg.execute(body)

    links = await pg.fetch(
        "SELECT id, round_id FROM lua_round_teams ORDER BY id"
    )
    assert [(row["id"], row["round_id"]) for row in links] == [
        (1, 1),
        (2, 3),
        (3, 2),
        (4, None),
        (5, 5),
        (6, 7),
        (7, None),
    ]
    spawn_links = await pg.fetch(
        "SELECT id, round_id FROM lua_spawn_stats ORDER BY id"
    )
    assert [(row["id"], row["round_id"]) for row in spawn_links] == [
        (1, 1),
        (2, 3),
        (3, None),
        (4, 5),
        (5, None),
        (6, 7),
        (7, None),
    ]

    # The migration is idempotent and the unique contract remains in force.
    await pg.execute(body)
    with pytest.raises(asyncpg.UniqueViolationError):
        await pg.execute(
            "INSERT INTO lua_round_teams "
            "(id, match_id, round_number, map_name, round_start_unix, round_id) "
            "VALUES (8, 'duplicate-round', 1, 'supply', 100, 1)"
        )


@pytest.mark.asyncio
async def test_migration_refuses_matching_link_with_ambiguous_exact_target(pg):
    await pg.execute(
        "INSERT INTO rounds (id, map_name, round_number, round_start_unix) "
        "VALUES (1, 'supply', 1, 100), (2, ' SUPPLY ', 1, 100); "
        "INSERT INTO lua_round_teams "
        "(id, match_id, round_number, map_name, round_start_unix, round_id) "
        "VALUES (1, 'ambiguous', 1, 'supply', 100, 1); "
        "INSERT INTO lua_spawn_stats "
        "(id, match_id, round_number, map_name, round_id) "
        "VALUES (1, 'ambiguous', 1, 'supply', 1)"
    )
    body = unwrap_outer_transaction(
        Path("migrations/067_repair_lua_round_links.sql").read_text()
    )

    with pytest.raises(asyncpg.RaiseError, match="guarded Lua repair"):
        async with pg.transaction():
            await pg.execute(body)

    assert await pg.fetchval(
        "SELECT round_id FROM lua_round_teams WHERE id = 1"
    ) == 1

    await pg.execute(
        "UPDATE lua_round_teams SET round_id = NULL; "
        "UPDATE lua_spawn_stats SET round_id = NULL"
    )
    await pg.execute(body)
    assert await pg.fetchval(
        "SELECT round_id FROM lua_round_teams WHERE id = 1"
    ) is None


class _AsyncpgAdapter:
    def __init__(self, conn):
        self.conn = conn
        self._transaction_lock = asyncio.Lock()

    @staticmethod
    def _translate(query):
        counter = 0

        def replace(_match):
            nonlocal counter
            counter += 1
            return f"${counter}"

        return re.sub(r"\?", replace, query)

    @asynccontextmanager
    async def transaction(self):
        # One test connection stands in for the pool; production serialization
        # is provided by the source-key advisory lock inside this transaction.
        async with self._transaction_lock, self.conn.transaction():
            yield self.conn

    async def execute(self, query, params=None):
        await self.conn.execute(self._translate(query), *(params or ()))

    async def executemany(self, query, params):
        await self.conn.executemany(self._translate(query), params)

    async def fetch_one(self, query, params=None):
        return await self.conn.fetchrow(self._translate(query), *(params or ()))

    async def fetch_all(self, query, params=None):
        return await self.conn.fetch(self._translate(query), *(params or ()))

    async def fetch_val(self, query, params=None):
        return await self.conn.fetchval(self._translate(query), *(params or ()))


class _SpawnWriter:
    def __init__(self, conn):
        self.db_adapter = _AsyncpgAdapter(conn)

    async def _has_lua_spawn_stats_table(self):
        return True

    async def _resolve_lua_spawn_team_identity(self, **kwargs):
        return await _LuaRoundStorageMixin._resolve_lua_spawn_team_identity(
            self,
            **kwargs,
        )


class _TeamWriter(_SpawnWriter):
    _lua_exact_source_lock_key = staticmethod(
        _LuaRoundStorageMixin._lua_exact_source_lock_key
    )

    def __init__(self, conn):
        super().__init__(conn)
        self.correlation_service = None

    async def _has_lua_round_teams_round_id(self):
        return True

    async def _resolve_lua_round_id_for_metadata(self, metadata):
        assert metadata["round_start_unix"] == 100
        return 1

    async def _reconcile_lua_exact_source(self, **kwargs):
        return await _LuaRoundStorageMixin._reconcile_lua_exact_source(
            self,
            **kwargs,
        )

    async def _resolve_round_correlation_context(
        self,
        _round_id,
        *,
        fallback_match_id,
        fallback_map_name,
        fallback_round_number,
    ):
        return fallback_match_id, fallback_map_name, fallback_round_number


@pytest.mark.asyncio
async def test_spawn_upsert_follows_team_identity_and_preserves_without_one(pg):
    metadata = {
        "map_name": "supply",
        "round_number": 1,
        "round_start_unix": 0,
        "round_end_unix": 1_776_800_900,
    }
    spawn = [{"guid": "A1", "name": "AxisOne", "spawns": 2, "deaths": 1}]
    match_id = datetime.fromtimestamp(  # noqa: DTZ006 - mirrors writer contract
        metadata["round_end_unix"]
    ).strftime(
        "%Y-%m-%d-%H%M%S"
    )
    await pg.execute(
        "INSERT INTO lua_round_teams "
        "(id, match_id, round_number, map_name, round_start_unix, round_id) "
        "VALUES (1, $1, 1, 'supply', 0, 1)",
        match_id,
    )
    writer = _SpawnWriter(pg)

    await _LuaRoundStorageMixin._store_lua_spawn_stats(writer, metadata, spawn)
    assert await pg.fetchval(
        "SELECT round_id FROM lua_spawn_stats WHERE player_guid = 'A1'"
    ) == 1

    await pg.execute("UPDATE lua_round_teams SET round_id = NULL WHERE id = 1")
    await _LuaRoundStorageMixin._store_lua_spawn_stats(writer, metadata, spawn)
    assert await pg.fetchval(
        "SELECT round_id FROM lua_spawn_stats WHERE player_guid = 'A1'"
    ) is None

    await pg.execute("DELETE FROM lua_round_teams WHERE id = 1")
    await pg.execute("UPDATE lua_spawn_stats SET round_id = 1")
    await _LuaRoundStorageMixin._store_lua_spawn_stats(writer, metadata, spawn)
    assert await pg.fetchval(
        "SELECT round_id FROM lua_spawn_stats WHERE player_guid = 'A1'"
    ) == 1


@pytest.mark.asyncio
async def test_live_exact_reconcile_unlinks_duplicate_sources_and_spawn_rows(pg):
    await pg.execute(
        "INSERT INTO rounds (id, map_name, round_number, round_start_unix) "
        "VALUES (1, 'supply', 1, 100)"
    )
    await pg.execute(
        "INSERT INTO lua_round_teams "
        "(id, match_id, round_number, map_name, round_start_unix, round_id) "
        "VALUES (1, 'source-a', 1, ' Supply ', 100, NULL); "
        "INSERT INTO lua_spawn_stats "
        "(id, match_id, round_number, map_name, round_id) "
        "VALUES (1, 'source-a', 1, 'supply', NULL)"
    )
    writer = _SpawnWriter(pg)

    resolved = await _LuaRoundStorageMixin._reconcile_lua_exact_source(
        writer,
        match_id="source-a",
        map_name="supply",
        round_number=1,
        round_start_unix=100,
    )
    assert resolved == 1
    assert await pg.fetchval("SELECT round_id FROM lua_round_teams WHERE id = 1") == 1
    assert await pg.fetchval("SELECT round_id FROM lua_spawn_stats WHERE id = 1") == 1

    await pg.execute(
        "INSERT INTO lua_round_teams "
        "(id, match_id, round_number, map_name, round_start_unix, round_id) "
        "VALUES (2, 'source-b', 1, 'SUPPLY', 100, NULL); "
        "INSERT INTO lua_spawn_stats "
        "(id, match_id, round_number, map_name, round_id) "
        "VALUES (2, 'source-b', 1, 'SUPPLY', 1)"
    )
    resolved = await _LuaRoundStorageMixin._reconcile_lua_exact_source(
        writer,
        match_id="source-b",
        map_name="supply",
        round_number=1,
        round_start_unix=100,
    )
    assert resolved is None
    assert await pg.fetchval(
        "SELECT COUNT(*) FROM lua_round_teams WHERE round_id IS NOT NULL"
    ) == 0
    assert await pg.fetchval(
        "SELECT COUNT(*) FROM lua_spawn_stats WHERE round_id IS NOT NULL"
    ) == 0


@pytest.mark.asyncio
async def test_concurrent_live_team_writers_cannot_claim_duplicate_source(pg):
    await pg.execute(
        "INSERT INTO rounds (id, map_name, round_number, round_start_unix) "
        "VALUES (1, 'supply', 1, 100); "
        "ALTER TABLE lua_round_teams "
        "ADD CONSTRAINT lua_round_teams_round_id_key UNIQUE (round_id)"
    )
    writer = _TeamWriter(pg)

    def metadata(round_end_unix):
        return {
            "map_name": "supply",
            "round_number": 1,
            "round_start_unix": 100,
            "round_end_unix": round_end_unix,
            "axis_players": [],
            "allies_players": [],
        }

    results = await asyncio.gather(
        _LuaRoundStorageMixin._store_lua_round_teams(writer, metadata(200)),
        _LuaRoundStorageMixin._store_lua_round_teams(writer, metadata(201)),
    )

    assert sorted(results, key=lambda value: value is None) == [1, None]
    rows = await pg.fetch(
        "SELECT match_id, round_id FROM lua_round_teams ORDER BY match_id"
    )
    assert len(rows) == 2
    assert [row["round_id"] for row in rows] == [None, None]


@pytest.mark.asyncio
async def test_lua_relinker_requires_one_exact_source_target(pg):
    await pg.execute(
        "INSERT INTO rounds (id, map_name, round_number, round_start_unix) "
        "VALUES (1, 'supply', 1, 100)"
    )
    await pg.execute(
        "INSERT INTO lua_round_teams "
        "(id, match_id, round_number, map_name, round_start_unix, round_id) "
        "VALUES (1, 'exact-defer', 1, ' Supply ', 200, NULL); "
        "INSERT INTO lua_spawn_stats "
        "(id, match_id, round_number, map_name, round_id) "
        "VALUES (1, 'exact-defer', 1, 'supply', NULL)"
    )

    await pg.execute(_RELINK_LUA_TEAMS_EXACT_TEMPLATE, "supply", 1, 200)
    await pg.execute(_RELINK_LUA_SPAWN_FROM_TEAMS_TEMPLATE, "supply", 1, 200)
    assert await pg.fetchval(
        "SELECT round_id FROM lua_round_teams WHERE id = 1"
    ) is None

    await pg.execute(
        "INSERT INTO rounds (id, map_name, round_number, round_start_unix) "
        "VALUES (2, 'SUPPLY', 1, 200)"
    )
    await pg.execute(_RELINK_LUA_TEAMS_EXACT_TEMPLATE, "supply", 1, 200)
    await pg.execute(_RELINK_LUA_SPAWN_FROM_TEAMS_TEMPLATE, "supply", 1, 200)
    assert await pg.fetchval(
        "SELECT round_id FROM lua_round_teams WHERE id = 1"
    ) == 2
    assert await pg.fetchval(
        "SELECT round_id FROM lua_spawn_stats WHERE id = 1"
    ) == 2

    await pg.execute(
        "INSERT INTO rounds (id, map_name, round_number, round_start_unix) "
        "VALUES (4, 'supply', 1, 300)"
    )
    await pg.execute(
        "INSERT INTO lua_round_teams "
        "(id, match_id, round_number, map_name, round_start_unix, round_id) "
        "VALUES (4, 'duplicate-source-a', 1, 'supply', 300, NULL), "
        "       (5, 'duplicate-source-b', 1, 'SUPPLY', 300, NULL)"
    )
    await pg.execute(_RELINK_LUA_TEAMS_EXACT_TEMPLATE, "supply", 1, 300)
    assert await pg.fetchval(
        "SELECT COUNT(*) FROM lua_round_teams "
        "WHERE round_start_unix = 300 AND round_id IS NOT NULL"
    ) == 0

    await pg.execute(
        "INSERT INTO rounds (id, map_name, round_number, round_start_unix) "
        "VALUES (3, 'supply', 1, 200)"
    )
    await pg.execute(_RELINK_LUA_TEAMS_EXACT_TEMPLATE, "supply", 1, 200)
    await pg.execute(_RELINK_LUA_SPAWN_FROM_TEAMS_TEMPLATE, "supply", 1, 200)
    assert await pg.fetchval(
        "SELECT round_id FROM lua_round_teams WHERE id = 1"
    ) is None
    assert await pg.fetchval(
        "SELECT round_id FROM lua_spawn_stats WHERE id = 1"
    ) is None
