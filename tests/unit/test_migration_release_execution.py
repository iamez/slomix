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

INNER_BOOTSTRAP = '''
import asyncpg,pathlib,runpy,sys
kind,events,script,*args=sys.argv[1:]
def record(value):
 with open(events,'a') as stream: stream.write(value+'\\n')
class Transaction:
 async def __aenter__(self): record('transaction-start')
 async def __aexit__(self,*args): record('transaction-end')
class Connection:
 def transaction(self): return Transaction()
 async def fetch(self,*args): return []
 async def fetchval(self,sql,*args): return 'pg_try_advisory_lock' in sql
 async def execute(self,sql,*args):
  if sql.strip() == 'SELECT 1;':
   record('migration-execute')
   if kind == 'execute': raise RuntimeError('PRIVATE_DDL_ERROR_CONTENT')
  if 'FALSE)' in sql: record('failure-recorded')
  return 'OK'
 async def close(self):
  record('close')
  if kind == 'close': raise RuntimeError('PRIVATE_CLOSE_ERROR_CONTENT')
async def connect(**kwargs): return Connection()
asyncpg.connect=connect
sys.argv=[script,*args]
runpy.run_path(script,run_name='__main__')
'''


@pytest.mark.parametrize('kind', ['execute', 'close', 'rejected'])
@pytest.mark.parametrize('marked', [False, True])
def test_native_inner_migration_and_close_failures_obey_release_redaction(tmp_path, kind, marked):
    import hashlib
    root = payload(tmp_path, 'apply_migrations')
    marker = root / '.slomix-release.json'
    if kind == 'rejected':
        sql = root / 'migrations/001_fixture.sql'
        sql.write_text('CREATE INDEX CONCURRENTLY fixture ON fixture(id);\n')
        manifest = json.loads(marker.read_text())
        manifest['files']['migrations/001_fixture.sql'] = hashlib.sha256(sql.read_bytes()).hexdigest()
        marker.write_text(json.dumps(manifest))
    if not marked:
        marker.unlink()
    config = tmp_path / 'approved.env'
    config.write_text('POSTGRES_HOST=fixture\nPOSTGRES_PORT=5432\nPOSTGRES_DATABASE=fixture\n'
                      'POSTGRES_USER=fixture\nPOSTGRES_PASSWORD=\n')
    config.chmod(0o600)
    events = tmp_path / 'driver-events'
    result = subprocess.run([sys.executable, '-I', '-B', '-c', INNER_BOOTSTRAP, kind, str(events),
                             str(root / 'scripts/apply_migrations.py')],
                            env={'PATH': '/usr/bin:/bin', 'SLOMIX_ENV_FILE': str(config)},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    measured = events.read_text().splitlines()
    assert measured[-1] == 'close'
    if kind == 'execute':
        assert 'migration-execute' in measured and 'failure-recorded' in measured
    if kind == 'close':
        assert 'migration-execute' in measured
    if marked:
        assert 'PRIVATE_' not in result.stdout + result.stderr
        assert json.loads(result.stderr) == {'status': 'refused_or_failed',
            'reason': 'Release migration command could not complete safely', 'partial_commits_possible': True}
    elif kind == 'execute':
        assert 'PRIVATE_DDL_ERROR_CONTENT' in result.stdout and 'FAILED' in result.stdout
    elif kind == 'rejected':
        assert 'REJECTED' in result.stdout and 'CONCURRENTLY' in result.stdout
    else:
        assert 'PRIVATE_CLOSE_ERROR_CONTENT' in result.stderr and 'Traceback' in result.stderr
