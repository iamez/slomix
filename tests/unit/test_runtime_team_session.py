"""Real async lifecycle with protocol pools; no database or transport claims."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from shared import runtime_team_session as session
from shared import runtime_team_worker as lifecycle
from shared.runtime_import_pool import ImportDatabaseConfig
from shared.runtime_team_worker import RuntimeTeamWorker

FLAGS = ('EVENT_STREAM_ENABLED', 'RUNTIME_TEAM_EVENTS_ENABLED', 'RUNTIME_TEAM_WORKER_ENABLED')


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    for flag in FLAGS:
        monkeypatch.setenv(flag, 'true')


def config():
    return ImportDatabaseConfig('/tmp/explicit-test-socket', 'fixture', 'fixture', '',
                                application_name='slomix-team-fixture')


def pool():
    return SimpleNamespace(acquire=Mock(), close=AsyncMock(), terminate=Mock())


@pytest.mark.parametrize('flag', FLAGS)
@pytest.mark.parametrize('value', [None, 'false'])
async def test_disabled_never_creates_resources(monkeypatch, flag, value):
    if value is None:
        monkeypatch.delenv(flag)
    else:
        monkeypatch.setenv(flag, value)
    factory = AsyncMock()
    monkeypatch.setattr(session, 'create_import_pool', factory)
    result = await session.run_team_worker(None, None, None)
    assert result.status == 'disabled'
    factory.assert_not_awaited()


async def test_stopped_before_start_does_not_create_pool_or_change_worker(monkeypatch):
    stop = asyncio.Event()
    stop.set()
    worker = RuntimeTeamWorker()
    previous = worker.state
    factory = AsyncMock()
    monkeypatch.setattr(session, 'create_import_pool', factory)
    assert (await session.run_team_worker(None, worker, stop)).status == 'stopped'
    assert worker.state is previous
    factory.assert_not_awaited()


@pytest.mark.parametrize('overrides', [
    {'database': None}, {'worker': None}, {'stop': None},
    *[{'close_timeout': value} for value in (True, None, '5', 0, -1, 31, float('nan'), float('inf'))],
])
async def test_invalid_active_configuration_precedes_factory(monkeypatch, overrides):
    factory = AsyncMock()
    monkeypatch.setattr(session, 'create_import_pool', factory)
    options = dict(database=config(), worker=RuntimeTeamWorker(), stop=asyncio.Event())
    options.update(overrides)
    with pytest.raises(ValueError):
        await session.run_team_worker(**options)
    factory.assert_not_awaited()


@pytest.mark.parametrize('failure', [OSError('factory'), asyncio.CancelledError()])
async def test_factory_failure_never_runs_worker(monkeypatch, failure):
    worker = RuntimeTeamWorker()
    worker.run = AsyncMock()
    monkeypatch.setattr(session, 'create_import_pool', AsyncMock(side_effect=failure))
    with pytest.raises(type(failure)) as caught:
        await session.run_team_worker(config(), worker, asyncio.Event())
    assert caught.value is failure
    worker.run.assert_not_awaited()


@pytest.mark.parametrize('failure', [RuntimeError('worker'), asyncio.CancelledError()])
async def test_worker_failure_closes_before_propagation(monkeypatch, failure):
    owned = pool()
    worker = RuntimeTeamWorker()
    worker.run = AsyncMock(side_effect=failure)
    monkeypatch.setattr(session, 'create_import_pool', AsyncMock(return_value=owned))
    with pytest.raises(type(failure)) as caught:
        await session.run_team_worker(config(), worker, asyncio.Event())
    assert caught.value is failure
    owned.close.assert_awaited_once_with()
    owned.terminate.assert_not_called()


@pytest.mark.parametrize('mode', ['error', 'timeout', 'cancel'])
async def test_failed_close_terminates_and_propagates(monkeypatch, mode):
    async def close():
        if mode == 'error':
            raise OSError('close')
        if mode == 'cancel':
            raise asyncio.CancelledError()
        await asyncio.Event().wait()

    owned = pool()
    owned.close = close
    worker = RuntimeTeamWorker()
    worker.run = AsyncMock()
    monkeypatch.setattr(session, 'create_import_pool', AsyncMock(return_value=owned))
    with pytest.raises({'error': OSError, 'timeout': TimeoutError, 'cancel': asyncio.CancelledError}[mode]):
        await session.run_team_worker(config(), worker, asyncio.Event(), close_timeout=0.01)
    owned.terminate.assert_called_once_with()


async def test_actual_worker_repeated_runs_release_before_close(monkeypatch):
    trace = []
    stop = asyncio.Event()
    connection = object()
    pools = []

    async def factory(database):
        assert database == config()
        index = len(pools)
        trace.append(('create', index))

        @asynccontextmanager
        async def acquire():
            trace.append(('acquire', index))
            try:
                yield connection
            finally:
                trace.append(('release', index))

        async def close():
            trace.append(('close', index))

        owned = SimpleNamespace(acquire=acquire, close=close, terminate=Mock())
        pools.append(owned)
        return owned

    async def page(conn, **kwargs):
        assert conn is connection and kwargs['hint'] is None
        stop.set()
        return SimpleNamespace(status='page', next_hint=None, items=[])

    monkeypatch.setattr(session, 'create_import_pool', factory)
    monkeypatch.setattr(lifecycle, 'consume_team_page', page)
    worker = RuntimeTeamWorker()
    for _ in range(2):
        stop.clear()
        state = await session.run_team_worker(config(), worker, stop)
        assert state is worker.state and state.status == 'stopped'
        assert state.last_success_monotonic is not None
    assert trace == [(action, index) for index in range(2)
                     for action in ('create', 'acquire', 'release', 'close')]
    for owned in pools:
        owned.terminate.assert_not_called()
    print(f'actual worker lifecycle: {trace}')


async def test_actual_task_cancellation_releases_page_before_close(monkeypatch):
    entered = asyncio.Event()
    trace = []

    @asynccontextmanager
    async def acquire():
        try:
            yield object()
        finally:
            trace.append('release')

    async def page(*args, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    owned = pool()
    owned.acquire = acquire
    owned.close = AsyncMock(side_effect=lambda: trace.append('close'))
    monkeypatch.setattr(session, 'create_import_pool', AsyncMock(return_value=owned))
    monkeypatch.setattr(lifecycle, 'consume_team_page', page)
    worker = RuntimeTeamWorker()
    task = asyncio.create_task(session.run_team_worker(config(), worker, asyncio.Event()))
    try:
        await asyncio.wait_for(entered.wait(), 2)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert trace == ['release', 'close']
    assert worker.state.status == 'stopped'
    owned.terminate.assert_not_called()
    print(f'actual cancellation lifecycle: {trace}')


async def test_external_cancellation_while_closing_terminates(monkeypatch):
    closing = asyncio.Event()
    exited = asyncio.Event()

    async def close():
        closing.set()
        try:
            await asyncio.Event().wait()
        finally:
            exited.set()

    owned = pool()
    owned.close = close
    worker = RuntimeTeamWorker()
    worker.run = AsyncMock()
    monkeypatch.setattr(session, 'create_import_pool', AsyncMock(return_value=owned))
    task = asyncio.create_task(session.run_team_worker(config(), worker, asyncio.Event()))
    try:
        await asyncio.wait_for(closing.wait(), 2)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert exited.is_set()
    owned.terminate.assert_called_once_with()


@pytest.mark.parametrize('failure', [RuntimeError('worker'), asyncio.CancelledError()])
async def test_worker_error_remains_primary_when_close_also_fails(monkeypatch, failure):
    owned = pool()
    close_error = OSError('close')
    owned.close.side_effect = close_error
    worker = RuntimeTeamWorker()
    worker.run = AsyncMock(side_effect=failure)
    monkeypatch.setattr(session, 'create_import_pool', AsyncMock(return_value=owned))
    with pytest.raises(type(failure)) as caught:
        await session.run_team_worker(config(), worker, asyncio.Event())
    assert caught.value is failure and failure.__cause__ is close_error
    owned.terminate.assert_called_once_with()


async def test_disabled_return_never_reuses_old_success_state(monkeypatch):
    worker = RuntimeTeamWorker()
    worker.state = lifecycle.TeamWorkerState(status='stopped', last_success_monotonic=123)
    monkeypatch.setenv('RUNTIME_TEAM_WORKER_ENABLED', 'false')
    returned = await session.run_team_worker(config(), worker, asyncio.Event())
    assert returned.status == 'disabled' and returned.last_success_monotonic is None
    assert worker.state.last_success_monotonic == 123  # Caller-owned history, not this run's result.


@pytest.mark.parametrize('mode', ['disabled', 'stopped'])
async def test_policy_change_during_creation_closes_without_acquiring(monkeypatch, mode):
    owned = pool()
    stop = asyncio.Event()

    async def factory(database):
        if mode == 'disabled':
            monkeypatch.setenv('RUNTIME_TEAM_WORKER_ENABLED', 'false')
        else:
            stop.set()
        return owned

    monkeypatch.setattr(session, 'create_import_pool', factory)
    result = await session.run_team_worker(config(), RuntimeTeamWorker(), stop)
    assert result.status == mode and result.last_success_monotonic is None
    owned.acquire.assert_not_called()
    owned.close.assert_awaited_once_with()
    owned.terminate.assert_not_called()
