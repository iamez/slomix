"""Native audit post-connect failures are synthetic; no real DB connection."""
import json
import subprocess
import sys

import pytest

from tests.unit.test_release_operator_tool_boundaries import payload

BOOTSTRAP = '''
import pathlib,psycopg2,runpy,sys
kind,events,script=sys.argv[1:]
def record(value):
 with open(events,'a') as stream: stream.write(value+'\\n')
class Cursor:
 def __init__(self): self.calls=0
 def __enter__(self): return self
 def __exit__(self,*args): return False
 def execute(self,*args):
  record('execute')
  self.calls+=1
  if kind=='query': raise RuntimeError('PRIVATE_QUERY_CONTENT')
 def fetchone(self): return (0,) if self.calls%2 else (0,0,0)
 def fetchall(self): return []
class Connection:
 def set_session(self,**kwargs): record('readonly-session')
 def cursor(self):
  record('cursor')
  if kind=='cursor': raise RuntimeError('PRIVATE_CURSOR_PATH')
  if kind in {'interrupt','interrupt-close'}: raise KeyboardInterrupt()
  if kind in {'exit','exit-close'}: raise SystemExit(73)
  return Cursor()
 def close(self):
  record('close')
  if kind in {'close','interrupt-close','exit-close'}: raise RuntimeError('PRIVATE_CLOSE_PATH')
def connect(**kwargs):
 record('connect')
 return Connection()
psycopg2.connect=connect
sys.argv=[script,'--json']
if kind=='rules':
 namespace=runpy.run_path(script,run_name='audit_fixture')
 namespace['main'].__globals__['RULES']=[namespace['RULES'][0],namespace['RULES'][0]]
 raise SystemExit(namespace['main'](['--json']))
runpy.run_path(script,run_name='__main__')
'''


def invoke(tmp_path, kind, marked=True):
    root = payload(tmp_path, 'data_plausibility_audit')
    if not marked:
        (root / '.slomix-release.json').unlink()
    config = tmp_path / 'approved.env'
    config.write_text('POSTGRES_HOST=fixture\nPOSTGRES_PORT=5432\nPOSTGRES_DATABASE=fixture\n'
                      'POSTGRES_USER=fixture\nPOSTGRES_PASSWORD=fixture\n')
    config.chmod(0o600)
    events = tmp_path / 'driver-events'
    result = subprocess.run([sys.executable, '-I', '-B', '-c', BOOTSTRAP, kind, str(events),
                            str(root / 'scripts/data_plausibility_audit.py')],
                           env={'PATH': '/usr/bin:/bin', 'SLOMIX_ENV_FILE': str(config)},
                           capture_output=True, text=True, timeout=10)
    return result, events.read_text().splitlines() if events.exists() else []


@pytest.mark.parametrize('kind', ['cursor', 'query', 'close', 'rules'])
@pytest.mark.parametrize('marked', [False, True])
def test_native_audit_runtime_redaction_preserves_legacy_errors(tmp_path, kind, marked):
    result, events = invoke(tmp_path, kind, marked)
    assert result.returncode == 1 and result.stdout == ''
    if kind == 'rules':
        assert events == []
    else:
        assert events[:2] == ['connect', 'readonly-session'] and events[-1] == 'close'
        if kind in {'query', 'close'}:
            assert 'execute' in events
    if marked:
        assert json.loads(result.stderr) == {'status': 'refused',
            'reason': 'Release audit execution could not complete safely'}
    else:
        assert 'Traceback' in result.stderr
        assert 'PRIVATE_' in result.stderr if kind != 'rules' else 'Duplicate rule names' in result.stderr


@pytest.mark.parametrize('kind,code', [('interrupt', -2), ('exit', 73),
                                      ('interrupt-close', -2), ('exit-close', 73)])
def test_native_audit_control_flow_survives_cleanup_failure(tmp_path, kind, code):
    result, events = invoke(tmp_path, kind)
    assert result.returncode == code and events[-1] == 'close'
    assert 'Release audit execution' not in result.stderr
