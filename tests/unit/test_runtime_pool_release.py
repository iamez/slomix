"""Only the known closed-proxy release race is retryable, never arbitrary internals."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asyncpg
import pytest

from shared import runtime_cache_worker, runtime_team_worker

MESSAGE = 'PoolConnectionHolder.release() called on a free connection holder'


def released_proxy():
    proxy = asyncpg.pool.PoolConnectionProxy.__new__(asyncpg.pool.PoolConnectionProxy)
    proxy._con = None  # noqa: SLF001 - real released-proxy state, no connection or fixture
    proxy._holder = None  # noqa: SLF001
    return proxy


def setup_actor(monkeypatch, actor, consume):
    monkeypatch.setenv('EVENT_STREAM_ENABLED', 'true')
    if actor == 'cache':
        monkeypatch.setenv('RUNTIME_HTTP_CACHE_EVENTS_ENABLED', 'true')
        monkeypatch.setenv('RUNTIME_HTTP_CACHE_WORKER_ENABLED', 'true')
        monkeypatch.setattr(runtime_cache_worker, 'consume_http_cache_events', consume)
        return runtime_cache_worker.RuntimeCacheWorker(poll_seconds=0.001)
    monkeypatch.setenv('RUNTIME_TEAM_EVENTS_ENABLED', 'true')
    monkeypatch.setenv('RUNTIME_TEAM_WORKER_ENABLED', 'true')
    monkeypatch.setattr(runtime_team_worker, 'consume_team_page', consume)
    return runtime_team_worker.RuntimeTeamWorker(poll_seconds=0.001)


def result():
    return SimpleNamespace(status='idle', processed=0, unsupported_pending=0,
                           generation=1, items=(), inspected=0, next_hint=None)


@pytest.mark.parametrize('actor', ['cache', 'team'])
async def test_closed_proxy_release_race_retries_without_publishing_success(monkeypatch, actor):
    stop = asyncio.Event()
    consume = AsyncMock(return_value=result())
    worker = setup_actor(monkeypatch, actor, consume)
    attempts = 0

    @asynccontextmanager
    async def acquire():
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            assert worker.state.status == 'unavailable'
            assert worker.state.last_success_monotonic is None
        yield released_proxy()
        if attempts == 1:
            raise asyncpg.InternalClientError(MESSAGE)
        stop.set()

    await asyncio.wait_for(worker.run(acquire, stop), 1)
    assert attempts == consume.await_count == 2
    assert worker.state.status == 'stopped'
    assert worker.state.error_type is None
    assert worker.state.last_success_monotonic is not None


@pytest.mark.parametrize('actor', ['cache', 'team'])
@pytest.mark.parametrize('shape', ['unknown_message', 'non_proxy', 'acquire_error', 'live_proxy'])
async def test_other_internal_errors_remain_fatal(monkeypatch, actor, shape):
    error = asyncpg.InternalClientError('other invariant' if shape == 'unknown_message' else MESSAGE)
    if shape == 'live_proxy':
        monkeypatch.setattr(asyncpg.pool.PoolConnectionProxy, 'is_closed', lambda self: False)
    consume = AsyncMock(return_value=result())
    worker = setup_actor(monkeypatch, actor, consume)

    @asynccontextmanager
    async def acquire():
        if shape == 'acquire_error':
            raise error
        yield object() if shape == 'non_proxy' else released_proxy()
        raise error

    with pytest.raises(asyncpg.InternalClientError) as caught:
        await asyncio.wait_for(worker.run(acquire, asyncio.Event()), 1)
    assert caught.value is error
    assert worker.state.status == 'failed'


@pytest.mark.parametrize('actor', ['cache', 'team'])
async def test_release_race_must_not_swallow_pending_cancellation(monkeypatch, actor):
    entered = asyncio.Event()
    stop = asyncio.Event()

    async def consume(*_args, **_kwargs):
        entered.set()
        await asyncio.Event().wait()

    worker = setup_actor(monkeypatch, actor, consume)
    attempts = 0

    @asynccontextmanager
    async def acquire():
        nonlocal attempts
        attempts += 1
        try:
            yield released_proxy()
        finally:
            raise asyncpg.InternalClientError(MESSAGE)

    task = asyncio.create_task(worker.run(acquire, stop))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        await asyncio.sleep(0.02)
        assert task.done(), 'Cancellation was replaced by a release retry'
        with pytest.raises(asyncio.CancelledError):
            await task
        assert attempts == 1
    finally:
        stop.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
