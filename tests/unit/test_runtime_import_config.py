"""External target refusal before pool creation and explicit TCP composition."""

import hashlib
import json
import os
from unittest.mock import AsyncMock

import pytest

from bot import runtime_import_cli as cli
from shared.runtime_import_config import load_import_database
from shared.runtime_import_pool import ImportDatabaseConfig, TcpImportDatabaseConfig
from tests.unit.test_runtime_import_cli import arguments

TARGET = ('192.168.64.116', 5432, 'fixture_db', 'fixture_role')
SENTINEL = 'synthetic-config-sentinel'


def config_file(tmp_path, **changes):
    values = dict(DATABASE_TYPE='postgresql', POSTGRES_HOST=TARGET[0], POSTGRES_PORT='5432',
                  POSTGRES_DATABASE=TARGET[2], POSTGRES_USER=TARGET[3],
                  POSTGRES_PASSWORD=SENTINEL, BOT_ENVIRONMENT='dev')
    values.update(changes)
    raw = ''.join(f'{key}={value}\n' for key, value in values.items()).encode()
    path = tmp_path / 'explicit.env'
    path.write_bytes(raw)
    path.chmod(0o600)
    return path, hashlib.sha256(raw).hexdigest()


def read(path, digest, **options):
    return load_import_database(path, expected_digest=digest, expected_target=TARGET,
                                environment={}, **options)


def tcp_arguments(tmp_path, path, digest):
    args = arguments(tmp_path)
    for option in ('--socket', '--database', '--user'):
        index = args.index(option)
        del args[index:index + 2]
    return args + ['--env-file', str(path), '--config-sha256', digest,
                   '--expected-target', *(str(value) for value in TARGET), '--writer-handover-confirmed']


def test_exact_private_file_and_target_do_not_mutate_environment(tmp_path):
    path, digest = config_file(tmp_path)
    before = dict(os.environ)
    result = read(path, digest)
    assert dict(os.environ) == before
    assert isinstance(result, TcpImportDatabaseConfig)
    assert result.host == TARGET[0] and result.port == TARGET[1]
    assert SENTINEL not in repr(result)
    assert result.pool_options()['password'] == SENTINEL
    assert result.pool_options()['ssl'] is False
    assert result.pool_options()['max_size'] == 1


@pytest.mark.parametrize('target', [
    ('127.0.0.1', 5432, 'fixture_db', 'fixture_role'),
    ('192.168.64.116', 5433, 'fixture_db', 'fixture_role'),
    ('192.168.64.116', 5432, 'different_db', 'fixture_role'),
    ('192.168.64.116', 5432, 'fixture_db', 'other_role'),
])
def test_independent_target_must_match_all_four_fields(tmp_path, target):
    path, digest = config_file(tmp_path)
    with pytest.raises(ValueError, match='independent operator expectation'):
        load_import_database(path, expected_digest=digest, expected_target=target, environment={})


@pytest.mark.parametrize('changes', [
    {'POSTGRES_PASSWORD': ''}, {'POSTGRES_PASSWORD': '${AMBIENT_PASSWORD}'},
    {'POSTGRES_PORT': '5432x'}, {'DATABASE_TYPE': 'sqlite'}, {'PGSERVICE': 'other'},
    {'POSTGRES_SSL_MODE': 'require'}, {'POSTGRES_SSL_MODE': 'verify-full'},
    {'POSTGRES_DSN': 'postgres://unapproved'}, {'POSTGRES_HOST': ''},
])
def test_incomplete_interpolated_or_ambiguous_configuration_is_refused(tmp_path, changes):
    path, digest = config_file(tmp_path, **changes)
    with pytest.raises(ValueError):
        read(path, digest)


@pytest.mark.parametrize('key', ['PGHOST', 'PGPASSWORD', 'PGPASSFILE', 'PGSERVICE', 'POSTGRES_HOST',
                                 'DATABASE_URL', 'DB_PASSWORD', 'PYTHONPATH', 'PYTHONHOME',
                                 'LD_PRELOAD', 'LD_LIBRARY_PATH', 'LD_AUDIT', 'BOT_ENVIRONMENT'])
def test_inherited_shadow_settings_are_refused_even_if_equal(tmp_path, key):
    path, digest = config_file(tmp_path)
    with pytest.raises(ValueError, match='Inherited environment'):
        load_import_database(path, expected_digest=digest, expected_target=TARGET,
                             environment={key: 'dev'})


def test_legacy_full_config_cannot_change_fixed_pool_budgets(tmp_path):
    path, digest = config_file(tmp_path, DB_PATH='legacy-only.db', POSTGRES_MIN_POOL='5',
                               POSTGRES_MAX_POOL='20', POSTGRES_SSL_MODE='disable')
    options = read(path, digest).pool_options()
    assert options['min_size'] == 0 and options['max_size'] == 1
    assert options['database'] == TARGET[2]


@pytest.mark.parametrize('changes', [{'password': ''}, {'password': None}, {'port': True},
                                    {'port': 0}, {'database': 'bad;db'}, {'user': ''}])
def test_tcp_rejects_invalid_connection_values(changes):
    values = dict(host=TARGET[0], database=TARGET[2], user=TARGET[3], password=SENTINEL)
    values.update(changes)
    with pytest.raises(ValueError):
        TcpImportDatabaseConfig(**values)


@pytest.mark.parametrize('invalid', ['digest', 'contents', 'duplicate', 'syntax', 'encoding',
                                   'public', 'symlink', 'relative', 'oversized'])
def test_unapproved_config_bytes_or_paths_are_refused(tmp_path, monkeypatch, invalid):
    path, digest = config_file(tmp_path)
    if invalid == 'digest':
        digest = 'a' * 64
    elif invalid in {'contents', 'duplicate', 'syntax', 'encoding', 'oversized'}:
        additions = {'contents': b'#changed\n', 'duplicate': b'POSTGRES_USER=other\n',
                     'syntax': b'bad="unclosed\n', 'encoding': b'\xff', 'oversized': b'x' * (1024 * 1024)}
        raw = path.read_bytes() + additions[invalid]
        path.write_bytes(raw)
        if invalid != 'contents':
            digest = hashlib.sha256(raw).hexdigest()
    elif invalid == 'public':
        path.chmod(0o644)
    elif invalid == 'symlink':
        alias = tmp_path / 'alias.env'
        alias.symlink_to(path)
        path = alias
    elif invalid == 'relative':
        monkeypatch.chdir(tmp_path)
        path = path.name
    with pytest.raises(ValueError):
        read(path, digest)


@pytest.mark.parametrize('host', ['localhost', '127.0.0.1', '192.168.64.116', '::1', 'fd12::1'])
def test_explicit_tcp_hosts_preserve_unix_guard(host):
    result = TcpImportDatabaseConfig(host, TARGET[2], TARGET[3], 'synthetic-only')
    assert result.pool_options()['host'] == host
    with pytest.raises(ValueError, match='Unix socket'):
        ImportDatabaseConfig(host, TARGET[2], TARGET[3], '')


@pytest.mark.parametrize('host', ['db.example', '127.0.0.1,192.168.64.116', 'postgres://localhost',
                                  '/tmp/socket', '8.8.8.8', '0.0.0.0', '224.0.0.1',  # noqa: S104 - refusal input
                                  '169.254.1.2', 'fe80::1', 'fd12::1%eth0', None, 1])
def test_tcp_does_not_admit_implicit_or_public_targets(host):
    with pytest.raises(ValueError):
        TcpImportDatabaseConfig(host, TARGET[2], TARGET[3], 'synthetic-only')


def clear_database_environment(monkeypatch):
    for key in list(os.environ):
        if key.startswith(('POSTGRES_', 'DB_', 'PG', 'DATABASE_')) or key in {
            'PYTHONPATH', 'PYTHONHOME', 'LD_PRELOAD', 'LD_LIBRARY_PATH', 'LD_AUDIT', 'BOT_ENVIRONMENT',
        }:
            monkeypatch.delenv(key)


def test_tcp_cli_passes_pinned_target_to_existing_exclusive_batch(tmp_path, monkeypatch, capsys):
    clear_database_environment(monkeypatch)
    path, digest = config_file(tmp_path)
    run = AsyncMock(return_value=((True, 'ok'), (True, 'ok')))
    monkeypatch.setattr(cli, 'run_exclusive_import_batch', run)
    assert cli.main(tcp_arguments(tmp_path, path, digest)) == 0
    database, jobs = run.await_args.args
    assert isinstance(database, TcpImportDatabaseConfig)
    assert database.host == TARGET[0] and database.password == SENTINEL
    assert len(jobs) == 2 and jobs[1].first == jobs[0].current
    assert run.await_args.kwargs['lock_directory'] == tmp_path / 'lock'
    assert json.loads(capsys.readouterr().out)['source_acknowledged'] is False


@pytest.mark.parametrize('change', ['digest', 'target', 'ambient', 'password'])
def test_cli_invalid_config_never_enters_batch(tmp_path, monkeypatch, capsys, change):
    clear_database_environment(monkeypatch)
    path, digest = config_file(tmp_path, **({'POSTGRES_PASSWORD': ''} if change == 'password' else {}))
    args = tcp_arguments(tmp_path, path, digest)
    if change == 'digest':
        args[args.index('--config-sha256') + 1] = '0' * 64
    elif change == 'target':
        args[args.index('--expected-target') + 1] = '127.0.0.1'
    elif change == 'ambient':
        monkeypatch.setenv('PGPASSWORD', 'synthetic-ambient-sentinel')
    run = AsyncMock()
    monkeypatch.setattr(cli, 'run_exclusive_import_batch', run)
    assert cli.main(args) == 1
    run.assert_not_awaited()
    output = capsys.readouterr()
    assert 'sentinel' not in output.out + output.err
    assert json.loads(output.out)['status'] == 'failed'
    assert not (tmp_path / 'lock').exists()


@pytest.mark.parametrize('missing', ['--config-sha256', '--expected-target', '--writer-handover-confirmed'])
def test_tcp_requires_all_explicit_authority_arguments(tmp_path, missing):
    path, digest = config_file(tmp_path)
    args = tcp_arguments(tmp_path, path, digest)
    start = args.index(missing)
    length = 1 if missing == '--writer-handover-confirmed' else 5 if missing == '--expected-target' else 2
    del args[start:start + length]
    with pytest.raises(SystemExit) as exc:
        cli.main(args)
    assert exc.value.code == 2
