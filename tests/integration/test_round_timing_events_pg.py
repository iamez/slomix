"""R02a real SQL proofs on the same explicitly isolated target as R01."""

import asyncio
import hashlib
import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import asyncpg
import pytest

from shared.round_timing_reconcile import reconcile_missing_round_timing
from shared.runtime_events import emit_round_stats_imported
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401 -- shared safe fixture


@pytest.fixture
async def timing_db(journal_db):  # noqa: F811 -- imported pytest fixture injection
    writer, reader = journal_db
    await writer.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public")
    # pgcrypto is explicitly public; include it after the private schema.
    schema = await writer.fetchval("SELECT current_schema()")
    for conn in (writer, reader):
        await conn.execute(f'SET search_path TO "{schema}", public')
    await writer.execute("""
        ALTER TABLE rounds ADD COLUMN actual_duration_seconds INTEGER,
            ADD COLUMN round_start_unix BIGINT, ADD COLUMN round_end_unix BIGINT,
            ADD COLUMN end_reason TEXT, ADD COLUMN total_pause_seconds INTEGER,
            ADD COLUMN pause_count INTEGER, ADD COLUMN map_name TEXT DEFAULT 'fixture',
            ADD COLUMN round_canonical_id TEXT;
        CREATE UNIQUE INDEX test_canonical_id ON rounds(round_canonical_id);
        CREATE TABLE lua_round_teams (
            id INTEGER PRIMARY KEY, round_id INTEGER, actual_duration_seconds INTEGER,
            round_start_unix BIGINT, round_end_unix BIGINT, end_reason TEXT,
            total_pause_seconds INTEGER, pause_count INTEGER
        )
    """)
    root = Path(__file__).resolve().parents[2]
    for name in ("083_runtime_events.sql", "084_runtime_timing_events.sql", "084_runtime_timing_events.sql"):
        await writer.execute((root / "migrations" / name).read_text())

    @asynccontextmanager
    async def transaction():
        async with writer.transaction():
            yield writer

    return writer, reader, SimpleNamespace(transaction=transaction)


async def seed(conn, round_id=1, round_number=1):
    await conn.execute("INSERT INTO rounds (id, round_number, gaming_session_id) VALUES ($1,$2,42)", round_id, round_number)
    await conn.execute("INSERT INTO lua_round_teams VALUES ($1,$1,60,$2,$3,'NORMAL',0,0)", round_id, round_id * 1000, round_id * 1000 + 60)


async def fill(adapter):
    return await reconcile_missing_round_timing(adapter, enabled=True)


async def test_commit_notify_noop_and_scoped_canonical_ids(timing_db):
    writer, reader, adapter = timing_db
    await seed(writer)
    await writer.execute("INSERT INTO rounds (id,round_number,actual_duration_seconds,round_start_unix) VALUES (99,1,10,99000)")
    notifications = asyncio.Queue()
    await reader.add_listener("round_events", lambda conn, pid, channel, payload: notifications.put_nowait(payload))

    @asynccontextmanager
    async def observed_transaction():
        async with writer.transaction():
            yield writer
            assert await reader.fetchval("SELECT actual_duration_seconds FROM rounds WHERE id=1") is None
            assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 0
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(notifications.get(), 0.1)

    assert await fill(SimpleNamespace(transaction=observed_transaction)) == 1
    event_id = await asyncio.wait_for(notifications.get(), 2)
    event = await reader.fetchrow("SELECT * FROM runtime_events")
    assert str(event["id"]) == event_id and event["event_type"] == "round_timing_reconciled"
    assert json.loads(event["event_details"])["actual_duration_seconds"] == 60
    assert await reader.fetchval("SELECT actual_duration_seconds FROM rounds WHERE id=1") == 60
    expected = hashlib.sha256(b"1000:fixture:1").hexdigest()[:16]
    assert await reader.fetchval("SELECT round_canonical_id FROM rounds WHERE id=1") == expected
    assert await reader.fetchval("SELECT round_canonical_id FROM rounds WHERE id=99") is None
    assert await fill(adapter) == 0
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 1
    assert len(await reader.fetch("SELECT * FROM runtime_events")) == 1
    print("R02a commit proof: timing + scoped canonical ID + event, one notification, repeat no-op")


async def test_event_failure_rolls_back_timing_and_allows_retry(timing_db):
    writer, reader, adapter = timing_db
    await seed(writer)
    await writer.execute("ALTER TABLE runtime_events ADD CONSTRAINT test_reject CHECK (event_type <> 'round_timing_reconciled')")
    with pytest.raises(asyncpg.CheckViolationError):
        await fill(adapter)
    assert await reader.fetchval("SELECT actual_duration_seconds FROM rounds WHERE id=1") is None
    assert await reader.fetchval("SELECT round_canonical_id FROM rounds WHERE id=1") is None
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 0
    await writer.execute("ALTER TABLE runtime_events DROP CONSTRAINT test_reject")
    assert await fill(adapter) == 1
    print("R02a rollback proof: rejected event leaves timing NULL; retry commits")


async def test_r0_and_ambiguous_sources_are_excluded(timing_db):
    writer, reader, adapter = timing_db
    await seed(writer, 1, 0)
    await seed(writer, 2, 2)
    await writer.execute("INSERT INTO lua_round_teams VALUES (3,2,70,2000,2070,'NORMAL',0,0)")
    assert await fill(adapter) == 0
    assert await reader.fetchval("SELECT count(*) FROM rounds WHERE actual_duration_seconds IS NULL") == 2
    assert await reader.fetch("SELECT * FROM runtime_events") == []


async def test_concurrent_fill_and_repeat_transition(timing_db):
    writer, reader, adapter = timing_db
    await seed(writer)

    @asynccontextmanager
    async def other_transaction():
        async with reader.transaction():
            yield reader

    results = await asyncio.gather(fill(adapter), fill(SimpleNamespace(transaction=other_transaction)))
    assert sum(results) == 1
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 1
    # A future explicit repair clearing duration is a new transition, not
    # deduplicated forever by (round_id, event_type) or the old payload hash.
    await writer.execute("UPDATE rounds SET actual_duration_seconds=NULL WHERE id=1")
    assert await fill(adapter) == 1
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 2
    assert len(await reader.fetch("SELECT * FROM runtime_events")) == 2


async def test_initial_import_dedup_survives_schema_upgrade(timing_db):
    writer, reader, adapter = timing_db
    await seed(writer)
    async with writer.transaction():
        args = dict(enabled=True, round_id=1, source_filename="fixture.txt",
                    source_payload_sha256=None, validation_passed=True)
        assert await emit_round_stats_imported(writer, **args) is not None
        assert await emit_round_stats_imported(writer, **args) is None
    assert await fill(adapter) == 1
    assert set(await reader.fetch("SELECT event_type FROM runtime_events")) == {
        ("round_stats_imported",), ("round_timing_reconciled",),
    }


async def test_fill_is_bounded_per_poll(timing_db):
    writer, reader, adapter = timing_db
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id) SELECT n,1,42 FROM generate_series(1,101) n")
    await writer.execute("INSERT INTO lua_round_teams SELECT n,n,60,n*1000,n*1000+60,'NORMAL',0,0 FROM generate_series(1,101) n")
    assert await fill(adapter) == 100
    assert await reader.fetchval("SELECT count(*) FROM rounds WHERE actual_duration_seconds IS NULL") == 1
    assert await fill(adapter) == 1
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 101
    assert len(await reader.fetch("SELECT * FROM runtime_events")) == 101
