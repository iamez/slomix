"""Lifecycle, retry and cancellation proofs for the caller-owned consumer."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asyncpg
import pytest

from shared import runtime_cache_worker as module
from shared.runtime_cache_consumer import CacheConsumption

FLAGS = ("EVENT_STREAM_ENABLED", "RUNTIME_HTTP_CACHE_EVENTS_ENABLED", "RUNTIME_HTTP_CACHE_WORKER_ENABLED")


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    for flag in FLAGS:
        monkeypatch.setenv(flag, "true")


@asynccontextmanager
async def connection():
    yield object()


@pytest.mark.parametrize("flag", FLAGS)
async def test_off_no_connection(monkeypatch, flag):
    monkeypatch.delenv(flag)
    acquire = AsyncMock(side_effect=AssertionError("must not acquire"))
    worker = module.RuntimeCacheWorker()
    await worker.run(acquire, asyncio.Event())
    assert worker.state.status == "disabled"
    acquire.assert_not_called()


@pytest.mark.parametrize("name,value", [("batch_size", True), ("batch_size", 0),
                                      ("poll_seconds", 0), ("attempt_timeout", float("inf")),
                                      ("poll_seconds", float("nan"))])
def test_invalid_config(name, value):
    with pytest.raises(ValueError):
        module.RuntimeCacheWorker(**{name: value})


async def test_poll_without_notifications_recovers_from_db_failure(monkeypatch):
    stop = asyncio.Event()
    worker = module.RuntimeCacheWorker(poll_seconds=0.001)
    calls = []

    async def consume(conn, **kwargs):
        calls.append(worker.state)
        if len(calls) == 1:
            raise OSError("private error text")
        if len(calls) == 3:
            stop.set()
        return CacheConsumption("idle", 0, 7, 0)

    monkeypatch.setattr(module, "consume_http_cache_events", consume)
    await asyncio.wait_for(worker.run(connection, stop), timeout=1)
    assert len(calls) == 3
    assert calls[1].status == "unavailable"
    assert calls[1].last_success_monotonic is None
    assert worker.state.status == "stopped"
    assert worker.state.generation == 7
    assert worker.state.error_type is None


async def test_full_batches_yield_and_release_each_connection(monkeypatch):
    stop = asyncio.Event()
    worker = module.RuntimeCacheWorker(batch_size=1, poll_seconds=60)
    counts = {"entered": 0, "released": 0}

    @asynccontextmanager
    async def acquire():
        counts["entered"] += 1
        try:
            yield object()
        finally:
            counts["released"] += 1

    async def consume(conn, **kwargs):
        if counts["entered"] == 3:
            stop.set()
        return CacheConsumption("advanced", 1, counts["entered"], 2)

    monkeypatch.setattr(module, "consume_http_cache_events", consume)
    await asyncio.wait_for(worker.run(acquire, stop), timeout=1)
    assert counts == {"entered": 3, "released": 3}
    assert worker.state.unsupported_pending == 2
    assert worker.state.generation == 3


async def test_idle_stop_interrupts_long_wait(monkeypatch):
    stop, consumed = asyncio.Event(), asyncio.Event()
    worker = module.RuntimeCacheWorker(poll_seconds=3600)

    async def consume(conn, **kwargs):
        consumed.set()
        return CacheConsumption("idle", 0, 0, 0)

    monkeypatch.setattr(module, "consume_http_cache_events", consume)
    task = asyncio.create_task(worker.run(connection, stop))
    try:
        await asyncio.wait_for(consumed.wait(), timeout=1)
        stop.set()
        await asyncio.wait_for(task, timeout=1)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_cancel_releases_active_connection_and_refuses_double_run(monkeypatch):
    active, released = asyncio.Event(), asyncio.Event()
    worker = module.RuntimeCacheWorker()

    @asynccontextmanager
    async def acquire():
        try:
            yield object()
        finally:
            released.set()

    async def consume(conn, **kwargs):
        active.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(module, "consume_http_cache_events", consume)
    task = asyncio.create_task(worker.run(acquire, asyncio.Event()))
    try:
        await asyncio.wait_for(active.wait(), timeout=1)
        with pytest.raises(RuntimeError, match="already running"):
            await worker.run(acquire, asyncio.Event())
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert released.is_set()
    assert worker.state.status == "stopped"
    assert worker.state.last_success_monotonic is None


async def test_programming_error_is_visible_and_propagates(monkeypatch):
    monkeypatch.setattr(module, "consume_http_cache_events", AsyncMock(side_effect=ValueError("broken")))
    worker = module.RuntimeCacheWorker()
    with pytest.raises(ValueError, match="broken"):
        await worker.run(connection, asyncio.Event())
    assert worker.state.status == "failed"
    assert worker.state.error_type == "ValueError"
    assert worker.state.last_success_monotonic is None


async def test_attempt_timeout_releases_then_retries(monkeypatch):
    stop = asyncio.Event()
    worker = module.RuntimeCacheWorker(poll_seconds=0.001, attempt_timeout=0.01)
    calls = {"entered": 0, "released": 0}

    @asynccontextmanager
    async def acquire():
        calls["entered"] += 1
        try:
            yield object()
        finally:
            calls["released"] += 1

    async def consume(conn, **kwargs):
        if calls["entered"] == 1:
            await asyncio.Event().wait()
        assert worker.state.status == "unavailable"
        assert worker.state.error_type == "TimeoutError"
        assert calls["released"] == 1
        stop.set()
        return CacheConsumption("idle", 0, 3, 0)

    monkeypatch.setattr(module, "consume_http_cache_events", consume)
    await asyncio.wait_for(worker.run(acquire, stop), timeout=1)
    assert calls == {"entered": 2, "released": 2}
    assert worker.state.generation == 3


async def test_interface_misuse_on_open_connection_is_not_retried(monkeypatch):
    consume = AsyncMock(side_effect=asyncpg.InterfaceError("operation already in progress"))
    monkeypatch.setattr(module, "consume_http_cache_events", consume)

    @asynccontextmanager
    async def acquire():
        yield SimpleNamespace(is_closed=lambda: False)

    worker = module.RuntimeCacheWorker(poll_seconds=0.001)
    with pytest.raises(asyncpg.InterfaceError, match="already in progress"):
        await asyncio.wait_for(worker.run(acquire, asyncio.Event()), timeout=1)
    consume.assert_awaited_once()
    assert worker.state.status == "failed"


async def test_cancel_during_acquisition_cleans_up_without_consuming(monkeypatch):
    entered, cleaned = asyncio.Event(), asyncio.Event()
    consume = AsyncMock()
    monkeypatch.setattr(module, "consume_http_cache_events", consume)

    @asynccontextmanager
    async def acquire():
        try:
            entered.set()
            await asyncio.Event().wait()
            yield object()
        finally:
            cleaned.set()

    worker = module.RuntimeCacheWorker()
    task = asyncio.create_task(worker.run(acquire, asyncio.Event()))
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert cleaned.is_set()
    consume.assert_not_awaited()
    assert worker.state.last_success_monotonic is None


async def test_unsupported_pending_stays_visible_after_successful_batch(monkeypatch):
    consume = AsyncMock(return_value=CacheConsumption("advanced", 1, 9, 2))
    monkeypatch.setattr(module, "consume_http_cache_events", consume)
    worker = module.RuntimeCacheWorker(poll_seconds=60)
    stop = asyncio.Event()
    task = asyncio.create_task(worker.run(connection, stop))
    try:
        async with asyncio.timeout(1):
            while worker.state.last_success_monotonic is None:
                await asyncio.sleep(0)
        assert worker.state.status == "unsupported"
        assert worker.state.unsupported_pending == 2
        assert worker.state.generation == 9
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=1)
