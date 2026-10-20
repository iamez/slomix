"""Fail-closed DEV readiness without starting a service or browser."""
import json
from pathlib import Path

import pytest

from scripts import dev_verify_health as gate


@pytest.fixture
def ready(monkeypatch):
    run = Path('/synthetic/run')
    state = {'etlegacy-bot': {'pid': 101, 'active': 'active', 'cwd': str(run)},
             'etlegacy-web': {'pid': 102, 'active': 'active', 'cwd': str(run / 'website')}}
    previous = {'etlegacy-bot': {'pid': 1}, 'etlegacy-web': {'pid': 2}, '_captured_at': 0}
    monkeypatch.setattr(gate, 'units', lambda root: state)
    monkeypatch.setattr(gate.os, 'readlink', lambda path: str(run / 'website') if '/102/' in path else str(run))
    payloads = {'/health': {'status': 'ok', 'database': 'ok'},
                '/api/build': {'revision': 'a' * 40, 'started_at': '2026-01-01T00:00:00+00:00'}}
    monkeypatch.setattr(gate, 'read_json', lambda path: payloads[path])
    return run, state, previous, payloads


def test_current_healthy_build_and_fresh_processes_pass(ready):
    run, state, previous, _ = ready
    assert gate.check(run, 'a' * 40, previous) == state


@pytest.mark.parametrize('failure', ['inactive', 'zero', 'stale', 'cwd', 'database', 'http_body',
                                    'revision', 'stale_build', 'naive_build'])
def test_failure_or_stale_process_never_reports_success(ready, monkeypatch, failure):
    run, state, previous, payloads = ready
    if failure == 'inactive':
        state['etlegacy-bot']['active'] = 'failed'
    elif failure == 'zero':
        state['etlegacy-web']['pid'] = 0
    elif failure == 'stale':
        previous['etlegacy-web']['pid'] = state['etlegacy-web']['pid']
    elif failure == 'cwd':
        monkeypatch.setattr(gate.os, 'readlink', lambda path: '/wrong')
    elif failure == 'database':
        payloads['/health']['database'] = 'error'
    elif failure == 'http_body':
        payloads['/health']['status'] = 'error'
    elif failure == 'revision':
        payloads['/api/build']['revision'] = 'b' * 40
    elif failure == 'stale_build':
        previous['_captured_at'] = gate.time.time()
    else:
        payloads['/api/build']['started_at'] = '2026-01-01T00:00:00'
    with pytest.raises(ValueError):
        gate.check(run, 'a' * 40, previous)


@pytest.mark.parametrize('extra', ['Environment=POSTGRES_PASSWORD=never-print-this',
                                 'EnvironmentFiles=/secret', 'WorkingDirectory=/wrong',
                                 'PassEnvironment=DATABASE_TYPE', 'User=root',
                                 'ExecStart={ path=/bin/true ; argv[]=/bin/true ; ignore_errors=no ; pid=0 }'])
def test_unit_override_is_rejected_without_exposing_values(monkeypatch, extra):
    output = 'LoadState=loaded\nActiveState=active\nMainPID=101\nWorkingDirectory=/synthetic/run\n'
    output += ('User=samba\nExecStart={ path=/synthetic/run/venv/bin/python3 ; '
               'argv[]=/synthetic/run/venv/bin/python3 bot/ultimate_bot.py ; ignore_errors=no ; pid=0 }\n')
    monkeypatch.setattr(gate.subprocess, 'check_output', lambda *args, **kwargs: output + extra)
    with pytest.raises(ValueError) as error:
        gate.units(Path('/synthetic/run'))
    assert 'never-print-this' not in str(error.value)


def test_cli_deadline_returns_failure_not_success(ready, tmp_path, monkeypatch, capsys):
    _, state, previous, _ = ready
    state['etlegacy-bot']['active'] = 'failed'
    path = tmp_path / 'previous.json'
    path.write_text(json.dumps(previous))
    times = iter([0, 46])
    monkeypatch.setattr(gate.time, 'monotonic', lambda: next(times))
    assert gate.main(['verify', '--run', str(tmp_path), '--target', 'a' * 40,
                      '--previous', str(path)]) == 1
    assert json.loads(capsys.readouterr().out)['healthy'] is False


@pytest.mark.parametrize('metadata', [
    {},  # Older systemd / MemoryPressureWatch=skip.
    dict.fromkeys(('LC_PAPER', 'LC_NAME', 'LC_ADDRESS', 'LC_TELEPHONE',
                   'LC_MEASUREMENT', 'LC_IDENTIFICATION'), 'C'),
    {'MEMORY_PRESSURE_WATCH': '/dev/null'},  # MemoryPressureWatch=no.
    {'MEMORY_PRESSURE_WATCH': '/sys/fs/cgroup/system.slice/example.service/memory.pressure',
     'MEMORY_PRESSURE_WRITE': 'c29tZSAyMDAwMDAgMjAwMDAwMAA='},
])
@pytest.mark.parametrize('extra', [None, 'UNAPPROVED_APP_SETTING', 'MEMORY_PRESSURE_UNKNOWN',
                                 'PYTHONPATH', 'PYTHONHOME', 'LD_PRELOAD',
                                 'LD_LIBRARY_PATH', 'LD_AUDIT', 'APP_MODE', 'LC_UNKNOWN'])
def test_actual_process_pressure_metadata_preserves_environment_guards(
        tmp_path, monkeypatch, metadata, extra):
    """Read real /proc exec identity; service, dotenv and HTTP are isolated doubles."""
    import subprocess
    import sys

    bootstrap = {'SLOMIX_ENV_FILE': str(tmp_path / 'approved.env')}
    environment = {**bootstrap, **metadata}
    if extra is not None:
        # Empty loader paths are harmless to the child but still forbidden by the gate.
        environment[extra] = ''
    argv = [sys.executable, '-B', '-S', '-c',
            'import sys; print("ready", flush=True); sys.stdin.buffer.read()']
    with subprocess.Popen(argv, cwd=tmp_path, env=environment, stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child:
        try:
            assert child.stdout.readline() == b'ready\n'
            state = {'etlegacy-bot': {'pid': child.pid, 'active': 'active', 'cwd': str(tmp_path)}}
            specification = {'argv': argv, 'environment': bootstrap, 'env_sha256': 'fixture',
                             'python_sha256': gate.file_hash(Path(f'/proc/{child.pid}/exe'))}
            contract = {'revision': 'a' * 40, 'services': {'etlegacy-bot': specification}}
            monkeypatch.setattr(gate, 'units', lambda *args: state)
            monkeypatch.setattr(gate, 'bot_ready', lambda *args: None)
            monkeypatch.setattr(gate, 'read_external_environment',
                                lambda *args, **kwargs: {'APP_MODE': 'approved'})
            payloads = {'/health': {'status': 'ok', 'database': 'ok'},
                        '/api/build': {'revision': 'a' * 40,
                                       'started_at': '2026-01-01T00:00:00+00:00'}}
            monkeypatch.setattr(gate, 'read_json', lambda path: payloads[path])
            previous = {'etlegacy-bot': {'pid': 0}, '_captured_at': 0}
            if extra is None:
                assert gate.check(tmp_path, 'a' * 40, previous, contract) == state
            else:
                with pytest.raises(ValueError, match='running configuration differs'):
                    gate.check(tmp_path, 'a' * 40, previous, contract)
        finally:
            child.communicate(timeout=5)
        assert child.returncode == 0
