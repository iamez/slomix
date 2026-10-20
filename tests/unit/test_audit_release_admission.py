"""Synthetic audit/preflight admission, with no deployed imports or real DB."""

import builtins
import hashlib
import json
import subprocess
import sys
from unittest.mock import Mock

import pytest

from scripts import data_plausibility_audit as audit
from shared.release_manifest import verify_release
from tests.unit.test_release_operator_tool_boundaries import payload


def inventory(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('isolated', [False, True])
def test_marked_audit_cli_refuses_shadow_or_tampered_source_before_driver(tmp_path, isolated):
    root = payload(tmp_path, 'data_plausibility_audit')
    shadow = tmp_path / 'shadow'
    shadow.mkdir()
    sentinel = tmp_path / 'unapproved-driver-executed'
    (shadow / 'psycopg2.py').write_text(f'open({str(sentinel)!r}, "w").write("unsafe")\n')
    if isolated:
        (root / 'migrations/001_fixture.sql').write_text('SELECT 2;\n')
    before = inventory(root)
    result = subprocess.run([sys.executable, *(['-I'] if isolated else []),
                             str(root / 'scripts/data_plausibility_audit.py'), '--json'],
                            env={'PATH': '/usr/bin:/bin', 'PYTHONPATH': str(shadow),
                                 'SLOMIX_ENV_FILE': str(tmp_path / 'missing-config')},
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 1 and result.stdout == ''
    assert json.loads(result.stderr) == {'status': 'refused', 'reason':
        ('Release audit source verification failed' if isolated else 'Release audit requires isolated Python (-I)')}
    assert not sentinel.exists()
    assert inventory(root) == before


@pytest.mark.parametrize('damage', ['audit', 'round_time', 'missing', 'manifest', 'extra'])
def test_native_audit_rejects_complete_inventory_drift_before_shared_rules(tmp_path, damage):
    root = payload(tmp_path, 'data_plausibility_audit')
    sentinel = tmp_path / 'unapproved-rules-executed'
    if damage == 'audit':
        with (root / 'scripts/data_plausibility_audit.py').open('a') as stream:
            stream.write('\n# Unapproved source bytes\n')
    elif damage == 'round_time':
        with (root / 'shared/round_time.py').open('a') as stream:
            stream.write(f'\nopen({str(sentinel)!r}, "w").write("unsafe")\n')
    elif damage == 'missing':
        (root / 'shared/round_time.py').unlink()
    elif damage == 'manifest':
        (root / '.slomix-release.json').write_text('{}')
    else:
        (root / 'unlisted.py').write_text('# unapproved\n')
    result = subprocess.run([sys.executable, '-I', str(root / 'scripts/data_plausibility_audit.py'), '--json'],
                            env={'PATH': '/usr/bin:/bin', 'SLOMIX_ENV_FILE': str(tmp_path / 'missing-config')},
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 1 and result.stdout == ''
    assert json.loads(result.stderr) == {'status': 'refused', 'reason': 'Release audit source verification failed'}
    assert not sentinel.exists() and not list(root.rglob('__pycache__'))


@pytest.mark.parametrize('entry', ['connection', 'config', 'rules', 'trends', 'run', 'run_trends'])
def test_library_entry_rechecks_manifest_before_config_import_or_cursor(tmp_path, monkeypatch, entry):
    root = payload(tmp_path, 'data_plausibility_audit')
    (root / 'shared/round_time.py').write_text('# tampered bytes\n')
    monkeypatch.setattr(audit, '_REPO_ROOT', root)
    original_load = audit._load_dotenv  # noqa: SLF001 - direct operator-library boundary
    loader = Mock(side_effect=AssertionError('Configuration reached before admission'))
    monkeypatch.setattr(audit, '_load_dotenv', loader)
    conn = Mock()
    conn.cursor.side_effect = AssertionError('Database cursor reached before admission')
    original_import = builtins.__import__
    imports = []
    def importing(name, *args, **kwargs):
        if name == 'psycopg2':
            imports.append(name)
            raise AssertionError('Driver import reached before admission')
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', importing)
    calls = {'connection': audit.get_connection, 'config': lambda: original_load(root),
             'rules': lambda: audit.validate_rules(audit.RULES),
             'trends': lambda: audit.validate_trend_rules(audit.TREND_RULES),
             'run': lambda: audit.run_audit(conn, audit.RULES),
             'run_trends': lambda: audit.run_trend_audit(conn, audit.TREND_RULES)}
    with pytest.raises(ValueError, match='checksum'):
        calls[entry]()
    assert imports == []
    loader.assert_not_called()
    conn.cursor.assert_not_called()


def test_library_main_refuses_source_before_rule_validation_and_connection(tmp_path, monkeypatch, capsys):
    root = payload(tmp_path, 'data_plausibility_audit')
    (root / 'shared/round_time.py').write_text('# tampered\n')
    monkeypatch.setattr(audit, '_REPO_ROOT', root)
    validation = Mock(side_effect=AssertionError('Rule validation reached before source admission'))
    connection = Mock(side_effect=AssertionError('Connection reached before source admission'))
    monkeypatch.setattr(audit, 'validate_rules', validation)
    monkeypatch.setattr(audit, 'get_connection', connection)
    assert audit.main(['--json']) == 1
    validation.assert_not_called()
    connection.assert_not_called()
    result = capsys.readouterr()
    assert json.loads(result.err)['reason'] == 'Release audit source verification failed'


def test_native_library_import_and_empty_audit_leave_payload_unchanged(tmp_path):
    root = payload(tmp_path, 'data_plausibility_audit')
    before = inventory(root)
    code = r'''
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location('audit_fixture', sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
class Cursor:
    def __enter__(self): return self
    def __exit__(self, *args): return False
class Connection:
    def cursor(self): return Cursor()
    def close(self): pass
module.get_connection = lambda: Connection()
module.RULES = []
module.TREND_RULES = []
raise SystemExit(module.main(['--json']))
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(root / 'scripts/data_plausibility_audit.py')],
                            env={'PATH': '/usr/bin:/bin'}, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0 and result.stderr == ''
    assert isinstance(json.loads(result.stdout), dict)
    assert inventory(root) == before
    verify_release(root)


def test_native_release_preflight_without_B_preserves_valid_payload(tmp_path):
    root = payload(tmp_path, 'dev_schema_preflight')
    before = inventory(root)
    result = subprocess.run([sys.executable, '-I', str(root / 'scripts/dev_schema_preflight.py'), '--release-mode',
                             '--env-file', str(tmp_path / 'missing-config'), '--expected-host', 'fixture',
                             '--expected-port', '5432', '--expected-database', 'fixture', '--expected-user', 'fixture'],
                            env={'PATH': '/usr/bin:/bin'}, capture_output=True, text=True, timeout=15)
    # The missing selected environment stops the test before database activity;
    # source integrity must have passed first and remain valid after the import.
    assert result.returncode == 1 and result.stderr == ''
    assert inventory(root) == before
    verify_release(root)
    assert json.loads(result.stdout)['clean'] is False


@pytest.mark.parametrize('tampered', [False, True])
def test_native_sentinel_admits_before_loader_and_preserves_payload_without_B(tmp_path, tampered):
    from pathlib import Path
    source = Path(__file__).resolve().parents[2]
    root = payload(tmp_path, 'data_plausibility_audit')
    if tampered:
        (root / 'shared/round_time.py').write_text('# tampered\n')
    before = inventory(root)
    code = r'''
import importlib.util, json, sys
# Only the unmarked test checkout supplies the existing sentinel caller.
# The copied marked payload remains synthetic and contains no credentials.
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import bot.services.monitor_tasks_mixin as monitor
monitor.__file__ = sys.argv[2] + '/bot/services/monitor_tasks_mixin.py'
original_spec = importlib.util.spec_from_file_location
loaded = []
class Cursor:
    def __enter__(self): return self
    def __exit__(self, *args): return False
class Connection:
    def cursor(self): return Cursor()
    def close(self): pass
def instrumented_spec(name, location, *args, **kwargs):
    spec = original_spec(name, location, *args, **kwargs)
    original_exec = spec.loader.exec_module
    def execute(module):
        loaded.append(name)
        original_exec(module)
        module.get_connection = lambda: Connection()
        module.RULES = []
        module.TREND_RULES = []
    spec.loader.exec_module = execute
    return spec
importlib.util.spec_from_file_location = instrumented_spec
# Force the validator itself to be imported from the synthetic marked payload,
# rather than reuse the unmarked caller's cached namespace module.
import shared
shared.__path__ = [sys.argv[2] + '/shared', sys.argv[1] + '/shared']
sys.modules.pop('shared.release_manifest', None)
if hasattr(shared, 'release_manifest'):
    del shared.release_manifest
sys.dont_write_bytecode = False
try:
    result = monitor._MonitorTasksMixin._run_audit_in_thread()
except ValueError:
    assert sys.argv[3] == 'tampered' and loaded == []
    print(json.dumps({'status': 'refused_before_loader'}))
else:
    assert sys.argv[3] == 'clean' and loaded == ['data_plausibility_audit']
    assert result == {'rules': [], 'trends': []}
    print(json.dumps({'status': 'read_only_fixture_completed'}))
'''
    result = subprocess.run([sys.executable, '-I', '-c', code, str(source), str(root),
                             'tampered' if tampered else 'clean'],
                            env={'PATH': '/usr/bin:/bin', 'BOT_LOG_DIR': str(tmp_path / 'external-logs')},
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.splitlines()[-1]) == {'status':
        'refused_before_loader' if tampered else 'read_only_fixture_completed'}
    assert inventory(root) == before
