"""Actual PostgreSQL receipt/generation proofs, not HTTP invalidation proof."""

import asyncio
import subprocess
from pathlib import Path

import asyncpg
import pytest

from shared.runtime_cache_consumer import CACHE_NAME, CONSUMER, SUPPORTED_EVENTS, consume_http_cache_events
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401


@pytest.fixture
async def cache_db(journal_db, monkeypatch):  # noqa: F811
    writer, reader = journal_db
    monkeypatch.setenv("EVENT_STREAM_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_HTTP_CACHE_EVENTS_ENABLED", "true")
    root = Path(__file__).resolve().parents[2]
    for name in (
        "083_runtime_events.sql", "084_runtime_timing_events.sql", "085_runtime_status_events.sql",
        "086_runtime_endstats_events.sql", "087_runtime_lua_correction_events.sql", "091_runtime_cache_consumer.sql",
    ):
        await writer.execute((root / "migrations" / name).read_text())
    return writer, reader


async def event(conn, round_id=42, event_type="round_stats_imported", schema_version=1):
    return await conn.fetchval("""
        INSERT INTO runtime_events(event_type,schema_version,round_id,round_number,
                                   source_filename,validation_passed,event_details)
        VALUES($1,$2,$3,1,$4,$5,$6::jsonb) RETURNING id
    """, event_type, schema_version, round_id,
        "fixture.txt" if event_type == "round_stats_imported" else None,
        True if event_type == "round_stats_imported" else None,
        None if event_type == "round_stats_imported" else '{}')


@pytest.mark.parametrize("off", ["EVENT_STREAM_ENABLED", "RUNTIME_HTTP_CACHE_EVENTS_ENABLED"])
async def test_off_does_not_touch_database(monkeypatch, off):
    monkeypatch.setenv("EVENT_STREAM_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_HTTP_CACHE_EVENTS_ENABLED", "true")
    monkeypatch.setenv(off, "false")
    result = await consume_http_cache_events(None)
    assert (result.status, result.processed, result.generation, result.unsupported_pending) == ("disabled", 0, None, None)


@pytest.mark.parametrize("bad", [True, False, 0, -1, 1001, "100", 1.5])
async def test_invalid_batch_rejected_before_database(monkeypatch, bad):
    monkeypatch.setenv("EVENT_STREAM_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_HTTP_CACHE_EVENTS_ENABLED", "true")
    with pytest.raises(ValueError, match="batch size"):
        await consume_http_cache_events(None, batch_size=bad)


async def test_all_supported_types_commit_once_and_idle_does_not_advance(cache_db):
    writer, reader = cache_db
    for event_type in SUPPORTED_EVENTS:
        await event(writer, event_type=event_type)
    result = await consume_http_cache_events(writer)
    assert (result.status, result.processed, result.generation, result.unsupported_pending) == ("advanced", 5, 1, 0)
    assert await reader.fetchval("SELECT count(*) FROM runtime_consumer_receipts") == len(await reader.fetch("SELECT * FROM runtime_consumer_receipts")) == 5
    again = await consume_http_cache_events(reader)
    assert (again.status, again.processed, again.generation) == ("idle", 0, 1)


async def test_receipt_failure_rolls_back_generation(cache_db):
    writer, reader = cache_db
    await consume_http_cache_events(writer)  # Persist empty generation zero.
    await event(writer)
    await writer.execute("ALTER TABLE runtime_consumer_receipts ADD CONSTRAINT fixture_failure CHECK(false)")
    with pytest.raises(asyncpg.CheckViolationError, match="fixture_failure"):
        await consume_http_cache_events(writer)
    assert await reader.fetchval("SELECT generation FROM runtime_cache_generations") == 0
    assert await reader.fetchval("SELECT count(*) FROM runtime_consumer_receipts") == 0
    await writer.execute("ALTER TABLE runtime_consumer_receipts DROP CONSTRAINT fixture_failure")
    assert (await consume_http_cache_events(reader)).processed == 1


async def test_generation_failure_creates_no_receipt(cache_db):
    writer, reader = cache_db
    await event(writer)
    await writer.execute("ALTER TABLE runtime_cache_generations ADD CONSTRAINT fixture_failure CHECK(generation=0)")
    with pytest.raises(asyncpg.CheckViolationError, match="fixture_failure"):
        await consume_http_cache_events(writer)
    assert await reader.fetchval("SELECT count(*) FROM runtime_consumer_receipts") == 0


async def test_commit_failure_does_not_acknowledge_effect(cache_db):
    writer, reader = cache_db
    await consume_http_cache_events(writer)
    await event(writer)
    await writer.execute("""
        CREATE FUNCTION reject_receipt_commit() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'fixture commit rejection' USING ERRCODE='23514';
            RETURN NEW;
        END;
        $$;
        CREATE CONSTRAINT TRIGGER fixture_deferred_rejection
        AFTER INSERT ON runtime_consumer_receipts DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION reject_receipt_commit();
    """)
    with pytest.raises(asyncpg.CheckViolationError, match="fixture commit rejection"):
        await consume_http_cache_events(writer)
    assert await reader.fetchval("SELECT generation FROM runtime_cache_generations") == 0
    assert await reader.fetchval("SELECT count(*) FROM runtime_consumer_receipts") == 0


async def test_late_committing_lower_event_id_is_caught_up(cache_db):
    writer, reader = cache_db
    async with writer.transaction():
        earlier = await event(writer, round_id=42)
        later = await event(reader, round_id=43)
        assert earlier < later
        assert (await consume_http_cache_events(reader)).processed == 1
        assert await reader.fetchval("SELECT event_id FROM runtime_consumer_receipts") == later
    result = await consume_http_cache_events(reader)
    assert (result.processed, result.generation) == (1, 2)
    assert await reader.fetchval("SELECT count(*) FROM runtime_consumer_receipts") == 2


async def test_bounded_batches_leave_remainder_for_next_call(cache_db):
    writer, reader = cache_db
    for round_id in range(7):
        await event(writer, round_id=round_id)
    results = [await consume_http_cache_events(writer, batch_size=3) for _ in range(3)]
    assert [result.processed for result in results] == [3, 3, 1]
    assert [result.generation for result in results] == [1, 2, 3]
    assert await reader.fetchval("SELECT count(*) FROM runtime_consumer_receipts") == 7


async def test_concurrent_consumers_serialize_the_same_effect(cache_db):
    writer, reader = cache_db
    await event(writer)
    results = await asyncio.gather(consume_http_cache_events(writer), consume_http_cache_events(reader))
    assert sorted(result.processed for result in results) == [0, 1]
    assert {result.generation for result in results} == {1}
    assert await reader.fetchval("SELECT count(*) FROM runtime_consumer_receipts") == 1


async def test_generation_is_locked_before_selecting_events(cache_db):
    writer, reader = cache_db
    await consume_http_cache_events(writer)
    await event(writer)
    task = None
    try:
        async with reader.transaction():
            await reader.fetchrow("SELECT * FROM runtime_cache_generations FOR UPDATE")
            task = asyncio.create_task(consume_http_cache_events(writer))
            for _ in range(100):
                await reader.execute("SELECT pg_stat_clear_snapshot()")
                activity = await reader.fetchrow(
                    "SELECT wait_event_type,query FROM pg_stat_activity WHERE pid=$1", writer.get_server_pid(),
                )
                if activity["wait_event_type"] == "Lock":
                    break
                await asyncio.sleep(0.01)
            assert activity["wait_event_type"] == "Lock"
            assert "SELECT generation" in activity["query"]
            assert "FOR UPDATE" in activity["query"]
            assert not task.done()
        assert (await asyncio.wait_for(task, timeout=5)).processed == 1
    finally:
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_caller_transaction_is_rejected(cache_db):
    writer, reader = cache_db
    async with writer.transaction():
        with pytest.raises(RuntimeError, match="own transaction"):
            await consume_http_cache_events(writer)
    assert await reader.fetchval("SELECT count(*) FROM runtime_cache_generations") == 0


async def test_unknown_schema_or_event_is_visible_without_starvation(cache_db):
    writer, reader = cache_db
    await writer.execute("ALTER TABLE runtime_events DROP CONSTRAINT runtime_events_schema_version_check")
    await writer.execute("ALTER TABLE runtime_events DROP CONSTRAINT runtime_events_event_type_check")
    await writer.execute("ALTER TABLE runtime_events DROP CONSTRAINT runtime_events_details_check")
    await event(writer, round_id=40, schema_version=2)
    await event(writer, round_id=41, event_type="future_event")
    valid = await event(writer)
    result = await consume_http_cache_events(writer, batch_size=1)
    assert (result.processed, result.unsupported_pending, result.generation) == (1, 2, 1)
    assert await reader.fetchval("SELECT event_id FROM runtime_consumer_receipts") == valid
    again = await consume_http_cache_events(reader)
    assert (again.status, again.processed, again.unsupported_pending) == ("unsupported", 0, 2)


async def test_other_consumer_receipts_do_not_acknowledge_this_consumer(cache_db):
    writer, reader = cache_db
    event_id = await event(writer)
    await writer.execute("INSERT INTO runtime_consumer_receipts(consumer_name,event_id) VALUES('another',$1)", event_id)
    assert (await consume_http_cache_events(writer)).processed == 1
    assert await reader.fetchval("SELECT count(*) FROM runtime_consumer_receipts WHERE consumer_name=$1", CONSUMER) == 1
    assert await reader.fetchval("SELECT generation FROM runtime_cache_generations WHERE cache_name=$1", CACHE_NAME) == 1


def test_migration_registration_and_bootstrap():
    root = Path(__file__).resolve().parents[2]
    name = "091_runtime_cache_consumer.sql"
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; printf "%s\\n" "${MIGRATIONS[@]}"',
         "release-config", str(root / "scripts/release_configs/v1.45.0.sh")],
        check=True, capture_output=True, text=True, timeout=5,
    )
    assert name in result.stdout.splitlines()
    assert (root / "migrations" / name).read_text().strip() in (root / "tools/schema_postgresql.sql").read_text()
