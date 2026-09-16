"""Persisted row comparison on the explicitly isolated PostgreSQL fixture."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from bot.services.endstats_pipeline_mixin import _EndstatsPipelineMixin
from shared.endstats_snapshot import capture_endstats_snapshot, journal_endstats_storage
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401


@pytest.fixture
async def snapshot_db(journal_db):  # noqa: F811
    writer, reader = journal_db
    await writer.execute("""
        CREATE TABLE round_awards (
            id SERIAL, round_id INTEGER, round_date TEXT, map_name TEXT,
            round_number INTEGER, award_name TEXT, player_name TEXT,
            player_guid TEXT, award_value TEXT, award_value_numeric REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE round_vs_stats (
            id SERIAL, round_id INTEGER, round_date TEXT, map_name TEXT,
            round_number INTEGER, player_name TEXT, player_guid TEXT,
            kills INTEGER, deaths INTEGER, subject_name TEXT, subject_guid TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO round_awards(round_id, award_name, award_value_numeric)
            VALUES (1, 'fixture', 'NaN'), (1, 'other', 1), (2, 'excluded', 99);
        INSERT INTO round_vs_stats(round_id, player_name, kills, deaths)
            VALUES (1, 'fixture', 2, 3);
    """)
    return writer, reader


async def test_snapshot_requires_transaction(snapshot_db):
    writer, _ = snapshot_db
    with pytest.raises(RuntimeError, match="storage transaction"):
        await capture_endstats_snapshot(writer, 1)


async def test_reordered_reinsert_with_new_ids_and_clocks_is_identical(snapshot_db):
    writer, reader = snapshot_db
    async with writer.transaction():
        before = await capture_endstats_snapshot(writer, 1)
        await writer.execute("""
            DELETE FROM round_awards WHERE round_id = 1;
            INSERT INTO round_awards(round_id, award_name, award_value_numeric, created_at)
                VALUES (1, 'other', 1, '2000-01-01'), (1, 'fixture', 'NaN', '2000-01-01');
            UPDATE round_vs_stats SET id = id + 100, created_at = '2000-01-01';
        """)
        assert before == await capture_endstats_snapshot(writer, 1)
    assert await reader.fetchval("SELECT count(*) FROM round_awards WHERE round_id=1") == 2
    assert len(await reader.fetch("SELECT * FROM round_awards WHERE round_id=1")) == 2
    print("snapshot runtime: reordered persisted rows and new IDs/clocks compare equal, NaN stable")


@pytest.mark.parametrize("statement", [
    "UPDATE round_awards SET award_value_numeric=2 WHERE award_name='other'",
    "UPDATE round_awards SET player_guid='changed' WHERE award_name='other'",
    "UPDATE round_awards SET award_value='changed' WHERE award_name='other'",
    "UPDATE round_vs_stats SET subject_guid='changed' WHERE round_id=1",
    "UPDATE round_vs_stats SET deaths=4 WHERE round_id=1",
    "INSERT INTO round_vs_stats(round_id,player_name,kills,deaths) VALUES(1,'fixture',2,3)",
])
async def test_real_content_and_duplicate_multiplicity_change_snapshot(snapshot_db, statement):
    writer, _ = snapshot_db
    async with writer.transaction():
        before = await capture_endstats_snapshot(writer, 1)
        await writer.execute(statement)
        assert before != await capture_endstats_snapshot(writer, 1)


async def test_other_round_changes_are_excluded(snapshot_db):
    writer, _ = snapshot_db
    async with writer.transaction():
        before = await capture_endstats_snapshot(writer, 1)
        await writer.execute("UPDATE round_awards SET award_name='changed' WHERE round_id=2")
        assert before == await capture_endstats_snapshot(writer, 1)


async def enable_journal(writer, monkeypatch):
    monkeypatch.setenv("EVENT_STREAM_ENABLED", "true")
    monkeypatch.setenv("ENDSTATS_EVENTS_ENABLED", "true")
    root = Path(__file__).resolve().parents[2]
    for migration in ("083_runtime_events.sql", "084_runtime_timing_events.sql",
                      "085_runtime_status_events.sql", "086_runtime_endstats_events.sql"):
        await writer.execute((root / "migrations" / migration).read_text())
    await writer.execute("INSERT INTO rounds VALUES (1,1,7)")


@pytest.mark.parametrize("publication", ["success", "false", "exception"])
async def test_actual_storage_commits_event_before_discord(snapshot_db, monkeypatch, publication):
    writer, reader = snapshot_db
    await enable_journal(writer, monkeypatch)
    monkeypatch.setenv("ENDSTATS_RETRY_ENABLED", "false")
    await writer.execute("""
        DELETE FROM round_awards;
        DELETE FROM round_vs_stats;
        CREATE TABLE processed_endstats_files (
            id SERIAL PRIMARY KEY, filename TEXT UNIQUE, round_id INTEGER,
            success BOOLEAN, error_message TEXT, processed_at TIMESTAMPTZ
        );
        CREATE TABLE player_aliases(alias TEXT, guid TEXT, last_seen TIMESTAMPTZ);
    """)

    @asynccontextmanager
    async def transaction():
        async with writer.transaction():
            yield writer

    async def fetch_one(query, params=()):
        return await writer.fetchrow(query, *params)

    async def execute(query, params=()):
        return await writer.execute(query, *params)

    attempts = []

    async def publish(*args):
        assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 1
        assert len(await reader.fetch("SELECT * FROM runtime_events")) == 1
        assert await reader.fetchval("SELECT count(*) FROM round_vs_stats") == 1
        attempts.append(args)
        if publication == "exception":
            raise RuntimeError("fixture Discord unavailable after commit")
        return publication == "success"

    bot = object.__new__(_EndstatsPipelineMixin)
    bot.db_adapter = SimpleNamespace(transaction=transaction, fetch_one=fetch_one, execute=execute)
    bot.round_publisher = SimpleNamespace(publish_endstats=publish)
    payload = {"awards": [{"name": "award", "player": "fixture", "value": "1", "numeric": 1}],
               "vs_stats": [{"player": "opponent", "kills": 2, "deaths": 3, "subject": "fixture"}]}

    async def store():
        return await bot._store_endstats_and_publish(  # noqa: SLF001
            "fixture", payload, 1, "2026-09-16", "fixture", 1, logging.getLogger(__name__)
        )

    for _ in range(2):
        if publication == "exception":
            with pytest.raises(RuntimeError, match="Discord unavailable"):
                await store()
        else:
            assert await store() is (publication == "success")
    assert len(attempts) == (1 if publication == "success" else 2)
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 1
    assert await reader.fetchval("SELECT event_type FROM runtime_events") == "round_endstats_changed"
    print(f"storage runtime: publication={publication}, committed event visible before Discord, repeat adds no event")


@pytest.mark.parametrize("failure", ["event", "storage", "notify"])
async def test_event_or_storage_failure_rolls_back_both(snapshot_db, monkeypatch, failure):
    writer, reader = snapshot_db
    await enable_journal(writer, monkeypatch)
    if failure == "event":
        await writer.execute("ALTER TABLE runtime_events ADD CONSTRAINT reject_fixture CHECK (round_id <> 1)")
    class NotifyFailure:
        def __getattr__(self, name):
            return getattr(writer, name)

        async def execute(self, query, *args):
            if "pg_notify" in query:
                raise RuntimeError("fixture notify failure")
            return await writer.execute(query, *args)

    connection = NotifyFailure() if failure == "notify" else writer
    with pytest.raises(Exception, match="reject_fixture|fixture storage failure|fixture notify failure"):
        async with writer.transaction(), journal_endstats_storage(connection, round_id=1):
            await writer.execute("UPDATE round_vs_stats SET kills=99 WHERE round_id=1")
            if failure == "storage":
                raise RuntimeError("fixture storage failure")
    assert await reader.fetchval("SELECT kills FROM round_vs_stats WHERE round_id=1") == 2
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 0


@pytest.mark.parametrize("round_number", [0, 2])
async def test_journal_round_scope(snapshot_db, monkeypatch, round_number):
    writer, reader = snapshot_db
    await enable_journal(writer, monkeypatch)
    await writer.execute("UPDATE rounds SET round_number=$1 WHERE id=1", round_number)
    async with writer.transaction(), journal_endstats_storage(writer, round_id=1):
        await writer.execute("UPDATE round_vs_stats SET kills=99 WHERE round_id=1")
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == int(round_number == 2)
    if round_number == 2:
        row = await reader.fetchrow("SELECT round_number, gaming_session_id FROM runtime_events")
        assert tuple(row) == (2, 7)


async def test_missing_round_rejected_before_storage(snapshot_db, monkeypatch):
    writer, _ = snapshot_db
    await enable_journal(writer, monkeypatch)
    with pytest.raises(ValueError, match="missing round"):
        async with writer.transaction(), journal_endstats_storage(writer, round_id=999):
            pytest.fail("Storage must not execute for a missing round")


@pytest.mark.parametrize("global_flag,narrow_flag", [(False, False), (False, True), (True, False)])
async def test_disabled_journal_needs_no_connection(monkeypatch, global_flag, narrow_flag):
    monkeypatch.setenv("EVENT_STREAM_ENABLED", str(global_flag).lower())
    monkeypatch.setenv("ENDSTATS_EVENTS_ENABLED", str(narrow_flag).lower())
    async with journal_endstats_storage(None, round_id=1):
        pass


async def test_same_round_writer_waits_before_reading(snapshot_db, monkeypatch):
    writer, reader = snapshot_db
    await enable_journal(writer, monkeypatch)
    entered = asyncio.Event()

    async def second_writer():
        async with reader.transaction(), journal_endstats_storage(reader, round_id=1):
            entered.set()
            assert await reader.fetchval("SELECT kills FROM round_vs_stats WHERE round_id=1") == 99

    task = None
    try:
        async with writer.transaction(), journal_endstats_storage(writer, round_id=1):
            await writer.execute("UPDATE round_vs_stats SET kills=99 WHERE round_id=1")
            task = asyncio.create_task(second_writer())
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(entered.wait(), 0.1)
            assert await writer.fetchval(
                "SELECT wait_event_type FROM pg_stat_activity WHERE pid=$1", reader.get_server_pid()
            ) == "Lock"
        await asyncio.wait_for(task, 2)
        assert entered.is_set()
        assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 1
        print("concurrency runtime: second transaction waits on PG lock, then sees committed first write")
    finally:
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
