"""Native marked migration execution uses synthetic driver failures, never DB."""
import json
import subprocess
import sys

import pytest

from tests.unit.test_release_operator_tool_boundaries import payload

BOOTSTRAP = '''
import asyncpg, pathlib, runpy, sys
kind, sentinel, script, *args = sys.argv[1:]
async def connect(**kwargs):
 pathlib.Path(sentinel).write_text('driver called')
 if kind == 'interrupt': raise KeyboardInterrupt()
 if kind == 'exit': raise SystemExit(73)
 raise RuntimeError('PRIVATE_DATABASE_PASSWORD_AND_PATH')
asyncpg.connect=connect
sys.argv=[script,*args]
runpy.run_path(script,run_name='__main__')
'''


def invoke(tmp_path, *, command=('--status',), extra='', kind='ordinary'):
    root = payload(tmp_path, 'apply_migrations')
    config = tmp_path / 'approved.env'
    config.write_text('POSTGRES_HOST=fixture\nPOSTGRES_PORT=5432\nPOSTGRES_DATABASE=fixture\n'
                      'POSTGRES_USER=fixture\nPOSTGRES_PASSWORD=\n' + extra)
    config.chmod(0o600)
    sentinel = tmp_path / 'driver-called'
    result = subprocess.run([sys.executable, '-I', '-B', '-c', BOOTSTRAP, kind, str(sentinel),
                             str(root / 'scripts/apply_migrations.py'), *command],
                            env={'PATH': '/usr/bin:/bin', 'SLOMIX_ENV_FILE': str(config)},
                            capture_output=True, text=True, timeout=10)
    return result, sentinel


@pytest.mark.parametrize('command', [('--status',), ('--validate',), ('--baseline',),
                                    ('--mark', '001_fixture.sql'), ('--only', '001_fixture.sql'), ()])
def test_native_marked_commands_redact_async_execution_failures(tmp_path, command):
    result, sentinel = invoke(tmp_path, command=command)
    assert sentinel.read_text() == 'driver called'
    assert result.returncode == 1 and result.stdout == ''
    assert json.loads(result.stderr) == {'status': 'refused_or_failed',
        'reason': 'Release migration command could not complete safely', 'partial_commits_possible': True}


@pytest.mark.parametrize('field', ['HOST', 'DATABASE', 'USER'])
@pytest.mark.parametrize('blank', ['', '   '])
def test_native_marked_identity_never_falls_back_from_empty_values(tmp_path, field, blank):
    # dotenv preserves a quoted blank string; supplied DB_* fallback must not
    # override an explicitly selected, but empty, POSTGRES_* value either.
    alias = {'HOST': 'HOST', 'DATABASE': 'NAME', 'USER': 'USER'}[field]
    result, sentinel = invoke(tmp_path, extra=f'POSTGRES_{field}="{blank}"\nDB_{alias}=unapproved-fallback\n')
    assert not sentinel.exists()
    assert result.returncode == 1 and result.stdout == ''
    assert json.loads(result.stderr) == {'status': 'refused',
        'reason': 'Release migration configuration verification failed'}


@pytest.mark.parametrize('kind,code', [('exit', 73), ('interrupt', -2)])
def test_native_marked_execution_preserves_control_flow(tmp_path, kind, code):
    result, sentinel = invoke(tmp_path, kind=kind)
    assert sentinel.read_text() == 'driver called'
    assert result.returncode == code
    assert 'refused_or_failed' not in result.stderr
