"""Bootstrap-parity isolation is observable, not a test-database naming claim."""

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.integration import test_fresh_bootstrap_parity as module


def target():
    return dict(host='private', port=5432, database='slomix_fixture_owned', user='owner', password='')


def test_collection_never_loads_application_dotenv_or_opens_transport(tmp_path):
    script = '''
import asyncpg, dotenv, pytest
def forbidden(*args, **kwargs):
    raise AssertionError("COLLECTION_SIDE_EFFECT")
asyncpg.connect = asyncpg.create_pool = dotenv.load_dotenv = forbidden
raise SystemExit(pytest.main(['-o', 'addopts=', '-p', 'pytest_asyncio.plugin',
    '--collect-only', '-q', 'tests/integration/test_fresh_bootstrap_parity.py']))
'''
    result = subprocess.run([sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=20,
        env={**os.environ, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
             'BOT_LOG_DIR': str(tmp_path / 'bot'), 'WEB_LOG_DIR': str(tmp_path / 'web')})
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1 test collected' in result.stdout


@pytest.mark.parametrize('requested', [False, True])
async def test_ambient_target_never_authorizes_a_connection(monkeypatch, requested):
    monkeypatch.delenv('RUNTIME_EVENTS_TEST_SOCKET', raising=False)
    monkeypatch.delenv('RUNTIME_EVENTS_TEST_CI', raising=False)
    monkeypatch.setenv('POSTGRES_TEST_HOST', '192.0.2.1')
    if requested:
        monkeypatch.setenv('RUNTIME_EVENTS_TEST_CI', 'true')
    transport = AsyncMock(side_effect=AssertionError('TRANSPORT_REACHED'))
    monkeypatch.setattr(module.asyncpg, 'connect', transport)
    with pytest.raises(ValueError if requested else pytest.skip.Exception):
        await anext(module.migration_target.__wrapped__())
    transport.assert_not_awaited()


@pytest.mark.parametrize('field', ['host', 'port', 'database', 'user', 'password'])
async def test_real_runner_identity_is_pinned_and_drift_is_refused(monkeypatch, field):
    runner = module.migration_runner.__wrapped__(monkeypatch)
    assert module.parity_runner.__wrapped__(monkeypatch, target(), runner) is runner
    transport = AsyncMock()
    monkeypatch.setattr(module.asyncpg, 'connect', transport)
    await runner.get_connection()
    transport.assert_awaited_once_with(**target(), timeout=5, command_timeout=5, ssl=False)
    monkeypatch.setenv('POSTGRES_' + field.upper(), '6543' if field == 'port' else 'wrong')
    with pytest.raises(AssertionError, match='escaped its owned'):
        await runner.get_connection()
    assert transport.await_count == 1


@pytest.mark.parametrize('failure', ['database', 'username', 'query', 'body', 'close'])
async def test_reader_closes_on_identity_query_body_or_cleanup_failure(failure):
    conn = AsyncMock()
    conn.fetchrow.return_value = dict(database=target()['database'], username=target()['user'])
    runner = SimpleNamespace(get_connection=AsyncMock(return_value=conn))
    if failure in {'database', 'username'}:
        conn.fetchrow.return_value[failure] = 'wrong'
    elif failure == 'query':
        conn.fetchrow.side_effect = RuntimeError('query failed')
    generator = module.parity_connection.__wrapped__(runner, target())
    if failure in {'database', 'username', 'query'}:
        with pytest.raises(RuntimeError if failure == 'query' else AssertionError):
            await anext(generator)
    else:
        assert await anext(generator) is conn
        if failure == 'close':
            conn.close.side_effect = RuntimeError('close failed')
            with pytest.raises(RuntimeError, match='close failed'):
                await anext(generator)
        else:
            with pytest.raises(RuntimeError, match='body failed'):
                await generator.athrow(RuntimeError('body failed'))
    conn.close.assert_awaited_once_with(timeout=5)
    conn.execute.assert_not_awaited()


async def test_requested_connection_failure_is_not_skipped():
    runner = SimpleNamespace(get_connection=AsyncMock(side_effect=OSError('requested unavailable')))
    with pytest.raises(OSError, match='requested unavailable'):
        await anext(module.parity_connection.__wrapped__(runner, target()))


@pytest.mark.parametrize('failure', ['empty', 'sql', 'added', 'removed'])
async def test_actual_parity_body_rejects_missing_or_changed_schema(monkeypatch, tmp_path, failure):
    dump, migration = tmp_path / 'dump.sql', tmp_path / '001_probe.sql'
    dump.write_text('SELECT 1;')
    migration.write_text('SELECT 2;')
    monkeypatch.setattr(module, 'DUMP', dump)
    before = frozenset({('fixture', 'id', 'integer')})
    after = before
    if failure == 'empty':
        before = frozenset()
    elif failure == 'added':
        after |= {('fixture', 'unaccounted', 'text')}
    elif failure == 'removed':
        after = frozenset()
    snapshots = AsyncMock(side_effect=[before, after])
    monkeypatch.setattr(module, '_snapshot', snapshots)
    conn = AsyncMock()
    # Keep later ledger checks valid, so a missing drift guard cannot fail for
    # unrelated incomplete mock data during the negative-control mutation.
    conn.fetch.return_value = [dict(filename='001_probe.sql', success=True, checksum='synthetic')]
    conn.fetchval.return_value = 1
    if failure == 'sql':
        conn.execute.side_effect = [None, None, module.asyncpg.UndefinedTableError('missing fixture')]
    runner = SimpleNamespace(discover_migrations=lambda: [('001_probe.sql', migration)],
        unwrap_outer_transaction=lambda text: text, split_statements=lambda text: [text],
        cmd_baseline=AsyncMock(), cmd_validate=AsyncMock())
    expected = ('dump produced no schema' if failure == 'empty' else
                'missing effects' if failure == 'sql' else 'dump ≠ migrations')
    with pytest.raises(AssertionError, match=expected):
        await module.test_dump_contains_every_migration(conn, runner)
    runner.cmd_baseline.assert_not_awaited()
    runner.cmd_validate.assert_not_awaited()
    calls = conn.execute.await_args_list
    assert calls[0].args == ('SELECT 1;',) and calls[0].kwargs == {'timeout': 60}
    assert calls[1].args == ("SET statement_timeout = '5s'; SET lock_timeout = '1s'",)
    if failure != 'empty':
        assert calls[2].args == ('SELECT 2;',)
