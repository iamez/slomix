"""Characterize the legacy Lua correction boundary before opt-in atomicity.

This pins existing partial-commit behavior, not desired enabled-mode behavior.
Only isolated fixture data is written; canonical-ID/linking side effects are
stubbed so this proof concerns the actual round and player UPDATE statements.
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asyncpg
import pytest

from bot.core.database_adapter import PostgreSQLAdapter
from bot.core.round_canonical import compute_canonical_id
from bot.services.lua_correction_service import apply_atomic_lua_correction, lua_correction_events_enabled
from bot.ultimate_bot import UltimateETLegacyBot
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401


async def test_legacy_player_failure_leaves_round_correction_committed(journal_db, monkeypatch, caplog):  # noqa: F811
    writer, reader = journal_db
    await writer.execute("""
        ALTER TABLE rounds ADD COLUMN actual_duration_seconds INTEGER;
        ALTER TABLE rounds ADD COLUMN time_limit INTEGER;
        ALTER TABLE rounds ADD COLUMN winner_team INTEGER;
        INSERT INTO rounds VALUES (42,1,7,1800,20,1);
        CREATE TABLE player_comprehensive_stats (
            round_id INTEGER, damage_given INTEGER, time_played_seconds INTEGER,
            time_played_minutes REAL, dpm REAL,
            CONSTRAINT fixture_reject_dpm CHECK (dpm=0)
        );
        INSERT INTO player_comprehensive_stats VALUES (42,1200,1800,30,0);
    """)

    async def fetch_one(query, params=None):
        return await writer.fetchrow(query, *(params or ()))

    async def execute(query, params=None):
        return await writer.execute(query, *(params or ()))

    canonical = AsyncMock()
    monkeypatch.setattr("bot.core.round_canonical.update_canonical_id_if_possible", canonical)
    linker = AsyncMock()
    bot = SimpleNamespace(
        db_adapter=SimpleNamespace(fetch_one=fetch_one, execute=execute),
        _resolve_round_id_for_metadata=AsyncMock(return_value=42),
        _link_lua_round_teams=linker,
    )
    result = await UltimateETLegacyBot._apply_round_metadata_override(  # noqa: SLF001
        bot, "fixture", {"actual_duration_seconds": 600, "winner_team": 2}
    )
    assert result is None  # Legacy API suppresses the player UPDATE failure.
    assert tuple(await reader.fetchrow(
        "SELECT actual_duration_seconds,winner_team FROM rounds WHERE id=42"
    )) == (600, 2)
    assert tuple(await reader.fetchrow(
        "SELECT time_played_seconds,dpm FROM player_comprehensive_stats WHERE round_id=42"
    )) == (1800, 0)
    assert "fixture_reject_dpm" in caplog.text
    canonical.assert_awaited_once()
    linker.assert_awaited_once()
    print("legacy Lua runtime: round committed at 600s; rejected player update stays 1800s; exception suppressed")


@pytest.fixture
async def correction_db(journal_db):  # noqa: F811
    writer, reader = journal_db
    await writer.execute("""
        ALTER TABLE rounds ADD COLUMN map_name TEXT DEFAULT 'fixture';
        ALTER TABLE rounds ADD COLUMN winner_team INTEGER DEFAULT 1;
        ALTER TABLE rounds ADD COLUMN actual_duration_seconds INTEGER DEFAULT 1800;
        ALTER TABLE rounds ADD COLUMN total_pause_seconds INTEGER DEFAULT 0;
        ALTER TABLE rounds ADD COLUMN pause_count INTEGER DEFAULT 0;
        ALTER TABLE rounds ADD COLUMN end_reason TEXT;
        ALTER TABLE rounds ADD COLUMN round_start_unix BIGINT;
        ALTER TABLE rounds ADD COLUMN round_end_unix BIGINT;
        ALTER TABLE rounds ADD COLUMN round_canonical_id TEXT UNIQUE;
        INSERT INTO rounds(id,round_number,gaming_session_id) VALUES (42,1,7);
        CREATE TABLE player_comprehensive_stats (
            round_id INTEGER, player_guid TEXT, damage_given INTEGER,
            time_played_seconds INTEGER, time_played_minutes REAL, dpm REAL
        );
        INSERT INTO player_comprehensive_stats VALUES (42,'fixture',1200,1800,30,0);
    """)
    root = Path(__file__).resolve().parents[2]
    for name in ("083_runtime_events.sql", "084_runtime_timing_events.sql", "085_runtime_status_events.sql",
                 "086_runtime_endstats_events.sql", "087_runtime_lua_correction_events.sql"):
        await writer.execute((root / "migrations" / name).read_text())
    return writer, reader


def adapter_for(conn):
    # Real production transaction/ContextVar code; only pool checkout is substituted.
    adapter = PostgreSQLAdapter("unused", 5432, "unused", "unused", "", min_pool_size=1, max_pool_size=1)
    adapter.pool = SimpleNamespace(acquire=AsyncMock(return_value=conn), release=AsyncMock())
    return adapter


def metadata():
    return {"map_name": "fixture", "round_number": 1, "round_start_unix": 1700000000,
            "actual_duration_seconds": 600, "winner_team": 2}


async def test_atomic_correction_and_identical_retry(correction_db):
    writer, reader = correction_db
    adapter = adapter_for(writer)
    assert await apply_atomic_lua_correction(adapter, 42, metadata(), initializing_exact_start=True)
    expected = compute_canonical_id(1700000000, "fixture", 1)
    assert tuple(await reader.fetchrow(
        "SELECT actual_duration_seconds,winner_team,round_canonical_id FROM rounds WHERE id=42"
    )) == (600, 2, expected)
    assert tuple(await reader.fetchrow(
        "SELECT time_played_seconds,time_played_minutes,dpm FROM player_comprehensive_stats"
    )) == (600, 10, 120)
    assert await apply_atomic_lua_correction(adapter, 42, metadata())
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 1
    assert len(await reader.fetch("SELECT * FROM runtime_events")) == 1


async def test_correction_sql_identifiers_are_allowlisted_and_values_bound(correction_db):
    writer, reader = correction_db
    payload = metadata()
    hostile_value = "'; DROP TABLE rounds CASCADE; --"
    payload["end_reason"] = hostile_value
    payload["winner_team = 99 --"] = 99
    payload["gaming_session_id"] = 999
    payload["round_canonical_id"] = "untrusted-canonical-id"
    assert await apply_atomic_lua_correction(
        adapter_for(writer), 42, payload, initializing_exact_start=True,
    )
    row = await reader.fetchrow(
        "SELECT end_reason,winner_team,gaming_session_id,round_canonical_id FROM rounds WHERE id=42"
    )
    assert tuple(row) == (hostile_value, 2, 7, compute_canonical_id(1700000000, "fixture", 1))
    assert await reader.fetchval("SELECT count(*) FROM rounds") == 1
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 1
    print("atomic Lua runtime: round=600s, player=600s/DPM120, one event after repeat")


@pytest.mark.parametrize("fault", ["player", "event", "notify", "canonical_collision", "canonical_mismatch"])
async def test_atomic_failures_roll_back_round_players_and_event(correction_db, fault):
    writer, reader = correction_db
    if fault == "player":
        await writer.execute("ALTER TABLE player_comprehensive_stats ADD CHECK (dpm=0)")
    elif fault == "event":
        await writer.execute("ALTER TABLE runtime_events ADD CHECK (round_id<>42)")
    elif fault == "canonical_collision":
        await writer.execute("INSERT INTO rounds(id,round_number,round_canonical_id) VALUES (43,1,$1)",
                             compute_canonical_id(1700000000, "fixture", 1))
    elif fault == "canonical_mismatch":
        await writer.execute("UPDATE rounds SET round_canonical_id='wrong' WHERE id=42")

    class FaultConnection:
        def __getattr__(self, key):
            return getattr(writer, key)

        async def execute(self, query, *args):
            if "pg_notify" in query:
                raise RuntimeError("fixture notify failure")
            return await writer.execute(query, *args)

    adapter = adapter_for(FaultConnection() if fault == "notify" else writer)
    expected_error = {
        "player": asyncpg.CheckViolationError, "event": asyncpg.CheckViolationError,
        "notify": RuntimeError, "canonical_collision": asyncpg.UniqueViolationError,
        "canonical_mismatch": ValueError,
    }[fault]
    with pytest.raises(expected_error):
        await apply_atomic_lua_correction(adapter, 42, metadata(), initializing_exact_start=True)
    assert tuple(await reader.fetchrow(
        "SELECT actual_duration_seconds,round_start_unix FROM rounds WHERE id=42"
    )) == (1800, None)
    assert await reader.fetchval("SELECT time_played_seconds FROM player_comprehensive_stats") == 1800
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 0


@pytest.mark.parametrize("change", ["start", "map", "round", "missing", "r0"])
async def test_target_revalidation_before_writes(correction_db, change):
    writer, reader = correction_db
    statements = {
        "start": "UPDATE rounds SET round_start_unix=1700000001 WHERE id=42",
        "map": "UPDATE rounds SET map_name='other' WHERE id=42",
        "round": "UPDATE rounds SET round_number=2 WHERE id=42",
        "missing": "DELETE FROM rounds WHERE id=42",
        "r0": "UPDATE rounds SET round_number=0 WHERE id=42",
    }
    await writer.execute(statements[change])
    assert not await apply_atomic_lua_correction(adapter_for(writer), 42, metadata(), initializing_exact_start=True)
    assert await reader.fetchval("SELECT time_played_seconds FROM player_comprehensive_stats") == 1800
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 0


@pytest.mark.parametrize("bad_start", [True, 1.5, float("nan"), "bad"])
async def test_invalid_start_fails_before_transaction(bad_start):
    data = metadata() | {"round_start_unix": bad_start}
    with pytest.raises(ValueError):
        await apply_atomic_lua_correction(None, 42, data)


@pytest.mark.parametrize("bad_duration", [True, 600.5, float("nan"), float("inf"), -1, "600"])
async def test_invalid_duration_fails_before_transaction(bad_duration):
    with pytest.raises(ValueError, match="duration"):
        await apply_atomic_lua_correction(None, 42, metadata() | {"actual_duration_seconds": bad_duration})


@pytest.mark.parametrize("bad_round", [True, 1.5])
async def test_invalid_source_round_fails_before_transaction(bad_round):
    with pytest.raises(ValueError, match="round number"):
        await apply_atomic_lua_correction(None, 42, metadata() | {"round_number": bad_round})


@pytest.mark.parametrize("duration,expected_player", [(0, 1800), (600.0, 600)])
async def test_integer_seconds_contract(correction_db, duration, expected_player):
    writer, reader = correction_db
    await apply_atomic_lua_correction(adapter_for(writer), 42,
                                     metadata() | {"actual_duration_seconds": duration},
                                     initializing_exact_start=True)
    assert await reader.fetchval("SELECT actual_duration_seconds FROM rounds WHERE id=42") == int(duration)
    assert await reader.fetchval("SELECT time_played_seconds FROM player_comprehensive_stats") == expected_player


async def test_player_only_change_still_emits(correction_db):
    writer, reader = correction_db
    adapter = adapter_for(writer)
    await apply_atomic_lua_correction(adapter, 42, metadata(), initializing_exact_start=True)
    await writer.execute("UPDATE player_comprehensive_stats SET time_played_seconds=1800,dpm=0")
    await apply_atomic_lua_correction(adapter, 42, metadata())
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 2
    assert await reader.fetchval("SELECT dpm FROM player_comprehensive_stats") == 120


@pytest.mark.parametrize("global_flag,narrow_flag,expected", [(False,False,False),(True,False,False),(False,True,False),(True,True,True)])
def test_correction_flag_contract(monkeypatch, global_flag, narrow_flag, expected):
    monkeypatch.setenv("EVENT_STREAM_ENABLED", str(global_flag).lower())
    monkeypatch.setenv("LUA_CORRECTION_EVENTS_ENABLED", str(narrow_flag).lower())
    assert lua_correction_events_enabled() is expected


@pytest.mark.parametrize("link_fails", [False, True])
async def test_enabled_real_override_uses_atomic_path(correction_db, monkeypatch, link_fails):
    writer, reader = correction_db
    monkeypatch.setenv("EVENT_STREAM_ENABLED", "true")
    monkeypatch.setenv("LUA_CORRECTION_EVENTS_ENABLED", "true")
    # Existing exact identity, so the pre-transaction resolver chooses it directly.
    await writer.execute("UPDATE rounds SET round_start_unix=1700000000 WHERE id=42")
    linker = AsyncMock(side_effect=RuntimeError("fixture linking failure") if link_fails else None)
    bot = SimpleNamespace(db_adapter=adapter_for(writer), _resolve_lua_round_id_for_metadata=AsyncMock(return_value=42),
                          _link_lua_round_teams=linker)
    await UltimateETLegacyBot._apply_round_metadata_override(bot, "fixture", metadata())  # noqa: SLF001
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 1
    assert await reader.fetchval("SELECT dpm FROM player_comprehensive_stats") == 120
    linker.assert_awaited_once()


async def test_enabled_override_propagates_failed_correction(correction_db, monkeypatch):
    writer, reader = correction_db
    monkeypatch.setenv("EVENT_STREAM_ENABLED", "true")
    monkeypatch.setenv("LUA_CORRECTION_EVENTS_ENABLED", "true")
    await writer.execute("UPDATE rounds SET round_start_unix=1700000000 WHERE id=42")
    await writer.execute("ALTER TABLE player_comprehensive_stats ADD CONSTRAINT reject_dpm CHECK(dpm=0)")
    linker = AsyncMock()
    bot = SimpleNamespace(db_adapter=adapter_for(writer), _resolve_lua_round_id_for_metadata=AsyncMock(return_value=42),
                          _link_lua_round_teams=linker)
    with pytest.raises(Exception, match="reject_dpm"):
        await UltimateETLegacyBot._apply_round_metadata_override(bot, "fixture", metadata())  # noqa: SLF001
    assert await reader.fetchval("SELECT actual_duration_seconds FROM rounds WHERE id=42") == 1800
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 0
    linker.assert_not_awaited()


def test_correction_migration_registration_and_disabled_template():
    root = Path(__file__).resolve().parents[2]
    sql = (root / "migrations/087_runtime_lua_correction_events.sql").read_text().strip()
    assert sql in (root / "tools/schema_postgresql.sql").read_text()
    assert '"087_runtime_lua_correction_events.sql"' in (root / "scripts/release_configs/v1.45.0.sh").read_text()
    assert "LUA_CORRECTION_EVENTS_ENABLED=false" in (root / ".env.example").read_text().splitlines()


async def test_concurrent_identical_correction_serializes(correction_db):
    writer, reader = correction_db
    await writer.execute("UPDATE rounds SET round_start_unix=1700000000 WHERE id=42")
    first = adapter_for(writer)
    task = None
    try:
        async with first.transaction():
            await apply_atomic_lua_correction(first, 42, metadata())  # Nested real savepoint.
            task = asyncio.create_task(apply_atomic_lua_correction(adapter_for(reader), 42, metadata()))
            await asyncio.sleep(0.1)
            assert not task.done()
            assert await writer.fetchval(
                "SELECT wait_event_type FROM pg_stat_activity WHERE pid=$1", reader.get_server_pid()
            ) == "Lock"
        assert await asyncio.wait_for(task, 2)
        assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 1
    finally:
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
