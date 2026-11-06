"""Closed native asyncpg connections retry; unrelated programming errors stay fatal."""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import asyncpg
import pytest

from shared import runtime_cache_worker as cache
from shared import runtime_team_worker as team
from shared.runtime_cache_consumer import CacheConsumption
from shared.runtime_team_batch import TeamBatch


class NativeConnectionState(asyncpg.Connection):
    """Driver methods over a closed/open state, without allocating a socket."""

    def __init__(self, *, closed):
        self._protocol = None if closed else SimpleNamespace(is_connected=lambda: True)  # noqa: SLF001 -- native driver-state fixture.
        self._aborted = closed  # noqa: SLF001 -- same state as native terminate().
        self._proxy = None  # noqa: SLF001 -- permit the real pool proxy to attach.

    def __del__(self):
        pass  # This state fixture owns no transport or other driver resources.


def setup(monkeypatch, kind):
    for flag in ('EVENT_STREAM_ENABLED', 'RUNTIME_HTTP_CACHE_EVENTS_ENABLED',
                 'RUNTIME_HTTP_CACHE_WORKER_ENABLED', 'RUNTIME_TEAM_EVENTS_ENABLED',
                 'RUNTIME_TEAM_WORKER_ENABLED'):
        monkeypatch.setenv(flag, 'true')
    module = cache if kind == 'cache' else team
    worker = (cache.RuntimeCacheWorker if kind == 'cache' else team.RuntimeTeamWorker)(poll_seconds=0.001)
    name = 'consume_http_cache_events' if kind == 'cache' else 'consume_team_page'
    return module, worker, name


@pytest.mark.parametrize('kind', ['cache', 'team'])
@pytest.mark.parametrize('transport', ['native', 'detached-proxy'])
async def test_closed_native_connection_releases_and_retries(monkeypatch, kind, transport):
    module, worker, name = setup(monkeypatch, kind)
    stop = asyncio.Event()
    closed = NativeConnectionState(closed=True)
    if transport == 'detached-proxy':
        closed = asyncpg.pool.PoolConnectionProxy(Mock(), closed)
        closed._detach()  # noqa: SLF001 -- model a released native pool lease.
    healthy = NativeConnectionState(closed=False)
    original = getattr(module, name)
    counts = {'acquired': 0, 'released': 0}

    @asynccontextmanager
    async def acquire():
        counts['acquired'] += 1
        if counts['acquired'] == 2:
            assert worker.state.status == 'unavailable'
            assert worker.state.error_type == 'ConnectionError'
        try:
            yield closed if counts['acquired'] == 1 else healthy
        finally:
            counts['released'] += 1

    async def consume(conn, **kwargs):
        if conn is closed:
            return await original(conn, **kwargs)
        stop.set()
        return CacheConsumption('idle', 0, 7, 0) if kind == 'cache' else TeamBatch('idle', (), None)

    monkeypatch.setattr(module, name, consume)
    await asyncio.wait_for(worker.run(acquire, stop), 1)
    assert counts == {'acquired': 2, 'released': 2}
    assert worker.state.status == 'stopped'
    assert worker.state.last_success_monotonic is not None
    assert worker.state.error_type is None


@pytest.mark.parametrize('kind', ['cache', 'team'])
async def test_attribute_error_on_usable_connection_is_not_retried(monkeypatch, kind):
    module, worker, name = setup(monkeypatch, kind)
    connection = NativeConnectionState(closed=False)
    released = []

    @asynccontextmanager
    async def acquire():
        try:
            yield connection
        finally:
            released.append(True)

    async def broken(*args, **kwargs):
        raise AttributeError('programming error on usable connection')

    monkeypatch.setattr(module, name, broken)
    with pytest.raises(AttributeError, match='programming error'):
        await worker.run(acquire, asyncio.Event())
    assert released == [True]
    assert worker.state.status == 'failed'
    assert worker.state.error_type == 'AttributeError'
