"""Explicit target/budget contract and actual lazy asyncpg lifecycle, no SQL."""

from unittest.mock import AsyncMock

import pytest

from shared import runtime_import_pool as module


def configuration(**changes):
    values = dict(socket='/tmp/fixture-socket', database='fixture_db', user='fixture_role', password='')
    values.update(changes)
    return module.ImportDatabaseConfig(**values)


@pytest.mark.parametrize('changes', [
    {'socket': '127.0.0.1'}, {'socket': 'relative'}, {'socket': '/tmp/../var'},
    {'socket': None}, {'database': ''}, {'database': 'bad;name'}, {'user': None},
    {'password': None}, {'port': True}, {'port': 0}, {'port': 65536},
    {'application_name': 'bad name'},
])
def test_rejects_implicit_or_unsupported_targets(changes):
    with pytest.raises(ValueError):
        configuration(**changes)


def test_password_hidden_and_options_ignore_ambient_settings(monkeypatch):
    for key in ('PGHOST', 'PGDATABASE', 'PGUSER', 'PGPASSWORD', 'PGPORT', 'PGSSLMODE'):
        monkeypatch.setenv(key, 'ambient-must-not-win')
    supplied = configuration()
    assert supplied.pool_options() == dict(
        host='/tmp/fixture-socket', port=5432, database='fixture_db', user='fixture_role',
        password='', ssl=False, target_session_attrs='read-write',
        min_size=0, max_size=1, timeout=5, command_timeout=10,
        server_settings={'search_path': 'public', 'statement_timeout': '10000',
                         'application_name': 'slomix-runtime-import-dev'},
    )
    # Deliberately generated fixture value, never a credential from the host.
    from uuid import uuid4
    sentinel = uuid4().hex
    assert sentinel not in repr(configuration(password=sentinel))
    first = supplied.pool_options()
    first['server_settings']['search_path'] = 'changed'
    assert supplied.pool_options()['server_settings']['search_path'] == 'public'


async def test_factory_passes_exact_options(monkeypatch):
    factory = AsyncMock(return_value=object())
    monkeypatch.setattr(module.asyncpg, 'create_pool', factory)
    supplied = configuration()
    assert await module.create_import_pool(supplied) is factory.return_value
    factory.assert_awaited_once_with(**supplied.pool_options())


async def test_real_pool_is_lazy_and_closes_without_connecting(monkeypatch):
    connect = AsyncMock(side_effect=AssertionError('Unexpected database connection'))
    monkeypatch.setattr(module.asyncpg.connection, 'connect', connect)
    pool = await module.create_import_pool(configuration())
    try:
        assert pool.get_size() == 0 and pool.get_max_size() == 1
        connect.assert_not_awaited()
    finally:
        await pool.close()
    with pytest.raises(module.asyncpg.InterfaceError, match='closed'):
        async with pool.acquire():
            pytest.fail('Closed pool allowed acquisition')
    print('Actual asyncpg pool: zero connections, capacity one, closed without network access')
