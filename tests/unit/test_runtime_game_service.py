"""Offline systemd parser proof; no unit activation or game process."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import prepare_runtime_game_service as module


@pytest.mark.parametrize('value', ['/tmp/a%b', '/tmp/a$b', '/tmp/a b', '/tmp/a\nb', '/tmp/../a'])
def test_expansion_paths_rejected(value):
    with pytest.raises(ValueError, match='ASCII'):
        module.safe_path(Path(value))


@pytest.mark.parametrize('bots', [False, True])
@pytest.mark.parametrize('import_requested,defer_team_assignment', [(False, False), (True, False), (True, True)])
def test_offline_unit_parser_and_exclusive_output(
        tmp_path, monkeypatch, bots, import_requested, defer_team_assignment):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'scripts').mkdir()
    (source / 'scripts/runtime_game_supervisor.py').write_text('raise SystemExit(99)\n')
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    tmp_path.chmod(0o700)
    checks = []
    monkeypatch.setattr(module, 'verify_source', lambda *a: checks.append('source'))
    monkeypatch.setattr(module, 'startup_recipe', lambda *a, **k: checks.append('workspace'))
    args = dict(source=source, interpreter=Path(sys.executable), workspace=workspace,
                destination=tmp_path / 'unit', commit='a' * 40,
                defer_team_assignment=defer_team_assignment)
    if bots:
        args.update(bot_fixture=tmp_path / 'bots', bot_manifest_sha256='b' * 64)
    if import_requested:
        args.update(proof_socket=Path('/tmp/slomix-runtime-pg-fixture'),
                    proof_database_name='slomix_fixture_' + 'c' * 32,
                    import_lock_directory=tmp_path / 'lock')
    record = module.prepare(**args)
    assert checks == ['source', 'workspace']
    assert record['activation_ready'] is False
    unit = args['destination'] / record['unit']
    text = unit.read_text()
    assert ('--proof-socket' in text) == import_requested
    assert record['import_requested'] == import_requested
    assert ('--defer-team-assignment' in text) is defer_team_assignment
    assert record['defer_team_assignment'] is defer_team_assignment
    assert json.loads((args['destination'] / 'service.json').read_text()) == record
    assert record['database_readiness_verified'] is False
    for line in ('Restart=no', 'RuntimeMaxSec=60min', 'KillMode=control-group',
                 'TimeoutStopSec=30s', 'LimitFSIZE=64M', 'MemoryMax=768M', 'TasksMax=64'):
        assert line in text.splitlines()
    assert 'UnsetEnvironment=PYTHONPATH PYTHONHOME LD_PRELOAD LD_LIBRARY_PATH LD_AUDIT' in text.splitlines()
    assert '[Install]' not in text and 'ExecStop=' not in text
    assert ' -I ' in text
    expected = (f"ExecStart={args['interpreter']} -I -B {source}/scripts/runtime_game_supervisor.py"
                f" run --directory {workspace} --unit {record['unit']} --commit {'a' * 40}")
    if bots:
        expected += f" --bot-fixture {tmp_path / 'bots'} --bot-manifest-sha256 {'b' * 64}"
    if import_requested:
        expected += (f" --proof-socket {args['proof_socket']} --proof-database-name {args['proof_database_name']}"
                     f" --import-lock-directory {args['import_lock_directory']}")
    if defer_team_assignment:
        expected += ' --defer-team-assignment'
    assert expected in text.splitlines()
    assert ('--bot-fixture' in text) == bots
    if bots:
        assert '--bot-manifest-sha256 ' + 'b' * 64 in text
    assert (args['destination'] / 'verify.txt').read_bytes() == b''
    assert (args['destination'] / 'service.log').read_bytes() == b''
    assert hashlib.sha256(unit.read_bytes()).hexdigest() == record['unit_sha256']
    assert subprocess.check_output(['sha256sum', str(unit)], text=True).split()[0] == record['unit_sha256']
    with pytest.raises(ValueError, match='NEW'):
        module.prepare(**args)


def test_source_refusal_creates_nothing(tmp_path, monkeypatch):
    def refuse(*args):
        raise ValueError('source refused')
    monkeypatch.setattr(module, 'verify_source', refuse)
    destination = tmp_path / 'output'
    with pytest.raises(ValueError, match='source refused'):
        module.prepare(source=tmp_path, interpreter=Path(sys.executable), workspace=tmp_path,
                       destination=destination, commit='a' * 40)
    assert not destination.exists()


@pytest.mark.parametrize('options', [
    {'proof_socket': Path('/tmp/slomix-runtime-pg-proof')},
    {'proof_socket': Path('/tmp/slomix-runtime-pg-proof'), 'proof_database_name': 'etlegacy',
     'import_lock_directory': Path('/tmp/lock')},
    {'proof_socket': Path('/tmp/slomix-runtime-pg-%n'),
     'proof_database_name': 'slomix_fixture_' + 'a' * 32, 'import_lock_directory': Path('/tmp/lock')},
])
def test_import_options_fail_closed(tmp_path, options):
    with pytest.raises(ValueError):
        module.render(source=tmp_path, interpreter=tmp_path / 'python', workspace=tmp_path / 'game',
                      destination=tmp_path / 'unit', unit='slomix-et-proof-' + 'a' * 16 + '.service',
                      commit='b' * 40, **options)


@pytest.mark.parametrize('policy', [None, 0, 1, 'true'])
@pytest.mark.parametrize('entrypoint', ['render', 'prepare'])
def test_team_policy_requires_an_explicit_bool_before_resources(monkeypatch, policy, entrypoint):
    def forbidden(*args, **kwargs):
        pytest.fail('invalid team policy touched source or workspace')
    monkeypatch.setattr(module, 'verify_source', forbidden)
    monkeypatch.setattr(module, 'startup_recipe', forbidden)
    args = dict(source=None, interpreter=None, workspace=None, destination=None,
                commit='a' * 40, defer_team_assignment=policy)
    if entrypoint == 'render':
        args['unit'] = 'slomix-et-proof-' + 'a' * 16 + '.service'
    with pytest.raises(ValueError, match='Explicit boolean'):
        getattr(module, entrypoint)(**args)


@pytest.mark.parametrize('missing', ['proof_socket', 'proof_database_name', 'import_lock_directory'])
@pytest.mark.parametrize('entrypoint', ['render', 'prepare'])
def test_deferred_policy_requires_complete_target_before_resources(monkeypatch, missing, entrypoint):
    def forbidden(*args, **kwargs):
        pytest.fail('incomplete deferred target touched source or workspace')
    monkeypatch.setattr(module, 'verify_source', forbidden)
    monkeypatch.setattr(module, 'startup_recipe', forbidden)
    args = dict(source=None, interpreter=None, workspace=None, destination=None,
                commit='a' * 40, defer_team_assignment=True,
                proof_socket=Path('/tmp/slomix-runtime-pg-fixture'),
                proof_database_name='slomix_fixture_' + 'c' * 32,
                import_lock_directory=Path('/tmp/lock'))
    args[missing] = None
    if entrypoint == 'render':
        args['unit'] = 'slomix-et-proof-' + 'a' * 16 + '.service'
    with pytest.raises(ValueError, match='complete proof import target'):
        getattr(module, entrypoint)(**args)


@pytest.mark.parametrize('enabled', [False, True])
def test_cli_forwards_explicit_policy(monkeypatch, capsys, enabled):
    observed = []
    monkeypatch.setattr(module, 'prepare', lambda **kw: observed.append(kw) or {'prepared': True})
    argv = ['prepare_runtime_game_service', '--source', '/source', '--interpreter', '/python',
            '--workspace', '/workspace', '--destination', '/destination', '--commit', 'a' * 40]
    if enabled:
        argv.append('--defer-team-assignment')
    monkeypatch.setattr(sys, 'argv', argv)
    assert module.main() == 0
    assert observed[0]['defer_team_assignment'] is enabled
    assert json.loads(capsys.readouterr().out) == {'prepared': True}


def test_fresh_cli_rejects_deferred_without_target_before_source_or_writes(tmp_path):
    destination = tmp_path / 'uncreated'
    result = subprocess.run(
        [sys.executable, '-I', str(Path(module.__file__).resolve()),
         '--source', '/nonexistent/source', '--interpreter', sys.executable,
         '--workspace', '/nonexistent/workspace', '--destination', str(destination),
         '--commit', 'a' * 40, '--defer-team-assignment'],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 1
    assert result.stdout == ''
    assert json.loads(result.stderr) == {
        'status': 'refused', 'error_type': 'ValueError',
        'activation_ready': False, 'evidence_retained': True,
    }
    assert not destination.exists()


def test_render_default_does_not_read_ambient_team_flags(monkeypatch):
    monkeypatch.setenv('RUNTIME_TEAM_EVENTS_ENABLED', 'true')
    monkeypatch.setenv('RUNTIME_TEAM_WORKER_ENABLED', 'true')
    text = module.render(
        source=Path('/source'), interpreter=Path('/python'), workspace=Path('/workspace'),
        destination=Path('/destination'), unit='slomix-et-proof-' + 'a' * 16 + '.service',
        commit='b' * 40, proof_socket=Path('/tmp/slomix-runtime-pg-fixture'),
        proof_database_name='slomix_fixture_' + 'c' * 32, import_lock_directory=Path('/lock'),
    )
    assert '--proof-socket' in text
    assert '--defer-team-assignment' not in text


@pytest.mark.parametrize('record', [{}, {'bundle': None}])
def test_cli_redacts_malformed_workspace_contract(tmp_path, record):
    from tests.unit.test_spa_artifact_preflight import git

    source = tmp_path / 'source'
    source.mkdir()
    git(source, 'init', '-b', 'fixture')
    git(source, 'config', 'user.name', 'Fixture')
    git(source, 'config', 'user.email', 'fixture@example.invalid')
    git(source, 'config', 'core.hooksPath', str(tmp_path / 'absent-hooks'))
    (source / 'fixture.txt').write_text('committed fixture\n')
    git(source, 'add', '--', 'fixture.txt')
    git(source, 'commit', '-m', 'fixture')
    workspace = tmp_path / 'private-workspace-sentinel'
    workspace.mkdir(mode=0o700)
    marker = workspace / 'workspace.json'
    marker.write_text(json.dumps(record))
    marker.chmod(0o600)
    result = subprocess.run([
        sys.executable, str(Path(module.__file__)), '--source', str(source),
        '--interpreter', sys.executable, '--workspace', str(workspace),
        '--destination', str(tmp_path / 'prepared'), '--commit', git(source, 'rev-parse', 'HEAD'),
    ], capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    report = json.loads(result.stderr)
    assert report['status'] == 'refused'
    assert report['error_type'] in {'KeyError', 'TypeError'}
    assert report['evidence_retained'] is True
    assert 'Traceback' not in result.stderr and str(workspace) not in result.stderr
    assert not result.stdout and not (tmp_path / 'prepared').exists()
    assert json.loads(marker.read_text()) == record
