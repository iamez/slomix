"""Durable catch-up without notifications against explicitly isolated PG."""

import asyncio
import json
import os
import signal
import sys
from contextlib import asynccontextmanager

import asyncpg
import pytest

from shared.runtime_cache_worker import RuntimeCacheWorker
from tests.integration.test_runtime_cache_consumer_pg import cache_db, event  # noqa: F401
from tests.integration.test_runtime_events_pg import connection_options, journal_db  # noqa: F401


@pytest.mark.parametrize("blocked_shutdown", [False, True])
async def test_independent_process_catches_up_and_handles_signal(cache_db, blocked_shutdown):  # noqa: F811
    writer, reader = cache_db
    options = connection_options()  # Refuses application DB fallback.
    await writer.execute("INSERT INTO rounds VALUES(42,1,7)")
    await event(writer)
    schema = await writer.fetchval("SELECT current_schema()")
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("POSTGRES_", "PG", "DISCORD_"))}
    env.update(
        BOT_ENVIRONMENT="dev", EVENT_STREAM_ENABLED="true",
        RUNTIME_HTTP_CACHE_EVENTS_ENABLED="true", RUNTIME_HTTP_CACHE_WORKER_ENABLED="true",
        POSTGRES_HOST=options["host"], POSTGRES_PORT=str(options.get("port", 5432)),
        POSTGRES_DATABASE=options["database"],
        POSTGRES_USER=options.get("user", os.environ.get("USER", "")),
        POSTGRES_PASSWORD=options.get("password", ""), RUNTIME_CACHE_DB_SCHEMA=schema,
    )
    lock = writer.transaction()
    locked = False
    process = None
    records = []
    try:
        if blocked_shutdown:
            await lock.start()
            locked = True
            await writer.execute("LOCK runtime_cache_generations IN ACCESS EXCLUSIVE MODE")
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "shared.runtime_cache_main", env=env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        async with asyncio.timeout(15):
            while True:
                line = await process.stdout.readline()
                assert line, "Cache process exited before proof"
                records.append(json.loads(line))
                if blocked_shutdown:
                    waiting = await reader.fetchval("""
                        SELECT count(*) FROM pg_stat_activity
                        WHERE application_name='slomix-runtime-cache-dev'
                          AND wait_event_type='Lock'
                    """)
                    if waiting == 1:
                        break
                elif records[-1]["generation"] == 1:
                    break
        # Signals target only this fixture-owned child, never a service.
        process.send_signal(signal.SIGINT if blocked_shutdown else signal.SIGTERM)
        stdout, stderr = await asyncio.wait_for(process.communicate(), 15)
        records.extend(json.loads(line) for line in stdout.splitlines())
        assert process.returncode == 0, stderr.decode()
        assert records[-1]["status"] == "stopped"
        count = await reader.fetchval("SELECT count(*) FROM runtime_consumer_receipts")
        rows = await reader.fetch("SELECT event_id FROM runtime_consumer_receipts")
        assert count == len(rows) == (0 if blocked_shutdown else 1)
        assert not await reader.fetchval("""
            SELECT count(*) FROM pg_stat_activity
            WHERE application_name='slomix-runtime-cache-dev'
        """)
        print(f"Process PG proof: blocked={blocked_shutdown}, exit=0, receipts={count}, no connections remain")
    finally:
        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.communicate(), 15)
            except TimeoutError:
                process.kill()
                await process.communicate()
        if locked:
            await lock.rollback()


async def until(predicate):
    async with asyncio.timeout(2):
        while not predicate():
            await asyncio.sleep(0.001)


async def test_poll_catches_late_low_id_and_restart_does_not_repeat(cache_db, monkeypatch):  # noqa: F811
    writer, reader = cache_db
    monkeypatch.setenv("RUNTIME_HTTP_CACHE_WORKER_ENABLED", "true")
    await writer.execute("INSERT INTO rounds VALUES(42,1,7)")
    late = reader.transaction()
    await late.start()
    task = None
    committed = False
    stop = asyncio.Event()

    @asynccontextmanager
    async def acquire():
        yield writer

    try:
        low = await event(reader)
        high = await event(writer, event_type="round_lua_corrected")
        assert low < high
        worker = RuntimeCacheWorker(poll_seconds=0.01)
        task = asyncio.create_task(worker.run(acquire, stop))
        await until(lambda: worker.state.generation == 1)
        await late.commit()
        committed = True
        # No NOTIFY listener exists: the next periodic scan finds the late ID.
        await until(lambda: worker.state.generation == 2)
        assert await reader.fetchval("SELECT count(*) FROM runtime_consumer_receipts") == 2
        assert len(await reader.fetch("SELECT * FROM runtime_consumer_receipts")) == 2
    finally:
        stop.set()
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if not committed:
            await late.rollback()
    restarted = RuntimeCacheWorker(poll_seconds=0.01)
    stop = asyncio.Event()
    task = asyncio.create_task(restarted.run(acquire, stop))
    try:
        await until(lambda: restarted.state.last_success_monotonic is not None)
        assert restarted.state.generation == 2
        assert restarted.state.status == "idle"
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=1)
    print("PG worker proof: late lower ID caught by polling; two receipts; restart keeps generation2")


async def test_receipt_failure_reports_unavailable_then_recovers(cache_db, monkeypatch):  # noqa: F811
    writer, reader = cache_db
    monkeypatch.setenv("RUNTIME_HTTP_CACHE_WORKER_ENABLED", "true")
    await writer.execute("INSERT INTO rounds VALUES(42,1,7)")
    await event(writer)
    await writer.execute("ALTER TABLE runtime_consumer_receipts ADD CONSTRAINT reject_worker CHECK(false)")
    worker = RuntimeCacheWorker(poll_seconds=0.01)
    stop = asyncio.Event()

    @asynccontextmanager
    async def acquire():
        yield writer

    task = asyncio.create_task(worker.run(acquire, stop))
    try:
        await until(lambda: worker.state.status == "unavailable")
        assert worker.state.last_success_monotonic is None
        assert worker.state.error_type == "CheckViolationError"
        assert await reader.fetchval("SELECT count(*) FROM runtime_consumer_receipts") == 0
        await reader.execute("ALTER TABLE runtime_consumer_receipts DROP CONSTRAINT reject_worker")
        await until(lambda: worker.state.generation == 1)
        assert worker.state.error_type is None
        assert await reader.fetchval("SELECT count(*) FROM runtime_consumer_receipts") == 1
    finally:
        stop.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_closed_connection_is_reacquired(cache_db, monkeypatch):  # noqa: F811
    writer, reader = cache_db
    monkeypatch.setenv("RUNTIME_HTTP_CACHE_WORKER_ENABLED", "true")
    await writer.execute("INSERT INTO rounds VALUES(42,1,7)")
    await event(writer)
    closed = await asyncpg.connect(**connection_options())
    await closed.close()
    worker = RuntimeCacheWorker(poll_seconds=0.01)
    stop = asyncio.Event()
    calls = []

    @asynccontextmanager
    async def acquire():
        calls.append(worker.state)
        yield closed if len(calls) == 1 else writer

    task = asyncio.create_task(worker.run(acquire, stop))
    try:
        await until(lambda: worker.state.generation == 1)
        assert calls[1].status == "unavailable"
        assert calls[1].error_type == "ConnectionError"
        assert await reader.fetchval("SELECT count(*) FROM runtime_consumer_receipts") == 1
    finally:
        stop.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
