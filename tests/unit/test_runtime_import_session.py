"""Owned session lifecycle with protocol pools; no SQL or network claims."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from bot.runtime_import_session import open_import_session


def config():
    return SimpleNamespace(database_type='postgresql')


def pool():
    return SimpleNamespace(close=AsyncMock(), terminate=Mock())


@pytest.mark.parametrize('enabled', [False, True])
async def test_session_owns_pool_and_explicit_journal_flag(monkeypatch, enabled):
    monkeypatch.setenv('EVENT_STREAM_ENABLED', str(not enabled).lower())
    owned = pool()
    factory = AsyncMock(return_value=owned)
    supplied = config()
    async with open_import_session(supplied, pool_factory=factory, journal_enabled=enabled) as manager:
        assert manager.config is supplied and manager.pool is owned
        assert manager.event_stream_enabled is enabled
        owned.close.assert_not_awaited()
    assert manager.pool is None
    factory.assert_awaited_once_with()
    owned.close.assert_awaited_once_with()
    owned.terminate.assert_not_called()


@pytest.mark.parametrize('failure', [RuntimeError('fixture import failure'), asyncio.CancelledError()])
async def test_body_failure_propagates_after_close(failure):
    owned = pool()
    with pytest.raises(type(failure)) as caught:
        async with open_import_session(config(), pool_factory=AsyncMock(return_value=owned),
                                       journal_enabled=True) as manager:
            raise failure
    assert caught.value is failure and manager.pool is None
    owned.close.assert_awaited_once_with()
    owned.terminate.assert_not_called()


async def test_real_task_cancellation_closes_pool():
    owned = pool()
    entered = asyncio.Event()

    async def run():
        async with open_import_session(config(), pool_factory=AsyncMock(return_value=owned),
                                       journal_enabled=True):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(run())
    try:
        await asyncio.wait_for(entered.wait(), 2)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    owned.close.assert_awaited_once_with()
    owned.terminate.assert_not_called()


@pytest.mark.parametrize('mode', ['error', 'timeout', 'cancel'])
async def test_unsuccessful_close_terminates_and_propagates(mode):
    reached = asyncio.Event()

    async def close():
        reached.set()
        if mode == 'error':
            raise OSError('fixture close failure')
        if mode == 'cancel':
            raise asyncio.CancelledError()
        await asyncio.Event().wait()

    owned = SimpleNamespace(close=close, terminate=Mock())
    error = {'error': OSError, 'timeout': TimeoutError, 'cancel': asyncio.CancelledError}[mode]
    with pytest.raises(error):
        async with open_import_session(config(), pool_factory=AsyncMock(return_value=owned),
                                       journal_enabled=True, close_timeout=0.02) as manager:
            assert manager.pool is owned
    assert reached.is_set() and manager.pool is None
    owned.terminate.assert_called_once_with()


@pytest.mark.parametrize('options', [
    {'config': None}, {'journal_enabled': 'true'}, {'journal_enabled': 1},
    *[{'close_timeout': value} for value in (True, None, '5', 0, -1, 31, float('nan'), float('inf'))],
])
async def test_bad_options_refused_before_pool_creation(options):
    factory = AsyncMock()
    arguments = dict(config=config(), pool_factory=factory, journal_enabled=True)
    arguments.update(options)
    with pytest.raises(ValueError):
        async with open_import_session(**arguments):
            pytest.fail('Invalid options yielded a manager')
    factory.assert_not_awaited()


async def test_factory_failure_is_not_hidden():
    failure = OSError('fixture connection failure')
    with pytest.raises(OSError) as caught:
        async with open_import_session(config(), pool_factory=AsyncMock(side_effect=failure),
                                       journal_enabled=True):
            pytest.fail('Failed factory yielded a manager')
    assert caught.value is failure


async def test_external_cancellation_during_close_terminates_pool():
    closing = asyncio.Event()
    close_exited = asyncio.Event()

    async def close():
        closing.set()
        try:
            await asyncio.Event().wait()
        finally:
            close_exited.set()

    owned = SimpleNamespace(close=close, terminate=Mock())
    managers = []

    async def run():
        async with open_import_session(config(), pool_factory=AsyncMock(return_value=owned),
                                       journal_enabled=True) as manager:
            managers.append(manager)

    task = asyncio.create_task(run())
    try:
        await asyncio.wait_for(closing.wait(), 2)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert close_exited.is_set() and managers[0].pool is None
    owned.terminate.assert_called_once_with()


@pytest.mark.parametrize('deferred', [False, True])
async def test_explicit_team_policy_reaches_manager(deferred, monkeypatch):
    monkeypatch.setenv('RUNTIME_TEAM_EVENTS_ENABLED', 'true')
    owned = pool()
    async with open_import_session(config(), pool_factory=AsyncMock(return_value=owned),
                                   journal_enabled=True, defer_team_assignment=deferred) as manager:
        assert manager.defer_team_assignment is deferred
    owned.close.assert_awaited_once()


@pytest.mark.parametrize('deferred,journal', [(1, True), ('true', True), (None, True), (True, False)])
async def test_invalid_team_policy_never_creates_pool(deferred, journal):
    factory = AsyncMock()
    with pytest.raises(ValueError):
        async with open_import_session(config(), pool_factory=factory, journal_enabled=journal,
                                       defer_team_assignment=deferred):
            pytest.fail('Invalid policy yielded')
    factory.assert_not_awaited()


@pytest.mark.parametrize('body_failure', [ValueError('import failed'), asyncio.CancelledError()])
@pytest.mark.parametrize('close_mode', ['error', 'timeout', 'cancel'])
async def test_import_failure_stays_primary_when_close_also_fails(body_failure, close_mode):
    async def close():
        if close_mode == 'error':
            raise OSError('cleanup failed')
        if close_mode == 'cancel':
            raise asyncio.CancelledError()
        await asyncio.Event().wait()

    owned = SimpleNamespace(close=close, terminate=Mock())
    with pytest.raises(type(body_failure)) as caught:
        async with open_import_session(config(), pool_factory=AsyncMock(return_value=owned),
                                       journal_enabled=True, close_timeout=0.01) as manager:
            raise body_failure
    assert caught.value is body_failure
    expected_cause = {'error': OSError, 'timeout': TimeoutError, 'cancel': asyncio.CancelledError}[close_mode]
    assert isinstance(caught.value.__cause__, expected_cause)
    assert manager.pool is None
    owned.terminate.assert_called_once_with()
