"""Opt-in journal proof against an owner-approved disposable PG cluster.

RUNTIME_EVENTS_TEST_SOCKET must name a private /tmp/slomix-runtime-pg-* socket
directory. No fallback to the application's database or POSTGRES_* settings.
This file never starts a server. Two connections observe visibility and NOTIFY.
"""

import asyncio
import os
import stat
import uuid
from pathlib import Path

import asyncpg
import pytest

from shared.runtime_events import emit_round_stats_imported


@pytest.fixture
async def journal_db():
    socket = os.getenv("RUNTIME_EVENTS_TEST_SOCKET")
    if not socket:
        pytest.skip("Disposable PostgreSQL not explicitly configured")
    path = Path(socket).resolve()
    if path.parent != Path("/tmp") or not path.name.startswith("slomix-runtime-pg-"):
        pytest.fail("Refusing non-disposable PostgreSQL socket path")
    info = path.stat()
    if not path.is_dir() or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        pytest.fail("Disposable PostgreSQL directory must be owned by this user with mode 0700")
    options = dict(host=str(path), database="postgres", timeout=5)
    writer = await asyncpg.connect(**options)
    reader = None
    schema = "runtime_events_test_" + uuid.uuid4().hex
    try:
        reader = await asyncpg.connect(**options)
        await writer.execute(f'CREATE SCHEMA "{schema}"')
        for conn in (writer, reader):
            await conn.execute(f'SET search_path TO "{schema}"')
        await writer.execute("""
            CREATE TABLE rounds (
                id INTEGER PRIMARY KEY, round_number INTEGER, gaming_session_id INTEGER
            )
        """)
        yield writer, reader
    finally:
        try:
            if reader is not None:
                await reader.close(timeout=5)
        finally:
            try:
                await writer.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE', timeout=5)
            finally:
                await writer.close(timeout=5)


async def migrate(conn):
    migration = Path(__file__).resolve().parents[2] / "migrations/083_runtime_events.sql"
    await conn.execute(migration.read_text())


async def emit(conn, round_id=1, enabled=True):
    return await emit_round_stats_imported(
        conn, enabled=enabled, round_id=round_id,
        source_filename="fixture-round-1.txt", source_payload_sha256="a" * 64,
        validation_passed=True,
    )


async def test_commit_visibility_retry_and_notification(journal_db):
    writer, reader = journal_db
    await migrate(writer)
    await migrate(writer)  # migration rerun must preserve the journal
    notifications = asyncio.Queue()

    def notified(conn, pid, channel, payload):
        notifications.put_nowait(payload)

    await reader.add_listener("round_events", notified)
    async with writer.transaction():
        await writer.execute("INSERT INTO rounds VALUES (1, 1, 42)")
        event_id = await emit(writer)
        assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 0
        assert await reader.fetchval("SELECT count(*) FROM rounds") == 0
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(notifications.get(), 0.1)
    assert await asyncio.wait_for(notifications.get(), 2) == str(event_id)
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 1
    rows = await reader.fetch("SELECT * FROM runtime_events")
    assert len(rows) == 1 and rows[0]["round_id"] == 1
    assert rows[0]["gaming_session_id"] == 42
    assert rows[0]["source_payload_sha256"] == "a" * 64
    assert rows[0]["event_type"] == "round_stats_imported"
    async with writer.transaction():
        assert await emit(writer) is None  # commit-before-processed_files retry
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(notifications.get(), 0.1)
    print(f"R01 commit proof: event={event_id}, row_count=1, retry=no new event/notify")


async def test_rollback_hides_data_event_and_notification(journal_db):
    writer, reader = journal_db
    await migrate(writer)
    notifications = asyncio.Queue()
    await reader.add_listener(
        "round_events", lambda conn, pid, channel, payload: notifications.put_nowait(payload),
    )
    with pytest.raises(RuntimeError, match="failure after journal"):
        async with writer.transaction():
            await writer.execute("INSERT INTO rounds VALUES (1, 1, 42)")
            assert await emit(writer) is not None
            raise RuntimeError("failure after journal")
    assert await reader.fetch("SELECT * FROM rounds") == []
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 0
    assert await reader.fetch("SELECT * FROM runtime_events") == []
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(notifications.get(), 0.1)
    print("R01 rollback proof: no round, no event, no notification")


async def test_disabled_without_migration_and_enabled_failure(journal_db):
    writer, reader = journal_db
    async with writer.transaction():
        await writer.execute("INSERT INTO rounds VALUES (1, 1, 42)")
        assert await emit(writer, enabled=False) is None
    assert await reader.fetchval("SELECT count(*) FROM rounds") == 1
    with pytest.raises(asyncpg.UndefinedTableError):
        async with writer.transaction():
            await writer.execute("INSERT INTO rounds VALUES (2, 2, 42)")
            await emit(writer, round_id=2)
    assert await reader.fetchval("SELECT count(*) FROM rounds") == 1
    assert await reader.fetchval("SELECT id FROM rounds") == 1
    print("R01 flag proof: OFF imports without journal; ON missing table rolls back")


async def test_r0_exclusion_and_concurrent_retry(journal_db):
    writer, reader = journal_db
    await migrate(writer)
    await writer.execute("INSERT INTO rounds VALUES (1, 1, 42), (2, 0, 42)")
    async with writer.transaction():
        assert await emit(writer, round_id=2) is None
    async def attempt(conn):
        async with conn.transaction():
            return await emit(conn)
    results = await asyncio.gather(attempt(writer), attempt(reader))
    assert sum(result is not None for result in results) == 1
    assert await writer.fetchval("SELECT count(*) FROM runtime_events") == 1
    assert len(await reader.fetch("SELECT * FROM runtime_events")) == 1
    print("R01 concurrency proof: two initial writers, exactly one event; no R0")
