"""Supervisor admission and native capture; never starts ET or systemd units."""

import os
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import runtime_game_supervisor as module
from tests.unit.test_runtime_match_listener import PEER, listener_path  # noqa: F401
from tests.unit.test_runtime_process_channel import approval

UNIT = 'slomix-et-proof-1234abcd.service'
INVOCATION = 'a' * 32


@pytest.mark.parametrize('deferred', [False, True])
def test_live_capture_passed_once_to_opt_in_import(monkeypatch, tmp_path, deferred):
    from unittest.mock import AsyncMock, Mock, create_autospec

    from scripts import runtime_game_import
    captured = SimpleNamespace(first_identity=SimpleNamespace(match_id='match'),
                               first=SimpleNamespace(reference=SimpleNamespace(sha256='first')),
                               second=SimpleNamespace(reference=SimpleNamespace(sha256='second')))
    pipe = Mock()
    child = SimpleNamespace(pid=123, stdin=pipe)
    monkeypatch.setattr(module, 'require_containment', lambda unit: {'InvocationID': INVOCATION})
    monkeypatch.setattr(module, 'verify_source', lambda *args: None)
    monkeypatch.setattr(module, 'startup_recipe', lambda *args, **kw: dict(argv=[], cwd='/', env={}, workspace={}))
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *args, **kw: child)
    monkeypatch.setattr(module.os, 'set_blocking', lambda *args: None)
    monkeypatch.setattr(module, 'capture_process', lambda *args: captured)
    monkeypatch.setattr(runtime_game_import, 'preflight_import',
                        create_autospec(runtime_game_import.preflight_import))
    importer = AsyncMock(return_value={'status': 'incomplete'})
    monkeypatch.setattr(runtime_game_import, 'import_live_capture', importer)
    result = module.run(tmp_path, UNIT, 'b' * 40, proof_socket=tmp_path,
                        proof_database_name='explicit', import_lock_directory=tmp_path, defer_team_assignment=deferred)
    importer.assert_awaited_once_with(captured, socket=tmp_path, database='explicit', lock_directory=tmp_path,
                                     defer_team_assignment=deferred)
    assert result['import']['status'] == 'incomplete'
    assert result['status'] == 'captured_import_attempted_shutdown_pending'
    pipe.close.assert_called_once()


def stopped():
    return dict(module.POLICY, Id=UNIT, ActiveState='inactive', MainPID='0',
                ControlGroup='', InvocationID=INVOCATION, Result='success')


@pytest.mark.parametrize('field', list(module.POLICY))
def test_policy_drift_is_rejected(monkeypatch, field):
    properties = stopped()
    properties[field] = 'wrong'
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: SimpleNamespace(
        stdout='\n'.join(f'{k}={v}' for k, v in properties.items())))
    with pytest.raises(ValueError, match='policy'):
        module.unit_properties(UNIT)


def test_run_outside_service_cannot_launch(monkeypatch, tmp_path):
    monkeypatch.setattr(module, 'unit_properties', lambda unit: stopped())
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **k: pytest.fail('Launch reached'))
    with pytest.raises(ValueError, match='main process'):
        module.run(tmp_path, UNIT, 'b' * 40)


def test_manager_claim_without_kernel_membership_is_rejected(monkeypatch):
    values = dict(stopped(), MainPID=str(os.getpid()), ActiveState='active', SubState='running',
                  ControlGroup='/user.slice/' + UNIT)
    monkeypatch.setattr(module, 'unit_properties', lambda unit: values)
    with pytest.raises(ValueError, match='cgroup'):
        module.require_containment(UNIT)


def test_commit_and_tracked_drift(tmp_path):
    def git(*args):
        return subprocess.check_output(['/usr/bin/git', '-C', str(tmp_path), *args], text=True).strip()
    git('init', '-q')
    path = tmp_path / 'source.py'
    path.write_text('original\n')
    git('add', 'source.py')
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '-qm', 'test: fixture')
    head = git('rev-parse', 'HEAD')
    module.verify_source(tmp_path, head)
    with pytest.raises(ValueError, match='moved'):
        module.verify_source(tmp_path, '0' * 40)
    path.write_text('changed\n')
    with pytest.raises(subprocess.CalledProcessError):
        module.verify_source(tmp_path, head)
    git('add', 'source.py')
    with pytest.raises(subprocess.CalledProcessError):
        module.verify_source(tmp_path, head)


def test_shutdown_requires_same_invocation(monkeypatch):
    monkeypatch.setattr(module, 'unit_properties', lambda unit: stopped())
    with pytest.raises(ValueError, match='shutdown'):
        module.verify_stopped(UNIT, 27962, 'b' * 32)


def test_native_occupied_udp_is_not_shutdown(monkeypatch):
    monkeypatch.setattr(module, 'unit_properties', lambda unit: stopped())
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        with pytest.raises(ValueError, match='occupied'):
            module.verify_stopped(UNIT, port, INVOCATION)
    result = module.verify_stopped(UNIT, port, INVOCATION)
    assert result['status'] == 'stopped'
    assert result['match_success'] == 'not_inferred_from_shutdown'


def test_native_capture_bridge(tmp_path, listener_path):  # noqa: F811
    roots = {}
    for name in ('authority', 'host_authority', 'producer_spool', 'capture_root'):
        directory = tmp_path / name
        directory.mkdir(mode=0o700)
        roots[name] = str(directory)
    executable = Path(sys.executable).resolve()
    record = dict(roots=roots, executable=str(executable), uid=os.getuid(),
                  executable_sha256=approval(executable)['expected_sha256'],
                  source_id='native-rehearsal', map_name='supply', socket_path=str(listener_path))
    peer = subprocess.Popen([str(executable), '-c', PEER.replace("== 'go'", "== 'map supply'"),
                             str(listener_path), roots['producer_spool']], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, umask=0o077)
    try:
        assert peer.stdout.readline().strip() == 'READY'
        os.set_blocking(peer.stdin.fileno(), False)
        result = module.capture_process(record, peer.pid, peer.stdin.fileno())
        result.verify()
        assert peer.stdout.readline().strip() == 'CLOSED BOTH'
        for capture in (result.first, result.second):
            path = capture.directory / capture.reference.filename
            digest = subprocess.check_output(['sha256sum', str(path)], text=True).split()[0]
            assert digest == capture.reference.sha256
        assert len(list(Path(roots['producer_spool']).glob('*/*.txt'))) == 2
    finally:
        peer.stdin.close()
        peer.wait(timeout=10)
    assert peer.returncode == 0, peer.stderr.read()
    print('Native peer: fresh allocation -> console release -> two captures -> EOF exit; NOT ET/systemd')


@pytest.mark.parametrize('policy', [None, 1, 'true', True])
def test_team_policy_refused_before_containment_or_launch(monkeypatch, tmp_path, policy):
    from unittest.mock import Mock

    containment = Mock(side_effect=AssertionError('must not reach service manager'))
    monkeypatch.setattr(module, 'require_containment', containment)
    with pytest.raises(ValueError, match='team assignment|team ownership'):
        module.run(tmp_path, UNIT, 'b' * 40, defer_team_assignment=policy)
    containment.assert_not_called()


def test_new_process_deferred_without_target_is_redacted_refusal(tmp_path):
    script = Path(module.__file__).resolve()
    result = subprocess.run([sys.executable, str(script), 'run', '--directory', str(tmp_path),
                             '--unit', UNIT, '--commit', 'b' * 40, '--defer-team-assignment'],
                            capture_output=True, text=True, timeout=10)
    import json

    assert result.returncode == 1
    assert result.stdout == ''
    assert json.loads(result.stderr) == {'status': 'refused_or_failed', 'error_type': 'ValueError',
                                        'shutdown_verified': False, 'evidence_retained': True}


@pytest.mark.parametrize('deferred', [False, True])
def test_supervisor_cli_forwards_policy(monkeypatch, tmp_path, deferred):
    from unittest.mock import Mock

    run = Mock(return_value={'status': 'fixture'})
    monkeypatch.setattr(module, 'run', run)
    args = ['run', '--directory', str(tmp_path), '--unit', UNIT, '--commit', 'b' * 40,
            '--proof-socket', str(tmp_path), '--proof-database-name', 'explicit',
            '--import-lock-directory', str(tmp_path)]
    if deferred:
        args.append('--defer-team-assignment')
    assert module.main(args) == 0
    assert run.call_args.kwargs['defer_team_assignment'] is deferred
