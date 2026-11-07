"""Retained proof ownership and explicit opt-in, without database writes."""

from unittest.mock import AsyncMock

import pytest

from tests.integration import test_runtime_proximity_full_schema_pg as module


@pytest.fixture
def recorded(monkeypatch):
    monkeypatch.setenv('RUNTIME_PROXIMITY_RETAIN_DB', 'true')
    options = dict(host='/private', port=5432, database='postgres', user='fixture_owner',
                   password='', ssl=False, timeout=5, command_timeout=5)
    monkeypatch.setattr(module, 'connection_options', lambda: options)
    admin, owner = AsyncMock(), AsyncMock()

    async def connect(**kwargs):
        if kwargs['database'] == 'postgres':
            return admin
        owner.fetchrow.return_value = dict(database=kwargs['database'], username=kwargs['user'])
        return owner

    call = AsyncMock(side_effect=connect)
    monkeypatch.setattr(module.asyncpg, 'connect', call)
    return admin, owner, call, options


@pytest.mark.parametrize('value', [None, '', 'false', 'TRUE', '1'])
async def test_missing_or_malformed_retention_never_connects(recorded, monkeypatch, value):
    _, _, connect, _ = recorded
    if value is None:
        monkeypatch.delenv('RUNTIME_PROXIMITY_RETAIN_DB')
    else:
        monkeypatch.setenv('RUNTIME_PROXIMITY_RETAIN_DB', value)
    generator = module.retained_full_schema_database.__wrapped__()
    with pytest.raises(pytest.skip.Exception if value is None else ValueError):
        await anext(generator)
    connect.assert_not_awaited()


async def test_invalid_target_is_not_hidden_as_skip(recorded, monkeypatch):
    _, _, connect, _ = recorded

    def invalid():
        raise ValueError('target refused')

    monkeypatch.setattr(module, 'connection_options', invalid)
    with pytest.raises(ValueError, match='target refused'):
        await anext(module.retained_full_schema_database.__wrapped__())
    connect.assert_not_awaited()


@pytest.mark.parametrize('failure', ['create', 'admin_close', 'owner_connect', 'database', 'username', 'query'])
async def test_setup_failures_close_owned_connections_and_never_delete(recorded, failure, capsys):
    admin, owner, connect, options = recorded
    if failure == 'create':
        admin.execute.side_effect = RuntimeError('create')
    elif failure == 'admin_close':
        admin.close.side_effect = RuntimeError('admin_close')
    elif failure == 'owner_connect':
        connect.side_effect = [admin, RuntimeError('owner_connect')]
    elif failure == 'query':
        owner.fetchrow.side_effect = RuntimeError('query')
    else:
        async def wrong_identity(*args):
            identity = dict(owner.fetchrow.return_value)
            identity[failure] = 'not_the_owned_identity'
            return identity
        owner.fetchrow.side_effect = wrong_identity
    with pytest.raises(RuntimeError):
        await anext(module.retained_full_schema_database.__wrapped__())
    admin.close.assert_awaited_once_with(timeout=5)
    if failure in {'database', 'username', 'query'}:
        owner.close.assert_awaited_once_with(timeout=5)
    owner.execute.assert_not_awaited()
    assert len(admin.execute.await_args_list) == 1
    assert admin.execute.await_args.args[0].endswith(' TEMPLATE template0')
    assert ('Synthetic proof database retained:' in capsys.readouterr().out) == (failure != 'create')


@pytest.mark.parametrize('failure', [None, 'body', 'close'])
async def test_owned_template0_connection_closes_but_database_is_retained(recorded, failure):
    admin, owner, connect, options = recorded
    generator = module.retained_full_schema_database.__wrapped__()
    actual_owner, actual_options = await anext(generator)
    assert actual_owner is owner
    name = actual_options['database']
    assert name.startswith('runtime_fullproof_') and len(name.removeprefix('runtime_fullproof_')) == 32
    assert actual_options == dict(options, database=name)
    admin.execute.assert_awaited_once_with(f'CREATE DATABASE "{name}" TEMPLATE template0')
    admin.close.assert_awaited_once_with(timeout=5)
    assert connect.await_args.kwargs == actual_options
    if failure == 'body':
        with pytest.raises(RuntimeError, match='body'):
            await generator.athrow(RuntimeError('body'))
    elif failure == 'close':
        owner.close.side_effect = RuntimeError('close')
        with pytest.raises(RuntimeError, match='close'):
            await anext(generator)
    else:
        with pytest.raises(StopAsyncIteration):
            await anext(generator)
    owner.close.assert_awaited_once_with(timeout=5)
    owner.execute.assert_not_awaited()
    assert len(admin.execute.await_args_list) == 1
