"""Round-validity INSERT contract of the production import path, on real PG.

The 2026-08-11 Omni-bot test proved the production importer
(PostgreSQLDatabaseManager._create_round_postgresql) historically wrote
rounds WITHOUT the bot/filler/orphan validity columns — is_bot_round was
never true in either database's history. These tests execute the real
INSERT ... ON CONFLICT statement against an isolated schema and pin the
persisted contract:

1. a bot round arrives is_bot_round=TRUE / is_valid=FALSE,
2. re-importing the same conflict key with "clean" data must NOT revive
   is_valid (sticky FALSE), and
3. an orphan R2 lands round_status='orphan_r2' and is_valid=FALSE.

Session-id derivation and restart detection are monkeypatched out — they
have their own coverage; the contract under test is the INSERT itself.
"""

import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

asyncpg = pytest.importorskip("asyncpg")

TEST_DB = {
    "host": os.getenv("POSTGRES_TEST_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_TEST_PORT", "5432")),
    "database": os.getenv("POSTGRES_TEST_DATABASE", "etlegacy_test"),
    "user": os.getenv("POSTGRES_TEST_USER", "etlegacy_user"),
    "password": os.getenv("POSTGRES_TEST_PASSWORD", "etlegacy_test_password"),
}

_ROUNDS_DDL = """
    CREATE TABLE rounds (
        id SERIAL PRIMARY KEY,
        round_date TEXT,
        round_time TEXT,
        match_id TEXT,
        map_name TEXT,
        round_number INTEGER,
        time_limit TEXT,
        actual_time TEXT,
        winner_team INTEGER,
        defender_team INTEGER,
        round_outcome TEXT,
        gaming_session_id INTEGER,
        round_status TEXT DEFAULT 'completed',
        created_at TIMESTAMP,
        is_bot_round BOOLEAN DEFAULT FALSE,
        bot_player_count INTEGER DEFAULT 0,
        human_player_count INTEGER DEFAULT 0,
        is_valid BOOLEAN NOT NULL DEFAULT TRUE,
        UNIQUE (match_id, round_number)
    )
"""


def _bot_players(n=6):
    return [
        {"name": f"[BOT]p{i}", "guid": f"OMNIBOT0{i:024d}", "is_bot": True}
        for i in range(n)
    ]


def _human_players(n=6):
    return [
        {"name": f"h{i}", "guid": f"{i:032d}", "is_bot": False} for i in range(n)
    ]


@pytest.fixture()
async def pg_schema(monkeypatch):
    try:
        conn = await asyncpg.connect(**TEST_DB, timeout=5)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"Test database unavailable (etlegacy_test): {exc}")

    schema = f"validity_{uuid.uuid4().hex[:12]}"
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}"')
    await conn.execute(_ROUNDS_DDL)

    # Manager construction requires postgres mode; point it at the test DB.
    # BOT_ENVIRONMENT is fail-closed with no default (environment-identity
    # RCA) — CI has a live test DB, so load_config() actually runs here.
    monkeypatch.setenv("BOT_ENVIRONMENT", "dev")
    monkeypatch.setenv("DATABASE_TYPE", "postgresql")
    for key, env in (
        ("host", "POSTGRES_HOST"),
        ("port", "POSTGRES_PORT"),
        ("database", "POSTGRES_DATABASE"),
        ("user", "POSTGRES_USER"),
        ("password", "POSTGRES_PASSWORD"),
    ):
        monkeypatch.setenv(env, str(TEST_DB[key]))

    from postgresql_database_manager import PostgreSQLDatabaseManager

    manager = PostgreSQLDatabaseManager()

    async def _fixed_session_id(_conn, _date, _time):
        return 999

    async def _no_restart_detection(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        manager, "_get_or_create_gaming_session_id", _fixed_session_id
    )
    monkeypatch.setattr(
        manager, "_detect_and_mark_restarts", _no_restart_detection
    )

    try:
        yield conn, manager
    finally:
        await conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await conn.close()


@pytest.mark.asyncio
async def test_bot_round_persists_flags_and_reimport_keeps_is_valid_sticky(
    pg_schema,
):
    conn, manager = pg_schema

    parsed_bot = {
        "map_name": "sw_goldrush_te",
        "players": _bot_players(),
        "bot_player_count": 6,
        "human_player_count": 0,
        "is_bot_round": True,
        "winner_team": 1,
        "defender_team": 1,
    }
    round_id = await manager._create_round_postgresql(  # noqa: SLF001 — the private INSERT path IS the contract under test
        conn, parsed_bot, "2026-08-11", "045605", "2026-08-11-045605-sw_goldrush_te-round-1.txt"
    )
    assert round_id is not None
    row = await conn.fetchrow("SELECT * FROM rounds WHERE id = $1", round_id)
    assert row["is_bot_round"] is True
    assert row["is_valid"] is False
    assert row["bot_player_count"] == 6
    assert row["round_status"] == "completed"

    # Re-import of the SAME conflict key with clean human data: counts and
    # is_bot_round follow the new import, but is_valid must stay FALSE —
    # a re-import can never revive a round that was invalidated.
    parsed_clean = {
        "map_name": "sw_goldrush_te",
        "players": _human_players(),
        "bot_player_count": 0,
        "human_player_count": 6,
        "winner_team": 2,
        "defender_team": 1,
    }
    round_id_2 = await manager._create_round_postgresql(  # noqa: SLF001
        conn, parsed_clean, "2026-08-11", "045605", "2026-08-11-045605-sw_goldrush_te-round-1.txt"
    )
    assert round_id_2 == round_id
    row = await conn.fetchrow("SELECT * FROM rounds WHERE id = $1", round_id)
    assert row["is_valid"] is False, "re-import must not revive an invalidated round"
    assert row["is_bot_round"] is False
    assert row["winner_team"] == 2


@pytest.mark.asyncio
async def test_orphan_r2_lands_orphan_status_and_invalid(pg_schema):
    conn, manager = pg_schema

    parsed_orphan = {
        "map_name": "te_escape2",
        "players": _human_players(),
        "bot_player_count": 0,
        "human_player_count": 6,
        "is_orphan_r2": True,
        "winner_team": 1,
        "defender_team": 2,
    }
    round_id = await manager._create_round_postgresql(  # noqa: SLF001 — the private INSERT path IS the contract under test
        conn, parsed_orphan, "2026-08-11", "052736", "2026-08-11-052736-te_escape2-round-2.txt"
    )
    assert round_id is not None
    row = await conn.fetchrow("SELECT * FROM rounds WHERE id = $1", round_id)
    assert row["round_status"] == "orphan_r2"
    assert row["is_valid"] is False
    assert row["is_bot_round"] is False


@pytest.mark.asyncio
async def test_clean_round_stays_valid(pg_schema):
    conn, manager = pg_schema

    parsed = {
        "map_name": "etl_adlernest",
        "players": _human_players(),
        "bot_player_count": 0,
        "human_player_count": 6,
        "winner_team": 2,
        "defender_team": 1,
    }
    round_id = await manager._create_round_postgresql(  # noqa: SLF001 — the private INSERT path IS the contract under test
        conn, parsed, "2026-08-11", "060000", "2026-08-11-060000-etl_adlernest-round-1.txt"
    )
    row = await conn.fetchrow("SELECT * FROM rounds WHERE id = $1", round_id)
    assert row["is_valid"] is True
    assert row["is_bot_round"] is False
    assert row["round_status"] == "completed"
