"""Bounded CLI/asyncio proof with pool protocol doubles; no native DB claim."""

import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from shared import runtime_team_cli as cli
from shared import runtime_team_session as session
from shared import runtime_team_worker as lifecycle

FLAGS = ('EVENT_STREAM_ENABLED', 'RUNTIME_TEAM_EVENTS_ENABLED', 'RUNTIME_TEAM_WORKER_ENABLED')


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    for flag in FLAGS:
        monkeypatch.setenv(flag, 'true')


@pytest.fixture
def socket():
    # Empty private directory only: never create a socket or start PostgreSQL.
    with tempfile.TemporaryDirectory(prefix='slomix-runtime-pg-', dir='/tmp') as directory:
        yield Path(directory)


def arguments(socket):
    return ['--execute', '--socket', str(socket), '--database', 'slomix_fixture_' + 'a' * 32,
            '--user', 'fixture_role', '--run-seconds', '0.03', '--poll-seconds', '0.005']


@pytest.mark.parametrize('flag', FLAGS)
async def test_gate_precedes_filesystem_and_pool(monkeypatch, flag):
    monkeypatch.delenv(flag)
    configure = Mock(side_effect=AssertionError('Filesystem touched'))
    monkeypatch.setattr(cli, '_configuration', configure)
    factory = AsyncMock()
    monkeypatch.setattr(session, 'create_import_pool', factory)
    result = await cli.execute(cli.parser().parse_args(arguments('/absent')))
    assert result['status'] == 'disabled' and result['has_successful_page'] is False
    assert result['last_page'] is None
    configure.assert_not_called()
    factory.assert_not_awaited()


@pytest.mark.parametrize('option,value', [
    ('--run-seconds', 'nan'), ('--run-seconds', 'inf'), ('--run-seconds', '0'),
    ('--run-seconds', '3601'), ('--attempt-timeout', '301'), ('--close-timeout', '31'),
    ('--poll-seconds', '-1'), ('--batch-size', '0'), ('--batch-size', '1001'),
    ('--port', '0'), ('--database', 'etlegacy'), ('--user', 'bad role'),
    ('--socket', '/var/run/postgresql'), ('--socket', 'relative'),
])
async def test_invalid_active_inputs_never_create_pool(socket, monkeypatch, option, value):
    args = arguments(socket)
    if option in args:
        args[args.index(option) + 1] = value
    else:
        args += [option, value]
    factory = AsyncMock()
    monkeypatch.setattr(session, 'create_import_pool', factory)
    with pytest.raises(cli.InvalidConfiguration):
        await cli.execute(cli.parser().parse_args(args))
    factory.assert_not_awaited()


@pytest.mark.parametrize('mode', ['permissions', 'symlink', 'owner'])
async def test_private_socket_contract_precedes_pool(socket, monkeypatch, mode):
    if mode == 'permissions':
        socket.chmod(0o755)
    elif mode == 'owner':
        monkeypatch.setattr(cli.os, 'getuid', lambda: -1)
    else:
        link = socket.with_name(socket.name + '-link')
        link.symlink_to(socket)
        socket = link
    factory = AsyncMock()
    monkeypatch.setattr(session, 'create_import_pool', factory)
    try:
        with pytest.raises(cli.InvalidConfiguration):
            await cli.execute(cli.parser().parse_args(arguments(socket)))
        factory.assert_not_awaited()
    finally:
        if mode == 'symlink':
            socket.unlink()


def protocol_pool(monkeypatch, page):
    trace = []

    @asynccontextmanager
    async def acquire():
        trace.append('acquire')
        try:
            yield object()
        finally:
            trace.append('release')

    async def close():
        trace.append('close')

    async def factory(database):
        assert database.password == '' and database.application_name == 'slomix-runtime-team-dev'
        assert database.database == 'slomix_fixture_' + 'a' * 32 and database.user == 'fixture_role'
        trace.append('create')
        return SimpleNamespace(acquire=acquire, close=close, terminate=Mock())

    monkeypatch.setattr(session, 'create_import_pool', factory)
    monkeypatch.setattr(lifecycle, 'consume_team_page', page)
    return trace


def idle_page():
    return SimpleNamespace(status='idle', next_hint=None, items=())


async def test_actual_duration_stops_worker_and_closes_pool(socket, monkeypatch):
    async def page(conn, **kwargs):
        return idle_page()

    trace = protocol_pool(monkeypatch, page)
    result = await asyncio.wait_for(cli.execute(cli.parser().parse_args(arguments(socket))), 1)
    assert result == {'status': 'stopped', 'has_successful_page': True,
                      'last_page': {'inspected': 0, 'processed': 0, 'pending': 0, 'already_processed': 0},
                      'last_error_type': None, 'source_acknowledged': False}
    assert trace[0] == 'create' and trace[-2:] == ['release', 'close']
    assert trace.count('acquire') == trace.count('release') >= 1
    print('actual bounded CLI asyncio:', trace, result)


async def test_duration_during_page_waits_for_attempt_cleanup(socket, monkeypatch):
    async def page(conn, **kwargs):
        await asyncio.Event().wait()

    trace = protocol_pool(monkeypatch, page)
    args = arguments(socket) + ['--attempt-timeout', '0.06']
    result = await asyncio.wait_for(cli.execute(cli.parser().parse_args(args)), 1)
    assert trace == ['create', 'acquire', 'release', 'close']
    assert result['status'] == 'stopped' and result['has_successful_page'] is False
    assert result['last_page'] is None and result['last_error_type'] == 'TimeoutError'


async def test_program_error_is_redacted_after_release_and_close(socket, monkeypatch):
    async def page(conn, **kwargs):
        raise ValueError('SECRET connection details')

    trace = protocol_pool(monkeypatch, page)
    result = await cli.execute(cli.parser().parse_args(arguments(socket)))
    assert result['status'] == 'failed' and result['last_error_type'] == 'ValueError'
    assert 'SECRET' not in json.dumps(result) and result['has_successful_page'] is False
    assert trace == ['create', 'acquire', 'release', 'close']


async def test_actual_cancellation_releases_and_closes(socket, monkeypatch):
    entered = asyncio.Event()

    async def page(conn, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    trace = protocol_pool(monkeypatch, page)
    args = arguments(socket)
    args[args.index('--run-seconds') + 1] = '30'
    task = asyncio.create_task(cli.execute(cli.parser().parse_args(args)))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert trace == ['create', 'acquire', 'release', 'close']
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize('mode,code', [('disabled', 3), ('invalid', 2), ('missing-execute', 2)])
def test_actual_subprocess_has_no_connection_or_setup_dependencies(tmp_path, mode, code):
    script = '''
import importlib.abc, runpy, sys
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname.split('.')[0] in {'discord', 'dotenv', 'website', 'bot'}:
   raise AssertionError('Forbidden startup dependency')
sys.meta_path.insert(0, Block())
import asyncpg
async def forbidden(*args, **kwargs): raise AssertionError('Pool construction attempted')
asyncpg.create_pool = forbidden
sys.argv = ['runtime-team'] + sys.argv[1:]
runpy.run_module('shared.runtime_team_cli', run_name='__main__')
'''
    args = arguments(tmp_path / 'missing')
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2])}
    if mode == 'disabled':
        for flag in FLAGS:
            env.pop(flag, None)
    if mode == 'missing-execute':
        args.remove('--execute')
    result = subprocess.run([sys.executable, '-c', script, *args], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == code, result.stderr + result.stdout
    if mode != 'missing-execute':
        assert json.loads(result.stdout)['status'] == mode
        assert result.stderr == ''
    assert list(tmp_path.iterdir()) == []


def test_main_never_calls_no_completed_page_a_success(socket, monkeypatch, capsys):
    monkeypatch.setattr(cli, 'execute', AsyncMock(return_value={
        'status': 'stopped', 'has_successful_page': False, 'last_page': None,
        'last_error_type': 'ConnectionError', 'source_acknowledged': False,
    }))
    previous = logging.root.manager.disable
    assert cli.main(arguments(socket)) == 1
    assert json.loads(capsys.readouterr().out)['last_error_type'] == 'ConnectionError'
    assert logging.root.manager.disable == previous


@pytest.mark.parametrize('fail', [False, True])
def test_actual_main_json_preserves_pool_cleanup_and_redacts_failure(socket, monkeypatch, capsys, fail):
    async def page(conn, **kwargs):
        if fail:
            raise ValueError('SECRET raw connection exception')
        return idle_page()

    trace = protocol_pool(monkeypatch, page)
    previous = logging.root.manager.disable
    assert cli.main(arguments(socket)) == (1 if fail else 0)
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert report['status'] == ('failed' if fail else 'stopped')
    assert report['has_successful_page'] is not fail
    assert 'SECRET' not in output.out + output.err
    assert logging.root.manager.disable == previous
    assert trace[0] == 'create' and trace[-2:] == ['release', 'close']
    print('actual CLI main JSON:', report, 'balanced pool:', trace.count('acquire') == trace.count('release'))


async def test_error_cancels_pending_duration_timer(socket, monkeypatch):
    loop = asyncio.get_running_loop()
    original = loop.call_later
    timers = []

    def call_later(delay, callback, *args, **kwargs):
        timer = original(delay, callback, *args, **kwargs)
        if delay == 30:
            timers.append(timer)
        return timer

    async def page(conn, **kwargs):
        raise ValueError('fixture failure')

    protocol_pool(monkeypatch, page)
    monkeypatch.setattr(loop, 'call_later', call_later)
    args = arguments(socket)
    args[args.index('--run-seconds') + 1] = '30'
    assert (await cli.execute(cli.parser().parse_args(args)))['status'] == 'failed'
    assert len(timers) == 1 and timers[0].cancelled()


def test_previous_success_does_not_hide_later_unavailability(socket, monkeypatch, capsys):
    monkeypatch.setattr(cli, 'execute', AsyncMock(return_value={
        'status': 'stopped', 'has_successful_page': True,
        'last_page': {'inspected': 1, 'processed': 1, 'pending': 0, 'already_processed': 0},
        'last_error_type': 'ConnectionError', 'source_acknowledged': False,
    }))
    assert cli.main(arguments(socket)) == 1
    assert json.loads(capsys.readouterr().out)['has_successful_page'] is True


@pytest.mark.parametrize('handle_sigterm', [False, True])
@pytest.mark.parametrize('outcome', ['success', 'failure', 'cancel'])
async def test_sigterm_handler_is_process_opt_in_and_removed(socket, monkeypatch, handle_sigterm, outcome):
    loop = asyncio.get_running_loop()
    add, remove = Mock(), Mock()
    monkeypatch.setattr(loop, 'add_signal_handler', add)
    monkeypatch.setattr(loop, 'remove_signal_handler', remove)

    async def run(database, worker, stop, **kwargs):
        if handle_sigterm:
            signum, callback = add.call_args.args
            assert signum == cli.signal.SIGTERM
            callback()
            callback()  # Repeated stop requests are harmless.
            assert stop.is_set()
        if outcome == 'cancel':
            raise asyncio.CancelledError()
        if outcome == 'failure':
            raise RuntimeError('fixture failure')
        return cli.TeamWorkerState(status='stopped')

    monkeypatch.setattr(cli, 'run_team_worker', run)
    args = cli.parser().parse_args(arguments(socket))
    if outcome == 'cancel':
        with pytest.raises(asyncio.CancelledError):
            await cli.execute(args, handle_sigterm=handle_sigterm)
    else:
        result = await cli.execute(args, handle_sigterm=handle_sigterm)
        assert result['status'] == ('failed' if outcome == 'failure' else 'stopped')
    if handle_sigterm:
        assert add.call_count == 1
        remove.assert_called_once_with(cli.signal.SIGTERM)
    else:
        add.assert_not_called()
        remove.assert_not_called()
