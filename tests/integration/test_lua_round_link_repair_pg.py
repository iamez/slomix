"""Execute migration 067 against the historical Lua mislink shape."""

import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

asyncpg = pytest.importorskip("asyncpg")

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
    namespace = f"luarepair_{uuid.uuid4().hex[:8]}"
    await conn.execute(f"CREATE SCHEMA {namespace}")
    await conn.execute(f"SET search_path TO {namespace}")
    await conn.execute(
        """
        CREATE TABLE rounds (
            id INTEGER PRIMARY KEY,
            map_name TEXT,
            round_number INTEGER,
            round_start_unix BIGINT
        );
        CREATE TABLE lua_round_teams (
            id INTEGER PRIMARY KEY,
            match_id TEXT NOT NULL,
            round_number INTEGER,
            map_name TEXT,
            round_start_unix BIGINT,
            captured_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            round_id INTEGER,
            UNIQUE(match_id, round_number)
        );
        CREATE TABLE lua_spawn_stats (
            id INTEGER PRIMARY KEY,
            match_id TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            map_name TEXT,
            round_id INTEGER,
            captured_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    yield conn
    await conn.execute(f"DROP SCHEMA {namespace} CASCADE")
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
            "VALUES (5, 'duplicate-round', 1, 'supply', 100, 1)"
        )
