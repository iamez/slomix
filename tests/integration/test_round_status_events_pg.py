"""Real status journal proofs, strictly on the explicit disposable PG target."""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from shared.round_status_events import mark_round_restart
from tests.integration.test_round_timing_events_pg import timing_db  # noqa: F401
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401


@pytest.fixture
async def status_db(timing_db):  # noqa: F811
    writer, reader, _ = timing_db
    await writer.execute("ALTER TABLE rounds ADD COLUMN round_status TEXT DEFAULT 'completed'")
    sql = (Path(__file__).resolve().parents[2] / "migrations/085_runtime_status_events.sql").read_text()
    await writer.execute(sql)
    await writer.execute(sql)
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id) VALUES (1,1,42),(2,1,42),(3,0,42)")
    return writer, reader


async def mark(conn, status="cancelled", round_id=1):
    return await mark_round_restart(conn, round_id=round_id, status=status, caused_by_round_id=2)


@pytest.mark.parametrize("status", ["cancelled", "substitution"])
async def test_commit_visibility_notification_and_noop(status_db, status):
    writer, reader = status_db
    notifications = asyncio.Queue()
    await reader.add_listener("round_events", lambda conn, pid, channel, payload: notifications.put_nowait(payload))
    async with writer.transaction():
        assert await mark(writer, status)
        assert not await mark(writer, status)
        assert not await mark(writer, status, round_id=3)
        assert await reader.fetchval("SELECT round_status FROM rounds WHERE id=1") == "completed"
        assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 0
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(notifications.get(), 0.1)
    event = await reader.fetchrow("SELECT * FROM runtime_events")
    assert await asyncio.wait_for(notifications.get(), 2) == str(event["id"])
    assert json.loads(event["event_details"]) == {
        "source": "restart_detection", "old_status": "completed",
        "new_status": status, "caused_by_round_id": 2,
    }
    assert await reader.fetchval("SELECT round_status FROM rounds WHERE id=1") == status
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 1
    assert len(await reader.fetch("SELECT * FROM runtime_events")) == 1
    print("R02b commit proof: status and event invisible before commit; one ID-only notification")


async def test_event_failure_rolls_back_current_import_and_old_status(status_db):
    writer, reader = status_db
    await writer.execute("ALTER TABLE runtime_events ADD CONSTRAINT reject_status CHECK(event_type <> 'round_status_changed')")
    with pytest.raises(asyncpg.CheckViolationError):
        async with writer.transaction():
            await writer.execute("INSERT INTO rounds (id,round_number) VALUES (4,1)")
            await mark(writer)
    assert await reader.fetchval("SELECT round_status FROM rounds WHERE id=1") == "completed"
    assert await reader.fetchval("SELECT count(*) FROM rounds WHERE id=4") == 0
    assert await reader.fetch("SELECT * FROM runtime_events") == []
    await writer.execute("ALTER TABLE runtime_events DROP CONSTRAINT reject_status")
    async with writer.transaction():
        assert await mark(writer)
    print("R02b rollback proof: rejected event rolls back new round and older status; retry succeeds")


async def test_concurrent_and_later_real_transition(status_db):
    writer, reader = status_db

    async def run(conn):
        async with conn.transaction():
            return await mark(conn)

    assert sum(await asyncio.gather(run(writer), run(reader))) == 1
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 1
    await writer.execute("UPDATE rounds SET round_status='completed' WHERE id=1")
    assert await run(writer)
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 2
    assert len(await reader.fetch("SELECT * FROM runtime_events")) == 2


async def test_notify_failure_rolls_back_status_and_event(status_db):
    writer, reader = status_db
    proxy = SimpleNamespace(
        is_in_transaction=writer.is_in_transaction, fetchrow=writer.fetchrow,
        fetchval=writer.fetchval, execute=AsyncMock(side_effect=RuntimeError("injected NOTIFY failure")),
    )
    with pytest.raises(RuntimeError, match="injected NOTIFY failure"):
        async with writer.transaction():
            await mark(proxy)
    assert await reader.fetchval("SELECT round_status FROM rounds WHERE id=1") == "completed"
    assert await reader.fetch("SELECT * FROM runtime_events") == []


async def test_canonical_import_status_failure_is_retryable(status_db, monkeypatch):
    """Canonical outer transaction + actual detector; parser/current insert stubbed."""
    from postgresql_database_manager import PostgreSQLDatabaseManager

    monkeypatch.setenv("EVENT_STREAM_ENABLED", "true")
    monkeypatch.setenv("ROUND_STATUS_EVENTS_ENABLED", "true")
    writer, reader = status_db
    await writer.execute("""
        ALTER TABLE rounds ADD COLUMN round_date TEXT DEFAULT '2026-09-14',
            ADD COLUMN round_time TEXT DEFAULT '120000', ADD COLUMN match_id TEXT;
        CREATE TABLE processed_files (filename TEXT PRIMARY KEY, success BOOLEAN);
        ALTER TABLE runtime_events ADD CONSTRAINT reject_status CHECK(event_type <> 'round_status_changed');
        UPDATE rounds SET round_status='cancelled' WHERE id=2;
    """)
    manager = object.__new__(PostgreSQLDatabaseManager)
    manager.event_stream_enabled = True
    manager.stats = dict.fromkeys([
        "files_processed", "files_skipped", "files_failed", "rounds_created",
        "players_inserted", "weapons_inserted",
    ], 0)
    manager.parser = SimpleNamespace(parse_stats_file=MagicMock(return_value={"players": [], "round_num": 1}))
    manager._compute_file_hashes = MagicMock(return_value=("a" * 64, "a" * 64))  # noqa: SLF001
    manager._extract_date_time_from_filename = MagicMock(return_value=("2026-09-14", "120200"))  # noqa: SLF001
    manager.find_processed_by_hash = AsyncMock(return_value=None)
    manager._insert_player_stats = AsyncMock(return_value=0)  # noqa: SLF001
    manager._insert_weapon_stats = AsyncMock(return_value=0)  # noqa: SLF001
    manager._validate_round_data = AsyncMock(return_value=(True, "ok"))  # noqa: SLF001
    manager._auto_assign_teams_from_r1 = AsyncMock()  # noqa: SLF001 -- outside journal contract

    @asynccontextmanager
    async def acquire():
        yield writer

    async def create_round(conn, *args):
        await conn.execute("INSERT INTO rounds (id,round_number,gaming_session_id,round_time) VALUES (4,1,42,'120200')")
        await manager._detect_and_mark_restarts(conn, 4, 42, "fixture", 1, "2026-09-14", "120200")  # noqa: SLF001
        return 4

    async def processed(filename):
        return bool(await writer.fetchval("SELECT count(*) FROM processed_files WHERE filename=$1", filename))

    async def record(filename, *, success, **kwargs):
        await writer.execute("INSERT INTO processed_files VALUES ($1,$2)", filename, success)

    manager.pool = SimpleNamespace(acquire=acquire)
    manager._create_round_postgresql = create_round  # noqa: SLF001
    manager.is_file_processed = processed
    manager.mark_file_processed = record
    result = await manager.process_file(Path("fixture-round-1.txt"))
    assert result[0] is False and result.retryable
    assert await reader.fetchval("SELECT round_status FROM rounds WHERE id=1") == "completed"
    assert await reader.fetchval("SELECT count(*) FROM rounds WHERE id=4") == 0
    assert await reader.fetch("SELECT * FROM processed_files") == []
    await writer.execute("ALTER TABLE runtime_events DROP CONSTRAINT reject_status")
    assert (await manager.process_file(Path("fixture-round-1.txt")))[0] is True
    assert await reader.fetchval("SELECT round_status FROM rounds WHERE id=1") == "cancelled"
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 2
    assert len(await reader.fetch("SELECT * FROM runtime_events")) == 2
    assert await reader.fetchval("SELECT success FROM processed_files") is True
    print("R02b canonical proof: detector failure rolls import back without marker; retry commits both events")
