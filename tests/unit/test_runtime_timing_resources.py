"""Session/cleanup guards without claiming native SQL or network execution."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from shared import runtime_timing_resources as resources
from shared.runtime_import_pool import ImportDatabaseConfig, TcpImportDatabaseConfig


def database():
    return ImportDatabaseConfig('/tmp/fixture-socket', 'fixture_db', 'fixture_role', '')


def connections(monkeypatch, *, changed=None, close_error=None):
    identity = ('fixture_db', 'public', 'fixture_role', False)
    writer = SimpleNamespace(fetchrow=AsyncMock(return_value=identity),
        fetchval=AsyncMock(return_value='off'), get_server_pid=lambda: 10, is_in_transaction=lambda: False)
    observer = SimpleNamespace(fetchrow=AsyncMock(return_value=changed or identity),
        fetchval=AsyncMock(return_value='on'), get_server_pid=lambda: 11, is_in_transaction=lambda: False,
        close=AsyncMock(side_effect=close_error), terminate=Mock())
    sessions = []

    @asynccontextmanager
    async def acquire():
        yield writer

    @asynccontextmanager
    async def session(config, **options):
        assert options['journal_enabled'] is True and options['defer_team_assignment'] is True
        manager = SimpleNamespace(pool=SimpleNamespace(acquire=acquire))
        try:
            yield manager
        finally:
            manager.pool = None
            sessions.append('closed')

    monkeypatch.setattr(resources, 'open_import_session', session)
    connect = AsyncMock(return_value=observer)
    monkeypatch.setattr(resources.asyncpg, 'connect', connect)
    return writer, observer, sessions, connect


async def test_observer_is_separately_owned_readonly_and_adapter_cannot_reconnect(monkeypatch):
    _, observer, sessions, connect = connections(monkeypatch)
    async with resources.timing_import_resources(database()) as (manager, adapter, independent):
        assert independent is observer and adapter.pool is manager.pool
        with pytest.raises(RuntimeError, match='Only the enclosing'):
            await adapter.close()
    assert adapter.pool is None and manager.pool is None and sessions == ['closed']
    observer.close.assert_awaited_once_with(timeout=5.0)
    observer.terminate.assert_not_called()
    assert connect.await_args.kwargs['server_settings']['default_transaction_read_only'] == 'on'
    assert connect.await_args.kwargs['target_session_attrs'] == 'primary'
    with pytest.raises(RuntimeError, match='enclosing owned import session'):
        await adapter.connect()


@pytest.mark.parametrize('changed', [('wrong_db', 'public', 'fixture_role', False),
                                  ('fixture_db', 'wrong_schema', 'fixture_role', False),
                                  ('fixture_db', 'public', 'wrong_role', False),
                                  ('fixture_db', 'public', 'fixture_role', True)])
async def test_mismatched_observer_never_yields(monkeypatch, changed):
    _, observer, sessions, _ = connections(monkeypatch, changed=changed)
    with pytest.raises(RuntimeError, match='do not agree'):
        async with resources.timing_import_resources(database()):
            pytest.fail('Mismatched resources admitted')
    observer.close.assert_awaited_once()
    assert sessions == ['closed']


@pytest.mark.parametrize('failure', [RuntimeError('primary stage failure'), asyncio.CancelledError()])
async def test_primary_failure_survives_observer_close_failure(monkeypatch, failure):
    close_error = OSError('observer close failure')
    _, observer, sessions, _ = connections(monkeypatch, close_error=close_error)
    with pytest.raises(type(failure)) as caught:
        async with resources.timing_import_resources(database()) as (_, adapter, _):
            raise failure
    assert caught.value is failure and caught.value.__cause__ is close_error
    assert adapter.pool is None and sessions == ['closed']
    observer.terminate.assert_called_once_with()


async def test_initial_observer_connection_failure_still_closes_import_session(monkeypatch):
    _, _, sessions, connect = connections(monkeypatch)
    connect.side_effect = OSError('synthetic connection failure')
    with pytest.raises(OSError):
        async with resources.timing_import_resources(database()):
            pytest.fail('Missing observer admitted')
    assert sessions == ['closed']


async def test_unsupported_ipv6_is_explicitly_refused_before_session(monkeypatch):
    session = Mock(side_effect=AssertionError('Unexpected session creation'))
    monkeypatch.setattr(resources, 'open_import_session', session)
    target = TcpImportDatabaseConfig('::1', 'fixture_db', 'fixture_role', 'synthetic-only')
    with pytest.raises(ValueError, match='IPv4'):
        async with resources.timing_import_resources(target):
            pytest.fail('Unsupported adapter target admitted')
    session.assert_not_called()
