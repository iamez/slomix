"""Execute migration 067 against the historical Lua mislink shape."""

# ruff: noqa: SLF001

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

asyncpg = pytest.importorskip("asyncpg")

from bot.cogs.proximity_mixins.relinker_mixin import (  # noqa: E402, PLC2701
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
                id INTEGER PRIMARY KEY,
                match_id TEXT NOT NULL,
                round_number INTEGER,
                map_name TEXT,
                round_start_unix BIGINT,
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
async def test_migration_rebinds_exact_unlinks_unknown_and_prevents_duplicates(pg):
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


class _AsyncpgAdapter:
    def __init__(self, conn):
        self.conn = conn

    async def executemany(self, query, params):
        await self.conn.executemany(query, params)


class _SpawnWriter:
    def __init__(self, conn, resolved_round_id):
        self.db_adapter = _AsyncpgAdapter(conn)
        self.resolved_round_id = resolved_round_id

    async def _has_lua_spawn_stats_table(self):
        return True

    async def _resolve_lua_round_id_for_metadata(self, _metadata):
        return self.resolved_round_id


@pytest.mark.asyncio
async def test_spawn_upsert_preserves_legacy_link_but_clears_exact_defer(pg):
    metadata = {
        "map_name": "supply",
        "round_number": 1,
        "round_start_unix": 0,
        "round_end_unix": 1_776_800_900,
    }
    spawn = [{"guid": "A1", "name": "AxisOne", "spawns": 2, "deaths": 1}]
    writer = _SpawnWriter(pg, resolved_round_id=1)

    await _LuaRoundStorageMixin._store_lua_spawn_stats(writer, metadata, spawn)
    writer.resolved_round_id = None
    await _LuaRoundStorageMixin._store_lua_spawn_stats(writer, metadata, spawn)
    assert await pg.fetchval(
        "SELECT round_id FROM lua_spawn_stats WHERE player_guid = 'A1'"
    ) == 1

    metadata["round_start_unix"] = 1_776_800_000
    await _LuaRoundStorageMixin._store_lua_spawn_stats(writer, metadata, spawn)
    assert await pg.fetchval(
        "SELECT round_id FROM lua_spawn_stats WHERE player_guid = 'A1'"
    ) is None


@pytest.mark.asyncio
async def test_lua_relinker_requires_one_exact_source_target(pg):
    await pg.execute(
        "INSERT INTO rounds (id, map_name, round_number, round_start_unix) "
        "VALUES (1, 'supply', 1, 100)"
    )
    await pg.execute(
        "INSERT INTO lua_round_teams "
        "(id, match_id, round_number, map_name, round_start_unix, round_id) "
        "VALUES (1, 'exact-defer', 1, ' Supply ', 200, NULL)"
    )

    await pg.execute(_RELINK_LUA_TEAMS_EXACT_TEMPLATE, "supply", 1, 200)
    assert await pg.fetchval(
        "SELECT round_id FROM lua_round_teams WHERE id = 1"
    ) is None

    await pg.execute(
        "INSERT INTO rounds (id, map_name, round_number, round_start_unix) "
        "VALUES (2, 'SUPPLY', 1, 200)"
    )
    await pg.execute(_RELINK_LUA_TEAMS_EXACT_TEMPLATE, "supply", 1, 200)
    assert await pg.fetchval(
        "SELECT round_id FROM lua_round_teams WHERE id = 1"
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
    assert await pg.fetchval(
        "SELECT round_id FROM lua_round_teams WHERE id = 1"
    ) == 2
