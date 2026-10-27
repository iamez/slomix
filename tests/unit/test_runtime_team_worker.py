"""Caller-owned polling lifecycle; no DB/service startup in these tests."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock

import asyncpg
import pytest

from shared import runtime_team_worker as module
from shared.runtime_team_batch import TeamBatch, TeamBatchItem
from shared.runtime_team_consumer import TeamConsumption
from shared.runtime_team_discovery import TeamScanHint
from shared.team_write_guard import TeamWriteBusy

FLAGS = ('EVENT_STREAM_ENABLED', 'RUNTIME_TEAM_EVENTS_ENABLED', 'RUNTIME_TEAM_WORKER_ENABLED')


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    for flag in FLAGS:
        monkeypatch.setenv(flag, 'true')


@asynccontextmanager
async def connection():
    yield Mock(is_closed=lambda: False)


def page(hint=None, status='pending'):
    return TeamBatch('page', (TeamBatchItem(1, TeamConsumption(status)),), hint)


@pytest.mark.parametrize('flag', FLAGS)
async def test_disabled_no_acquire(monkeypatch, flag):
    monkeypatch.delenv(flag)
    factory = Mock(side_effect=AssertionError('unexpected acquire'))
    worker = module.RuntimeTeamWorker()
    await worker.run(factory, asyncio.Event())
    assert worker.state.status == 'disabled'
    factory.assert_not_called()


@pytest.mark.parametrize('name,value', [('batch_size', True), ('batch_size', 1001),
                                      ('poll_seconds', False), ('poll_seconds', float('nan')),
                                      ('attempt_timeout', float('inf')), ('attempt_timeout', 0)])
def test_bad_config(name, value):
    with pytest.raises(ValueError):
        module.RuntimeTeamWorker(**{name: value})


async def test_finite_pages_release_then_wrap_wait(monkeypatch):
    worker = module.RuntimeTeamWorker(batch_size=1)
    stop = asyncio.Event()
    hint = TeamScanHint(1, 2)
    calls, lifecycle, waits = [], [], []

    @asynccontextmanager
    async def factory():
        lifecycle.append('enter')
        yield object()
        # Scheduling state is not advanced while release is in progress.
        assert worker.state.next_hint == (None if len(calls) == 1 else hint)
        lifecycle.append('exit')

    async def consume(conn, **kwargs):
        calls.append(kwargs['hint'])
        return page(hint if len(calls) == 1 else None)

    async def wait(event):
        waits.append(worker.state)
        event.set()

    monkeypatch.setattr(module, 'consume_team_page', consume)
    monkeypatch.setattr(worker, '_wait', wait)
    await asyncio.wait_for(worker.run(factory, stop), 1)
    assert calls == [None, hint]
    assert lifecycle == ['enter', 'exit', 'enter', 'exit']
    assert len(waits) == 1 and waits[0].status == 'pending'
    assert worker.state.pending == 1 and worker.state.inspected == 1
    assert worker.state.status == 'stopped'


@pytest.mark.parametrize('failure', [OSError('private-data'), TeamWriteBusy('private-data'),
    asyncpg.ConnectionDoesNotExistError('private-data'), asyncpg.SerializationError('private-data'),
    asyncpg.DeadlockDetectedError('private-data'), asyncpg.CannotConnectNowError('private-data')])
async def test_transient_retry_keeps_hint_and_redacts(monkeypatch, caplog, failure):
    stop = asyncio.Event()
    worker = module.RuntimeTeamWorker(poll_seconds=0.001)
    hint = TeamScanHint(1, 3)
    calls = []

    async def consume(conn, **kwargs):
        calls.append(kwargs['hint'])
        if len(calls) == 1:
            return page(hint)
        if len(calls) == 2:
            raise failure
        assert worker.state.status == 'unavailable'
        stop.set()
        return page()

    monkeypatch.setattr(module, 'consume_team_page', consume)
    await asyncio.wait_for(worker.run(connection, stop), 1)
    assert calls == [None, hint, hint]
    assert 'private-data' not in caplog.text
    assert type(failure).__name__ in caplog.text


@pytest.mark.parametrize('phase', ['acquire', 'release'])
async def test_resource_failure_retries_without_hint_publication(monkeypatch, phase):
    stop = asyncio.Event()
    worker = module.RuntimeTeamWorker(poll_seconds=0.001)
    attempts, hints = [], []

    @asynccontextmanager
    async def factory():
        attempts.append(1)
        if len(attempts) == 1 and phase == 'acquire':
            raise OSError('acquire')
        yield object()
        if len(attempts) == 1:
            raise OSError('release after possible commit')
        stop.set()

    async def consume(conn, **kwargs):
        hints.append(kwargs['hint'])
        return page(TeamScanHint(1, 2))

    monkeypatch.setattr(module, 'consume_team_page', consume)
    await asyncio.wait_for(worker.run(factory, stop), 1)
    assert hints == ([None] if phase == 'acquire' else [None, None])
    assert len(attempts) == 2


@pytest.mark.parametrize('phase', ['acquire', 'consume', 'release'])
async def test_attempt_deadline_covers_resource_lifetime(monkeypatch, phase):
    worker = module.RuntimeTeamWorker(attempt_timeout=0.01)
    stop = asyncio.Event()
    released = []

    @asynccontextmanager
    async def factory():
        try:
            if phase == 'acquire':
                await asyncio.Event().wait()
            yield object()
            if phase == 'release':
                await asyncio.Event().wait()
        finally:
            released.append(True)

    async def consume(conn, **kwargs):
        if phase == 'consume':
            await asyncio.Event().wait()
        return page(TeamScanHint(1, 2))

    async def wait(event):
        assert worker.state.status == 'unavailable'
        assert worker.state.error_type == 'TimeoutError'
        assert worker.state.next_hint is None
        event.set()

    monkeypatch.setattr(module, 'consume_team_page', consume)
    monkeypatch.setattr(worker, '_wait', wait)
    await asyncio.wait_for(worker.run(factory, stop), 1)
    assert released == [True]


@pytest.mark.parametrize('error', [ValueError('misuse'), asyncpg.UndefinedTableError('schema'),
                                  asyncpg.InterfaceError('misuse')])
async def test_permanent_failure_propagates(monkeypatch, error):
    worker = module.RuntimeTeamWorker()
    monkeypatch.setattr(module, 'consume_team_page', AsyncMock(side_effect=error))
    with pytest.raises(type(error)):
        await worker.run(connection, asyncio.Event())
    assert worker.state.status == 'failed'
    assert worker.state.error_type == type(error).__name__


async def test_closed_native_connection_retries(monkeypatch):
    worker = module.RuntimeTeamWorker()
    stop = asyncio.Event()

    @asynccontextmanager
    async def factory():
        yield Mock(is_closed=lambda: True)

    async def wait(event):
        assert worker.state.error_type == 'ConnectionError'
        event.set()

    monkeypatch.setattr(module, 'consume_team_page', AsyncMock(side_effect=asyncpg.InterfaceError('closed')))
    monkeypatch.setattr(worker, '_wait', wait)
    await worker.run(factory, stop)


async def test_cancel_releases_and_prevents_concurrent_run(monkeypatch):
    worker = module.RuntimeTeamWorker()
    entered = asyncio.Event()
    released = []

    @asynccontextmanager
    async def factory():
        try:
            yield object()
        finally:
            released.append(True)

    async def consume(*args, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(module, 'consume_team_page', consume)
    task = asyncio.create_task(worker.run(factory, asyncio.Event()))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        with pytest.raises(RuntimeError, match='already running'):
            await worker.run(factory, asyncio.Event())
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert released == [True]
        assert worker.state.status == 'stopped'
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_wrap_wait_is_interruptible_and_rerun_starts_fresh(monkeypatch):
    worker = module.RuntimeTeamWorker(poll_seconds=60)
    stop, waiting = asyncio.Event(), asyncio.Event()
    consume = AsyncMock(return_value=page())
    monkeypatch.setattr(module, 'consume_team_page', consume)
    original_wait = worker._wait  # noqa: SLF001 -- synchronize the real idle wait.

    async def wait(event):
        waiting.set()
        await original_wait(event)

    monkeypatch.setattr(worker, '_wait', wait)
    task = asyncio.create_task(worker.run(connection, stop))
    try:
        await asyncio.wait_for(waiting.wait(), 1)
        stop.set()
        await asyncio.wait_for(task, 1)
        # Old RAM progress is discarded even when the next run is already stopped.
        worker.state = module.TeamWorkerState(next_hint=TeamScanHint(1, 2))
        await worker.run(connection, stop)
        assert worker.state.next_hint is None
        assert consume.await_count == 1
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_worker_gate_closes_between_pages(monkeypatch):
    worker = module.RuntimeTeamWorker()
    calls = []

    async def consume(*args, **kwargs):
        calls.append(1)
        monkeypatch.setenv('RUNTIME_TEAM_WORKER_ENABLED', 'false')
        return page(TeamScanHint(1, 2))

    monkeypatch.setattr(module, 'consume_team_page', consume)
    await worker.run(connection, asyncio.Event())
    assert calls == [1] and worker.state.status == 'disabled'


async def test_disabled_page_retains_completed_prefix(monkeypatch):
    worker = module.RuntimeTeamWorker()
    result = TeamBatch('disabled', page(status='processed').items, None)
    monkeypatch.setattr(module, 'consume_team_page', AsyncMock(return_value=result))
    await worker.run(connection, asyncio.Event())
    assert worker.state.status == 'disabled' and worker.state.processed == 1


@pytest.mark.parametrize('recover', [False, True])
async def test_stop_retains_last_error_separately_from_prior_success(monkeypatch, recover):
    worker = module.RuntimeTeamWorker(poll_seconds=0.001)
    stop = asyncio.Event()
    calls = 0

    async def consume(conn, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            stop.set()
        if (calls == 1) == recover:
            raise ConnectionError('temporary fixture failure')
        return page(status='processed')

    monkeypatch.setattr(module, 'consume_team_page', consume)
    await worker.run(connection, stop)
    assert calls == 2 and worker.state.status == 'stopped'
    assert worker.state.last_success_monotonic is not None
    assert worker.state.processed == 1
    assert worker.state.error_type == (None if recover else 'ConnectionError')
