"""CLI contract and real subprocess failure proof, without a database fallback."""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from bot import runtime_import_cli as cli
from tests.unit.test_runtime_completed_import import inputs as _inputs

inputs = _inputs


def arguments(root):
    return ['--execute', '--socket', str(root / 'absent-socket'),
            '--database', 'fixture_db', '--user', 'fixture_role',
            '--spool', str(root), '--lock-directory', str(root / 'lock'),
            '--journal', 'enabled',
            '--r1', '1' * 32, '2026-09-25-120000-supply-round-1.txt', '61', 'a' * 64,
            '--r2', '2' * 32, '2026-09-25-120000-supply-round-2.txt', '61', 'b' * 64]


@pytest.mark.parametrize('missing', ['--execute', '--socket', '--database', '--user', '--journal', '--r2'])
def test_required_explicit_arguments(tmp_path, missing, monkeypatch):
    args = arguments(tmp_path)
    index = args.index(missing)
    count = 1 if missing == '--execute' else 5 if missing == '--r2' else 2
    del args[index:index + count]
    run = AsyncMock()
    monkeypatch.setattr(cli, 'run_exclusive_import_batch', run)
    with pytest.raises(SystemExit) as exc:
        cli.main(args)
    assert exc.value.code == 2
    run.assert_not_awaited()


@pytest.mark.parametrize('outcome,code,status', [
    (((True, 'canonical warning'), (True, 'Already processed')), 0, 'completed'),
    (((False, 'secret payload'),), 1, 'incomplete'),
    (ValueError('secret credential'), 1, 'failed'),
])
def test_composition_and_redacted_summary(tmp_path, monkeypatch, capsys, outcome, code, status):
    run = AsyncMock()
    if isinstance(outcome, Exception):
        run.side_effect = outcome
    else:
        run.return_value = outcome
    monkeypatch.setattr(cli, 'run_exclusive_import_batch', run)
    before = logging.root.manager.disable
    assert cli.main(arguments(tmp_path)) == code
    output = capsys.readouterr()
    assert 'secret' not in output.out + output.err
    result = json.loads(output.out)
    assert result['status'] == status and result['source_acknowledged'] is False
    assert logging.root.manager.disable == before
    database, jobs = run.await_args.args
    assert database.password == '' and database.database == 'fixture_db'
    assert jobs[1].first == jobs[0].current
    assert run.await_args.kwargs['journal_enabled'] is True


def test_journal_can_be_explicitly_disabled(tmp_path, monkeypatch, capsys):
    args = arguments(tmp_path)
    args[args.index('--journal') + 1] = 'disabled'
    run = AsyncMock(return_value=((True, 'done'), (True, 'done')))
    monkeypatch.setattr(cli, 'run_exclusive_import_batch', run)
    assert cli.main(args) == 0
    assert run.await_args.kwargs['journal_enabled'] is False


@pytest.mark.parametrize('strict', [False, True])
def test_cli_forwards_explicit_identity_policy(tmp_path, monkeypatch, strict):
    args = arguments(tmp_path)
    if strict:
        args.append('--require-declared-identity')
    run = AsyncMock(return_value=((True, 'ok'), (True, 'ok')))
    monkeypatch.setattr(cli, 'run_exclusive_import_batch', run)
    assert cli.main(args) == 0
    assert run.await_args.kwargs['require_declared_identity'] is strict


def test_bad_round_order_never_runs_batch(tmp_path, monkeypatch, capsys):
    args = arguments(tmp_path)
    args[args.index('--r1') + 2] = 'wrong-round-2.txt'
    run = AsyncMock()
    monkeypatch.setattr(cli, 'run_exclusive_import_batch', run)
    assert cli.main(args) == 1
    run.assert_not_awaited()
    assert json.loads(capsys.readouterr().out)['status'] == 'failed'


def test_interrupted_command_restores_logging(tmp_path, monkeypatch, capsys):
    def interrupt(*args):
        raise KeyboardInterrupt
    monkeypatch.setattr(cli, 'execute', interrupt)
    before = logging.root.manager.disable
    assert cli.main(arguments(tmp_path)) == 130
    assert logging.root.manager.disable == before
    assert json.loads(capsys.readouterr().out)['status'] == 'interrupted'


def test_real_subprocess_refuses_missing_receipts_without_setup_imports(tmp_path):
    (tmp_path / 'lock').mkdir(mode=0o700)
    root = Path(__file__).resolve().parents[2]
    script = '''
import importlib.abc, runpy, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'discord', 'dotenv', 'website'} or fullname in {
            'bot.config', 'bot.logging_config', 'shared.importer_startup',
        }:
            raise AssertionError('Forbidden setup dependency')
sys.meta_path.insert(0, Block())
sys.argv = ['runtime-import'] + sys.argv[1:]
runpy.run_module('bot.runtime_import_cli', run_name='__main__')
'''
    result = subprocess.run(
        [sys.executable, '-c', script, *arguments(tmp_path)], cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(root)}, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout) == {'status': 'failed', 'source_acknowledged': False}
    assert result.stderr == ''
    assert sorted(item.name for item in tmp_path.iterdir()) == ['lock']


def test_actual_receipts_and_parser_with_unavailable_database(inputs, tmp_path):
    """Exercise the real CLI to canonical SQL failure; retain all input bytes."""
    (tmp_path / 'lock').mkdir(mode=0o700)
    args = arguments(tmp_path)
    for number, (item, _) in enumerate(inputs, start=1):
        offset = args.index(f'--r{number}') + 1
        args[offset:offset + 4] = [item.generation, item.filename, str(item.size), item.sha256]
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, '-m', 'bot.runtime_import_cli', *args], cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(root), 'PGPASSWORD': 'never-print-this-sentinel'},
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 1
    assert result.stderr == ''
    assert json.loads(result.stdout) == {
        'status': 'incomplete', 'attempted': 1, 'successful': 0, 'source_acknowledged': False,
    }
    for item, raw in inputs:
        source = item.root / item.generation / item.filename
        assert source.read_bytes() == raw
        assert source.with_name(source.name + '.complete.json').exists()


@pytest.mark.parametrize('deferred', [False, True])
def test_cli_team_policy_default_and_opt_in(tmp_path, monkeypatch, deferred):
    args = arguments(tmp_path)
    if deferred:
        args.append('--defer-team-assignment')
    run = AsyncMock(return_value=((True, 'ok'), (True, 'ok')))
    monkeypatch.setattr(cli, 'run_exclusive_import_batch', run)
    assert cli.main(args) == 0
    assert run.await_args.kwargs['defer_team_assignment'] is deferred


def test_cli_deferred_without_journal_fails_before_batch(tmp_path, monkeypatch, capsys):
    args = arguments(tmp_path) + ['--defer-team-assignment']
    args[args.index('--journal') + 1] = 'disabled'
    run = AsyncMock()
    monkeypatch.setattr(cli, 'run_exclusive_import_batch', run)
    with pytest.raises(SystemExit) as exc:
        cli.main(args)
    assert exc.value.code == 2
    assert 'requires enabled journal' in capsys.readouterr().err
    run.assert_not_awaited()
    assert not (tmp_path / 'lock').exists()


@pytest.mark.parametrize('deferred', [False, True])
def test_new_process_cli_routes_team_policy_to_manager(request, tmp_path, deferred):
    pair = request.getfixturevalue('inputs')
    args = arguments(tmp_path)
    for number, (item, _) in enumerate(pair, start=1):
        index = args.index(f'--r{number}') + 1
        args[index:index + 4] = [item.generation, item.filename, str(item.size), item.sha256]
    (tmp_path / 'lock').mkdir(mode=0o700)
    if deferred:
        args.append('--defer-team-assignment')
    script = '''
import os, runpy, sys
import bot.runtime_import_attempt as attempt
from postgresql_database_manager import PostgreSQLDatabaseManager
calls, pools = [], []
class Pool:
    def __init__(self): self.closed = False
    async def close(self): self.closed = True
    def terminate(self): raise AssertionError('unexpected termination')
async def factory(config):
    pool = Pool()
    pools.append(pool)
    return pool
async def canonical(self, path, *, input_source, runtime_binding=None):
    assert self.defer_team_assignment is (os.environ['PROOF_DEFERRED'] == 'true')
    assert self.event_stream_enabled is True
    assert self.pool is pools[-1] and not self.pool.closed
    assert input_source.parse(None)['success']
    calls.append(path.name)
    return True, 'composition proof; DB effect stubbed'
attempt.create_import_pool = factory
PostgreSQLDatabaseManager.process_file = canonical
sys.argv = ['runtime-import'] + sys.argv[1:]
try:
    runpy.run_module('bot.runtime_import_cli', run_name='__main__')
except SystemExit as result:
    assert result.code == 0
    assert len(calls) == len(pools) == 2
    assert all(pool.closed for pool in pools)
'''
    result = subprocess.run([sys.executable, '-c', script, *args],
                            cwd=Path(__file__).resolve().parents[2],
                            env={**os.environ, 'PROOF_DEFERRED': str(deferred).lower(),
                                 'EVENT_STREAM_ENABLED': 'false', 'RUNTIME_TEAM_EVENTS_ENABLED': 'true'},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ''
    assert json.loads(result.stdout) == {'status': 'completed', 'attempted': 2,
                                         'successful': 2, 'source_acknowledged': False}
    assert all((item.root / item.generation / item.filename).read_bytes() == raw for item, raw in pair)
    print(f'New CLI process: defer={deferred}, 2 sealed inputs, 2 closed pools; SQL effect stubbed')
