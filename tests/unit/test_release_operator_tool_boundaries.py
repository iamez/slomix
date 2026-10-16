"""Offline operator CLI boundaries; never contacts a database or service."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from scripts import apply_migrations as migrations
from scripts import data_plausibility_audit as audit

ROOT = Path(__file__).resolve().parents[2]


def payload(tmp_path, script):
    root = tmp_path / 'release'
    for name in (f'scripts/{script}.py', 'shared/release_manifest.py',
                 'shared/runtime_environment.py', 'shared/round_time.py'):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    sql = root / 'migrations' / '001_fixture.sql'
    sql.parent.mkdir()
    sql.write_text('SELECT 1;\n')
    files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in root.rglob('*') if p.is_file()}
    (root / '.slomix-release.json').write_text(json.dumps(
        {'version': 1, 'source_commit': 'a' * 40, 'files': files}))
    return root


@pytest.mark.parametrize('isolated', [False, True])
def test_release_preflight_cli_never_executes_pythonpath_shadows(tmp_path, isolated):
    root = payload(tmp_path, 'dev_schema_preflight')
    shadow = tmp_path / 'shadow'
    shadow.mkdir()
    sentinel = tmp_path / 'shadow-executed'
    for name in ('asyncpg', 'dotenv'):
        (shadow / f'{name}.py').write_text(f'open({str(sentinel)!r}, "w").write("unsafe")\n')
    # Deliberately break the manifest: -I must ignore the shadow and reach the
    # ordinary redacted source refusal without reading the missing env file.
    (root / 'migrations/001_fixture.sql').write_text('SELECT 2;\n')
    env = {'PATH': '/usr/bin:/bin', 'PYTHONPATH': str(shadow), 'PYTHONDONTWRITEBYTECODE': '1'}
    args = [sys.executable, *(['-I', '-B'] if isolated else []),
            str(root / 'scripts/dev_schema_preflight.py'), '--release-mode',
            '--env-file', str(tmp_path / 'missing-config'), '--expected-host', 'fixture',
            '--expected-port', '5432', '--expected-database', 'fixture', '--expected-user', 'fixture']
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 1 and not sentinel.exists()
    report = json.loads(result.stdout)
    assert report['clean'] is False
    assert report['error'] == ('Preflight could not complete safely' if isolated
                               else 'Release preflight requires isolated Python (-I)')
    assert result.stderr == ''


@pytest.mark.parametrize('damage', ['sql', 'extra', 'manifest', 'directory'])
@pytest.mark.parametrize('boundary', ['inventory', 'config', 'connection'])
async def test_migration_payload_refused_before_config_inventory_or_connection(tmp_path, monkeypatch, damage, boundary):
    root = payload(tmp_path, 'apply_migrations')
    monkeypatch.setattr(migrations, '_REPO_ROOT', root)
    monkeypatch.setattr(migrations, 'MIGRATIONS_DIR', root / 'migrations')
    migrations.verify_migration_source()
    assert [name for name, _ in migrations.discover_migrations()] == ['001_fixture.sql']
    if damage == 'sql':
        (root / 'migrations/001_fixture.sql').write_text('SELECT 2;\n')
    elif damage == 'extra':
        (root / 'migrations/002_unlisted.sql').write_text('SELECT 3;\n')
    elif damage == 'manifest':
        (root / '.slomix-release.json').write_text('{}')
    else:
        monkeypatch.setattr(migrations, 'MIGRATIONS_DIR', tmp_path / 'other-sql')
    loader = Mock(side_effect=AssertionError('Configuration must not be read'))
    driver = AsyncMock(side_effect=AssertionError('Database must not be contacted'))
    monkeypatch.setattr(migrations, 'load_environment', loader)
    monkeypatch.setattr(migrations.asyncpg, 'connect', driver)
    with pytest.raises(ValueError):
        if boundary == 'inventory':
            migrations.discover_migrations()
        elif boundary == 'config':
            migrations.get_connection_kwargs()
        else:
            await migrations.get_connection()
    loader.assert_not_called()
    driver.assert_not_awaited()


def test_tampered_migration_cli_refuses_before_missing_config(tmp_path):
    root = payload(tmp_path, 'apply_migrations')
    (root / 'migrations/001_fixture.sql').write_text('SELECT 2;\n')
    env = {'PATH': '/usr/bin:/bin', 'SLOMIX_ENV_FILE': str(tmp_path / 'missing-config'),
           'PYTHONDONTWRITEBYTECODE': '1'}
    result = subprocess.run([sys.executable, '-I', '-B', str(root / 'scripts/apply_migrations.py'), '--status'],
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 1 and result.stdout == ''
    assert json.loads(result.stderr) == {'status': 'refused',
                                         'reason': 'Release migration source verification failed'}


@pytest.mark.parametrize('destination', ['missing', 'inside', 'alias', 'relative', 'inside-alias-outside'])
def test_release_audit_refuses_output_before_config_or_database(tmp_path, monkeypatch, capsys, destination):
    root = payload(tmp_path, 'data_plausibility_audit')
    monkeypatch.setattr(audit, '_REPO_ROOT', root)
    connect = Mock(side_effect=AssertionError('Database/config must not be read'))
    monkeypatch.setattr(audit, 'get_connection', connect)
    args = []
    if destination == 'inside':
        args = ['--output', str(root / 'docs/report.md')]
    elif destination == 'alias':
        alias = tmp_path / 'alias'
        alias.symlink_to(root, target_is_directory=True)
        args = ['--output', str(alias / 'report.md')]
    elif destination == 'relative':
        args = ['--output', 'report.md']
    elif destination == 'inside-alias-outside':
        (root / 'external-link').symlink_to(tmp_path, target_is_directory=True)
        args = ['--output', str(root / 'external-link/report.md')]
    assert audit.main(args) == 1
    connect.assert_not_called()
    result = capsys.readouterr()
    assert result.out == ''
    assert json.loads(result.err)['status'] == 'refused'


@pytest.mark.parametrize('json_stdout', [False, True])
def test_release_audit_external_output_or_json_is_admitted(tmp_path, monkeypatch, capsys, json_stdout):
    root = payload(tmp_path, 'data_plausibility_audit')
    monkeypatch.setattr(audit, '_REPO_ROOT', root)
    connection = Mock()
    monkeypatch.setattr(audit, 'get_connection', Mock(return_value=connection))
    monkeypatch.setattr(audit, 'run_audit', Mock(return_value=[]))
    monkeypatch.setattr(audit, 'run_trend_audit', Mock(return_value=[]))
    output = tmp_path / 'reports' / 'audit.md'
    assert audit.main(['--json'] if json_stdout else ['--output', str(output)]) == 0
    connection.close.assert_called_once()
    assert output.exists() is not json_stdout
    captured = capsys.readouterr()
    if json_stdout:
        assert isinstance(json.loads(captured.out), dict)
    else:
        assert output.read_text() in captured.out
    assert not (root / 'docs').exists()


@pytest.mark.parametrize('destination', ['missing', 'inside', 'alias'])
def test_release_audit_native_cli_refusal_never_reads_missing_credentials(tmp_path, destination):
    root = payload(tmp_path, 'data_plausibility_audit')
    args = []
    if destination == 'inside':
        args = ['--output', str(root / 'report.md')]
    elif destination == 'alias':
        alias = tmp_path / 'alias'
        alias.symlink_to(root, target_is_directory=True)
        args = ['--output', str(alias / 'report.md')]
    result = subprocess.run([sys.executable, '-I', '-B', str(root / 'scripts/data_plausibility_audit.py'), *args],
                            env={'PATH': '/usr/bin:/bin', 'SLOMIX_ENV_FILE': str(tmp_path / 'missing-config')},
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 1 and result.stdout == ''
    assert json.loads(result.stderr)['status'] == 'refused'


def test_unmarked_audit_retains_legacy_default_destination(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(audit, '_REPO_ROOT', tmp_path)
    connection = Mock()
    monkeypatch.setattr(audit, 'get_connection', Mock(return_value=connection))
    monkeypatch.setattr(audit, 'run_audit', Mock(return_value=[]))
    monkeypatch.setattr(audit, 'run_trend_audit', Mock(return_value=[]))
    assert audit.main([]) == 0
    reports = list((tmp_path / 'docs/research').glob('DATA_PLAUSIBILITY_T1_*.md'))
    assert len(reports) == 1
    assert reports[0].read_text() in capsys.readouterr().out
    connection.close.assert_called_once()


async def test_tampered_migration_connection_gate_precedes_driver_even_with_config_stub(tmp_path, monkeypatch):
    root = payload(tmp_path, 'apply_migrations')
    (root / 'migrations/001_fixture.sql').write_text('SELECT 2;\n')
    monkeypatch.setattr(migrations, '_REPO_ROOT', root)
    monkeypatch.setattr(migrations, 'MIGRATIONS_DIR', root / 'migrations')
    loader = Mock()
    driver = AsyncMock(side_effect=AssertionError('Driver reached with tampered migration payload'))
    monkeypatch.setattr(migrations, 'load_environment', loader)
    monkeypatch.setattr(migrations, 'resolve_env_file', lambda root: root / 'unused.env')
    monkeypatch.setattr(migrations.asyncpg, 'connect', driver)
    with pytest.raises(ValueError, match='checksum'):
        await migrations.get_connection()
    loader.assert_not_called()
    driver.assert_not_awaited()
