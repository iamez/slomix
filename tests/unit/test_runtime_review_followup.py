"""Native synthetic release CLI admission; no live database or service."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import runtime_game_supervisor as supervisor
from tests.unit.test_release_operator_tool_boundaries import payload


def config(tmp_path, extra=''):
    path = tmp_path / 'approved.env'
    path.write_text('POSTGRES_HOST=fixture\nPOSTGRES_PORT=5432\nPOSTGRES_DATABASE=fixture\n'
                    'POSTGRES_USER=fixture\nPOSTGRES_PASSWORD=\n' + extra)
    path.chmod(0o600)
    return path


@pytest.mark.parametrize('name', ['POSTGRES_HOST', 'POSTGRES_DATABASE', 'PGHOST', 'DB_NAME'])
def test_native_audit_rejects_inherited_target(tmp_path, name):
    root = payload(tmp_path, 'data_plausibility_audit')
    env = config(tmp_path)
    sentinel = tmp_path / 'database-driver-reached'
    (root / 'psycopg2.py').write_text(
        f'def connect(**kwargs):\n    open({str(sentinel)!r}, \"w\").write(\"reached\")\n    raise RuntimeError(\"fixture driver reached\")\n')
    manifest = root / '.slomix-release.json'
    data = json.loads(manifest.read_text())
    data['files']['psycopg2.py'] = hashlib.sha256((root / 'psycopg2.py').read_bytes()).hexdigest()
    manifest.write_text(json.dumps(data))
    result = subprocess.run([sys.executable, '-I', '-B', str(root / 'scripts/data_plausibility_audit.py'), '--json'],
                            env={'PATH': '/usr/bin:/bin', 'SLOMIX_ENV_FILE': str(env), name: 'UNAPPROVED_SENTINEL'},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and result.stdout == ''
    assert json.loads(result.stderr) == {'status': 'refused', 'reason': 'Audit database configuration or connection failed'}
    assert 'UNAPPROVED_SENTINEL' not in result.stderr
    assert not sentinel.exists()


@pytest.mark.parametrize('isolated', [False, True])
def test_native_marker_implicitly_enforces_preflight_release(tmp_path, isolated):
    root = payload(tmp_path, 'dev_schema_preflight')
    env = config(tmp_path)
    shadow = tmp_path / 'shadow'
    shadow.mkdir()
    sentinel = tmp_path / 'unsafe-import'
    (shadow / 'asyncpg.py').write_text(f'open({str(sentinel)!r}, "w").write("unsafe")\n')
    alternate = tmp_path / 'alternate'
    alternate.mkdir()
    (alternate / 'unapproved.sql').write_text('SELECT 1;')
    result = subprocess.run([sys.executable, *(['-I'] if isolated else []),
        str(root / 'scripts/dev_schema_preflight.py'), '--env-file', str(env), '--expected-host', 'fixture',
        '--expected-port', '5432', '--expected-database', 'fixture', '--expected-user', 'fixture',
        '--expected-env-sha256', hashlib.sha256(env.read_bytes()).hexdigest(), '--migrations-dir', str(alternate)],
        env={'PATH': '/usr/bin:/bin', 'SLOMIX_ENV_FILE': str(env), 'PYTHONPATH': str(shadow)},
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and result.stderr == '' and not sentinel.exists()
    report = json.loads(result.stdout)
    assert report == {'clean': False, 'error': ('Release migration/config paths do not match startup contract'
        if isolated else 'Release preflight requires isolated Python (-I)')}
    assert not list(root.rglob('__pycache__'))


@pytest.mark.parametrize('setting', ['POSTGRES_PORT=SECRET_INVALID', 'POSTGRES_PORT=65536',
    'MIGRATION_CONNECT_TIMEOUT_SECONDS=SECRET_INVALID', 'MIGRATION_COMMAND_TIMEOUT_SECONDS=1',
    'MIGRATION_STATEMENT_TIMEOUT_SECONDS=3601', 'MIGRATION_LOCK_TIMEOUT_SECONDS=-1'])
def test_native_migration_invalid_settings_are_redacted_before_command(tmp_path, setting):
    root = payload(tmp_path, 'apply_migrations')
    env = config(tmp_path, setting + '\n')
    result = subprocess.run([sys.executable, '-I', '-B', str(root / 'scripts/apply_migrations.py'), '--status'],
                            env={'PATH': '/usr/bin:/bin', 'SLOMIX_ENV_FILE': str(env)},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and result.stdout == ''
    assert json.loads(result.stderr) == {'status': 'refused', 'reason': 'Release migration configuration verification failed'}


@pytest.mark.parametrize('exception', [EOFError, RuntimeError])
def test_supervisor_redacts_ordinary_channel_and_artifact_errors(tmp_path, monkeypatch, capsys, exception):
    def fail(*args, **kwargs):
        raise exception('PRIVATE_PATH_OR_CHANNEL_CONTENT')
    monkeypatch.setattr(supervisor, 'run', fail)
    assert supervisor.main(['run', '--directory', str(tmp_path), '--unit', 'slomix-et-proof-1234abcd.service',
                            '--commit', 'a' * 40]) == 1
    result = capsys.readouterr()
    assert result.out == ''
    assert json.loads(result.err) == {'status': 'refused_or_failed', 'error_type': exception.__name__,
                                      'shutdown_verified': False, 'evidence_retained': True}


@pytest.mark.parametrize('exception', [KeyboardInterrupt, SystemExit])
def test_supervisor_keeps_control_flow_exceptions(tmp_path, monkeypatch, exception):
    def fail(*args, **kwargs):
        raise exception()
    monkeypatch.setattr(supervisor, 'run', fail)
    with pytest.raises(exception):
        supervisor.main(['run', '--directory', str(tmp_path), '--unit', 'slomix-et-proof-1234abcd.service',
                         '--commit', 'a' * 40])


def test_native_launch_prefix_removes_unknown_application_and_python_environment(tmp_path):
    argv = supervisor.supervisor_argv(Path('/fixture'), Path(sys.executable), tmp_path,
                                     'slomix-et-proof-1234abcd.service', 'a' * 40)
    prefix = argv[:argv.index('-I') + 2]
    result = subprocess.run([*prefix, '-c', 'import json,os;print(json.dumps(dict(os.environ)))'],
        env={'PATH': '/usr/bin:/bin', 'BOT_NAME_REGEX': '^$', 'UNRECOGNIZED_FUTURE_SETTING': 'unsafe',
             'PYTHONPATH': '/unsafe'}, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    actual = json.loads(result.stdout)
    assert actual['PATH'] == '/usr/bin:/bin' and actual['LC_ALL'] == 'C'
    assert set(actual) <= {'PATH', 'LC_ALL', 'LC_CTYPE'}


@pytest.mark.parametrize('field,value', [('Environment', 'BOT_NAME_REGEX=^$'),
                                        ('EnvironmentFiles', '/unapproved/config (ignore_errors=no)')])
def test_effective_unit_rejects_application_environment(monkeypatch, field, value):
    from types import SimpleNamespace

    from tests.unit.test_runtime_game_supervisor import stopped
    values = stopped() | {field: value}
    monkeypatch.setattr(supervisor.subprocess, 'run', lambda *args, **kw: SimpleNamespace(
        stdout='\n'.join(f'{key}={value}' for key, value in values.items())))
    with pytest.raises(ValueError, match='application environment'):
        supervisor.unit_properties('slomix-et-proof-1234abcd.service')


def test_actual_supervisor_environment_rejects_unapproved_application_setting(monkeypatch):
    import os

    from tests.unit.test_runtime_game_supervisor import stopped
    unit = 'slomix-et-proof-1234abcd.service'
    group = '/user.slice/' + unit
    values = stopped() | {'MainPID': str(os.getpid()), 'ActiveState': 'active',
                          'SubState': 'running', 'ControlGroup': group}
    monkeypatch.setattr(supervisor, 'unit_properties', lambda *args: values)
    monkeypatch.setattr(supervisor.Path, 'read_text', lambda *args: '0::' + group + '\n')
    monkeypatch.setattr(supervisor.os, 'environ', {'PATH': '/usr/bin:/bin', 'BOT_NAME_REGEX': '^$'})
    with pytest.raises(ValueError, match='effective application environment'):
        supervisor.require_containment(unit)
