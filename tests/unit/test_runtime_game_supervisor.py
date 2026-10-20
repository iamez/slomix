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
    monkeypatch.setattr(module, 'validate_launch_commands', lambda *args: None)
    monkeypatch.setattr(module, 'verify_source', lambda *args: None)
    monkeypatch.setattr(module, 'startup_recipe', lambda *args, **kw: dict(argv=[], cwd='/', env={}, workspace={'source_commit': 'b' * 40}))
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
                ControlGroup='', InvocationID=INVOCATION, Result='success',
                UnsetEnvironment=' '.join(module.CLEARED_ENVIRONMENT))


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
        try:
            sock.bind(('127.0.0.1', module.REHEARSAL_PORT))
        except OSError:
            pytest.skip('Dedicated rehearsal port already occupied; existing holder remains untouched')
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
    result = subprocess.run([sys.executable, '-I', str(script), 'run', '--directory', str(tmp_path),
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


def test_property_probe_explicitly_requests_empty_systemd_properties(monkeypatch):
    def show(command, **kwargs):
        assert '--all' in command
        return SimpleNamespace(stdout='\n'.join(f'{k}={v}' for k, v in stopped().items()))
    monkeypatch.setattr(module.subprocess, 'run', show)
    values = module.unit_properties(UNIT)
    assert values['NetworkNamespacePath'] == ''
    assert values['ControlGroup'] == ''


@pytest.mark.parametrize('shadow', ['asyncpg.py', 'shared/unknown.py', '__pycache__/asyncpg.pyc', 'ignored.py'])
def test_source_gate_rejects_untracked_and_ignored_inputs(tmp_path, shadow):
    from tests.unit.test_spa_artifact_preflight import git

    git(tmp_path, 'init', '-b', 'fixture')
    git(tmp_path, 'config', 'user.name', 'Fixture')
    git(tmp_path, 'config', 'user.email', 'fixture@example.invalid')
    git(tmp_path, 'config', 'core.hooksPath', str(tmp_path / 'absent-hooks'))
    (tmp_path / '.gitignore').write_text('ignored.py\n__pycache__/\n')
    (tmp_path / 'tracked.py').write_text('# trusted fixture\n')
    git(tmp_path, 'add', '--', '.gitignore', 'tracked.py')
    git(tmp_path, 'commit', '-m', 'fixture')
    head = git(tmp_path, 'rev-parse', 'HEAD')
    module.verify_source(tmp_path, head)
    path = tmp_path / shadow
    path.parent.mkdir(exist_ok=True)
    path.write_text('raise RuntimeError("must never execute")\n')
    with pytest.raises(ValueError, match='closed'):
        module.verify_source(tmp_path, head)
    assert path.exists()


def test_isolated_supervisor_loads_no_project_dependency_before_admission(tmp_path):
    import json

    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    script = scripts / 'runtime_game_supervisor.py'
    script.write_bytes(Path(module.__file__).read_bytes())
    sentinel = tmp_path / 'unexpected-import'
    for name in ('asyncpg', 'shared', 'json'):
        (scripts / f'{name}.py').write_text(f'open({str(sentinel)!r}, "w").write("unsafe")\n')
        (tmp_path / f'{name}.py').write_text(f'open({str(sentinel)!r}, "w").write("unsafe")\n')
    for options in ([], ['-I']):
        result = subprocess.run([sys.executable, *options, str(script), 'run', '--directory', str(tmp_path),
                                 '--unit', UNIT, '--commit', 'a' * 40, '--defer-team-assignment'],
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 1
        assert json.loads(result.stderr)['status'] == 'refused_or_failed'
        if not options:
            assert json.loads(result.stderr)['reason'] == 'isolated_python_required'
        assert not sentinel.exists() and not result.stdout


@pytest.mark.parametrize('unset,allowed', [('', False), ('PYTHONPATH', False),
    ('PYTHONPATH PYTHONHOME LD_PRELOAD LD_LIBRARY_PATH EXTRA', False),
    ('LD_LIBRARY_PATH LD_PRELOAD PYTHONHOME PYTHONPATH', False),
    ('LD_AUDIT LD_LIBRARY_PATH LD_PRELOAD PYTHONHOME PYTHONPATH', True)])
def test_unit_requires_the_complete_import_environment_scrub(monkeypatch, unset, allowed):
    values = stopped() | {'UnsetEnvironment': unset}
    monkeypatch.setattr(module.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(stdout='\n'.join(f'{k}={v}' for k, v in values.items())))
    if allowed:
        assert module.unit_properties(UNIT)['UnsetEnvironment'] == unset
    else:
        with pytest.raises(ValueError, match='environment is not cleared'):
            module.unit_properties(UNIT)


@pytest.mark.parametrize('flag', ['--assume-unchanged', '--skip-worktree'])
def test_source_gate_refuses_hidden_index_flags(tmp_path, flag):
    from tests.unit.test_spa_artifact_preflight import git

    git(tmp_path, 'init', '-b', 'fixture')
    git(tmp_path, 'config', 'user.name', 'Fixture')
    git(tmp_path, 'config', 'user.email', 'fixture@example.invalid')
    git(tmp_path, 'config', 'core.hooksPath', str(tmp_path / 'absent-hooks'))
    (tmp_path / 'tracked.py').write_text('# committed\n')
    git(tmp_path, 'add', '--', 'tracked.py')
    git(tmp_path, 'commit', '-m', 'fixture')
    head = git(tmp_path, 'rev-parse', 'HEAD')
    git(tmp_path, 'update-index', flag, '--', 'tracked.py')
    (tmp_path / 'tracked.py').write_text('# changed despite hidden index flag\n')
    with pytest.raises(ValueError, match='hidden index flags'):
        module.verify_source(tmp_path, head)


@pytest.mark.parametrize('name', ['MemoryMax', 'TasksMax', 'LimitFSIZE', 'LimitCORE', 'NoNewPrivileges', 'UMask'])
def test_required_resource_properties_cannot_be_omitted(monkeypatch, name):
    values = stopped()
    values.pop(name, None)
    monkeypatch.setattr(module.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(stdout='\n'.join(f'{k}={v}' for k, v in values.items())))
    with pytest.raises(ValueError, match='policy disagrees'):
        module.unit_properties(UNIT)


@pytest.mark.parametrize('failure', [ImportError, ModuleNotFoundError])
def test_deferred_import_failure_is_redacted_before_launch(monkeypatch, tmp_path, capsys, failure):
    import builtins
    import json
    original_import = builtins.__import__

    monkeypatch.setattr(module, 'require_containment', lambda unit: {'InvocationID': INVOCATION})
    monkeypatch.setattr(module, 'validate_launch_commands', lambda *args: None)
    monkeypatch.setattr(module, 'verify_source', lambda *args: None)
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *args, **kwargs: pytest.fail('Launch reached'))

    def importing(name, *args, **kwargs):
        if name == 'scripts.runtime_game_startup':
            raise failure('private dependency path /private/never-disclose')
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', importing)
    assert module.main(['run', '--directory', str(tmp_path), '--unit', UNIT, '--commit', 'b' * 40]) == 1
    output = capsys.readouterr()
    assert output.out == ''
    assert json.loads(output.err) == dict(status='refused_or_failed', error_type=failure.__name__,
                                          shutdown_verified=False, evidence_retained=True)


@pytest.mark.parametrize('failure', [KeyboardInterrupt, SystemExit, __import__('asyncio').CancelledError])
def test_cli_does_not_hide_interruption(monkeypatch, tmp_path, failure):
    def interrupt(*args, **kwargs):
        raise failure()
    monkeypatch.setattr(module, 'run', interrupt)
    with pytest.raises(failure):
        module.main(['run', '--directory', str(tmp_path), '--unit', UNIT, '--commit', 'b' * 40])


def test_corrupt_archive_failure_is_redacted(monkeypatch, tmp_path, capsys):
    import json
    import zipfile

    def invalid_archive(*args, **kwargs):
        with zipfile.ZipFile(tmp_path / 'private.pk3'):
            pytest.fail('Corrupt archive admitted')

    (tmp_path / 'private.pk3').write_bytes(b'not a zip archive')
    monkeypatch.setattr(module, 'run', invalid_archive)
    assert module.main(['run', '--directory', str(tmp_path), '--unit', UNIT, '--commit', 'b' * 40]) == 1
    output = capsys.readouterr()
    assert output.out == ''
    assert json.loads(output.err) == dict(status='refused_or_failed', error_type='BadZipFile',
                                          shutdown_verified=False, evidence_retained=True)


def test_isolated_cli_redacts_a_deferred_missing_dependency(tmp_path):
    import json
    code = """
import builtins, importlib.util, sys
spec = importlib.util.spec_from_file_location('supervisor_fixture', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.require_containment = lambda unit: {'InvocationID': 'a' * 32}
module.verify_source = lambda *args: None
module.validate_launch_commands = lambda *args: None
original_import = builtins.__import__
def importing(name, *args, **kwargs):
    if name == 'scripts.runtime_game_startup':
        raise ModuleNotFoundError('sensitive dependency and path /never/disclose')
    return original_import(name, *args, **kwargs)
builtins.__import__ = importing
raise SystemExit(module.main(['run', '--directory', sys.argv[2], '--unit',
                             'slomix-et-proof-1234abcd.service', '--commit', 'b' * 40]))
"""
    result = subprocess.run([sys.executable, '-I', '-B', '-c', code, module.__file__, str(tmp_path)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and result.stdout == ''
    assert json.loads(result.stderr) == dict(status='refused_or_failed', error_type='ModuleNotFoundError',
                                             shutdown_verified=False, evidence_retained=True)


def test_capture_allows_both_rounds_readiness_before_round_completion(monkeypatch, tmp_path):
    from contextlib import nullcontext
    from unittest.mock import Mock

    from shared import (
        runtime_game_console,
        runtime_identity_allocation,
        runtime_match_controller,
        runtime_match_listener,
        runtime_process_authority,
        runtime_process_pin,
    )

    pin = object()
    driver = object()
    result = Mock()
    listener = Mock(return_value=result)
    monkeypatch.setattr(runtime_process_pin, 'pin_process', lambda *args, **kwargs: nullcontext(pin))
    monkeypatch.setattr(runtime_process_authority, 'reserve_process_epoch', lambda *args, **kwargs: 'epoch')
    monkeypatch.setattr(runtime_identity_allocation, 'allocate_round_pair', lambda *args:
                        SimpleNamespace(first=SimpleNamespace(match_id='match')))
    monkeypatch.setattr(runtime_match_controller, 'RuntimeMatchController', lambda **kwargs: driver)
    monkeypatch.setattr(runtime_game_console, 'map_release', lambda *args: nullcontext('release'))
    monkeypatch.setattr(runtime_match_listener, 'serve_match', listener)
    record = dict(roots={name: str(tmp_path / name) for name in
                         ('authority', 'host_authority', 'producer_spool', 'capture_root')},
                  uid=os.getuid(), executable=str(Path(sys.executable).resolve()),
                  executable_sha256='a' * 64, source_id='fixture', map_name='supply',
                  socket_path=str(tmp_path / 'socket'))
    assert module.capture_process(record, 123, 0) is result
    listener.assert_called_once_with(driver, tmp_path / 'socket', on_ready='release',
                                     initial_readiness_wait=1800, bootstrap_wait=1800, completion_wait=3600)
    result.verify.assert_called_once()


@pytest.mark.parametrize('failure', [TimeoutError, __import__('asyncio').CancelledError])
def test_capture_interruption_closes_supervisor_input_without_claiming_shutdown(monkeypatch, tmp_path, failure):
    from unittest.mock import Mock
    pipe = Mock()
    monkeypatch.setattr(module, 'require_containment', lambda unit: {'InvocationID': INVOCATION})
    monkeypatch.setattr(module, 'validate_launch_commands', lambda *args: None)
    monkeypatch.setattr(module, 'verify_source', lambda *args: None)
    monkeypatch.setattr(module, 'startup_recipe', lambda *args, **kwargs: dict(argv=[], cwd='/', env={}, workspace={'source_commit': 'b' * 40}))
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *args, **kwargs: SimpleNamespace(pid=123, stdin=pipe))
    monkeypatch.setattr(module.os, 'set_blocking', lambda *args: None)
    def interrupted(*args):
        raise failure()
    monkeypatch.setattr(module, 'capture_process', interrupted)
    with pytest.raises(failure):
        module.run(tmp_path, UNIT, 'b' * 40)
    pipe.close.assert_called_once()


def effective_start(argv):
    return ('{ path=' + argv[0] + ' ; argv[]=' + ' '.join(argv)
            + ' ; ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }')


@pytest.mark.parametrize('damage', ['wrapper', 'extra', 'ignored', 'multiple', *module.AUXILIARY_COMMANDS])
def test_effective_unit_commands_refuse_wrappers_and_auxiliaries(tmp_path, damage, monkeypatch):
    argv = module.supervisor_argv(Path(module.__file__).resolve().parents[1], sys.executable,
                                 tmp_path, UNIT, 'b' * 40, evidence_log=tmp_path / 'service.log')
    monkeypatch.setattr(module, 'validate_evidence_sink', lambda *args: None)
    props = stopped() | {'ExecStart': effective_start(argv)}
    module.validate_launch_commands(props, argv)
    if damage == 'wrapper':
        props['ExecStart'] = effective_start(['/bin/sh', '-c', *argv])
    elif damage == 'extra':
        props['ExecStart'] = effective_start(argv + ['--extra'])
    elif damage == 'ignored':
        props['ExecStart'] = props['ExecStart'].replace('ignore_errors=no', 'ignore_errors=yes')
    elif damage == 'multiple':
        props['ExecStart'] += ' ' + props['ExecStart']
    else:
        props[damage] = effective_start(['/bin/true'])
    monkeypatch.setattr(module, 'require_containment', lambda unit: props)
    monkeypatch.setattr(module, 'verify_source', lambda *args: pytest.fail('Source import admission reached'))
    with pytest.raises(ValueError, match='commands|ExecStart'):
        module.run(tmp_path, UNIT, 'b' * 40)


@pytest.mark.parametrize('damage', ['none', 'null', 'stderr', 'wrong-path', 'no-append', 'other-stderr'])
def test_native_evidence_descriptors_are_pinned(tmp_path, damage):
    import json

    path = tmp_path / 'service.log'
    other = tmp_path / 'other.log'
    path.touch(mode=0o600)
    other.touch(mode=0o600)
    code = '''
import importlib.util, json, pathlib, sys
spec = importlib.util.spec_from_file_location('supervisor', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
props = {'StandardOutput': 'append', 'StandardError': 'inherit'}
if sys.argv[3] == 'null': props['StandardOutput'] = 'null'
if sys.argv[3] == 'stderr': props['StandardError'] = 'null'
try:
    module.validate_evidence_sink(props, pathlib.Path(sys.argv[2]))
except ValueError:
    print(json.dumps({'status': 'refused'}))
else:
    print(json.dumps({'status': 'admitted'}))
'''
    target = other if damage == 'wrong-path' else path
    with path.open('w' if damage == 'no-append' else 'a') as stdout, other.open('a') as stderr:
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code, module.__file__,
                                 str(target), damage], stdout=stdout,
                                stderr=stderr if damage == 'other-stderr' else subprocess.STDOUT,
                                timeout=10, check=True)
    assert result.returncode == 0
    assert json.loads(path.read_text()) == {'status': 'admitted' if damage == 'none' else 'refused'}


def test_source_admission_ignores_replacement_commit_when_checking_checkout(tmp_path):
    from tests.unit.test_spa_artifact_preflight import git
    git(tmp_path, 'init', '-b', 'fixture')
    git(tmp_path, 'config', 'user.name', 'Fixture')
    git(tmp_path, 'config', 'user.email', 'fixture@example.invalid')
    git(tmp_path, 'config', 'core.hooksPath', str(tmp_path / 'absent-hooks'))
    (tmp_path / 'tracked.py').write_text('# approved\n')
    git(tmp_path, 'add', '--', 'tracked.py')
    git(tmp_path, 'commit', '-m', 'fixture approved')
    approved = git(tmp_path, 'rev-parse', 'HEAD')
    (tmp_path / 'tracked.py').write_text('# unapproved replacement\n')
    git(tmp_path, 'add', '--', 'tracked.py')
    git(tmp_path, 'commit', '-m', 'fixture replacement')
    alternate = git(tmp_path, 'rev-parse', 'HEAD')
    git(tmp_path, 'replace', approved, alternate)
    git(tmp_path, 'update-ref', 'refs/heads/fixture', approved)
    # The index/checkout matches the replacement and Git's ordinary diff is
    # empty, but it differs from the raw commit the operator approved.
    assert subprocess.check_output(['git', '-C', str(tmp_path), 'diff', 'HEAD']) == b''
    with pytest.raises(subprocess.CalledProcessError):
        module.verify_source(tmp_path, approved)
