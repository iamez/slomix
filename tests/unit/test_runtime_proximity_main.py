"""Fail-closed DEV configuration, safe default subprocess and shared lifecycle."""

import json
import os
import subprocess
import sys
from unittest.mock import AsyncMock

import pytest

from shared import runtime_proximity_main as module
from shared.runtime_proximity_worker import ProximityWorkerState


@pytest.fixture
def settings(monkeypatch, tmp_path):
    values = dict(BOT_ENVIRONMENT='dev', RUNTIME_PROXIMITY_DEV_HANDOVER_CONFIRMED='true',
                  RUNTIME_PROXIMITY_ROOT=str(tmp_path), RUNTIME_PROXIMITY_SOURCE_ID='fixture',
                  RUNTIME_PROXIMITY_GAMETIMES_DIR=str(tmp_path), POSTGRES_HOST='127.0.0.1',
                  POSTGRES_PORT='5432', POSTGRES_DATABASE='proof', POSTGRES_USER='fixture',
                  POSTGRES_PASSWORD='fake_proximity_config_secret', RUNTIME_PROXIMITY_DB_SCHEMA='proof')
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return values


@pytest.mark.parametrize('name', ['BOT_ENVIRONMENT', 'RUNTIME_PROXIMITY_DEV_HANDOVER_CONFIRMED',
    'RUNTIME_PROXIMITY_ROOT', 'RUNTIME_PROXIMITY_SOURCE_ID', 'RUNTIME_PROXIMITY_GAMETIMES_DIR',
    'POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DATABASE', 'POSTGRES_USER',
    'POSTGRES_PASSWORD', 'RUNTIME_PROXIMITY_DB_SCHEMA'])
def test_required_explicit_configuration(settings, monkeypatch, name):
    monkeypatch.delenv(name)
    with pytest.raises(ValueError):
        module.ProximityProcessConfig.from_environment()


@pytest.mark.parametrize('name,value', [('BOT_ENVIRONMENT', 'production'),
    ('POSTGRES_HOST', 'example.org'), ('POSTGRES_HOST', '192.0.2.1'), ('POSTGRES_HOST', '::1'),
    ('POSTGRES_HOST', '/tmp/a,/tmp/b'), ('POSTGRES_PORT', '0'), ('POSTGRES_PORT', '65536'),
    ('RUNTIME_PROXIMITY_DB_SCHEMA', 'a,b'), ('RUNTIME_PROXIMITY_ROOT', 'relative'),
    ('RUNTIME_PROXIMITY_GAMETIMES_DIR', 'relative'), ('RUNTIME_PROXIMITY_SOURCE_ID', '../bad')])
def test_unsafe_configuration(settings, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        module.ProximityProcessConfig.from_environment()


def test_pool_limits_and_secret_repr(settings):
    config = module.ProximityProcessConfig.from_environment()
    options = config.pool_options()
    assert (options['min_size'], options['max_size']) == (0, 2)
    assert options['timeout'] == 5 and options['command_timeout'] == 10
    assert options['server_settings']['search_path'] == '"proof"'
    assert 'fake_proximity_config_secret' not in repr(config)


def test_default_disabled_subprocess_does_not_need_config():
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('POSTGRES_', 'RUNTIME_PROXIMITY_', 'BOT_ENVIRONMENT'))}
    result = subprocess.run([sys.executable, '-m', 'shared.runtime_proximity_main'],
                            env=env, capture_output=True, text=True, check=True, timeout=10)
    state = json.loads(result.stdout)
    assert state['status'] == 'disabled' and state['last_batch_counts'] is None
    assert result.stderr == ''
    print('Entrypoint proof: fresh process default disabled, no DB config required, one JSON state')


def test_enabled_without_handover_fails_redacted(settings):
    env = dict(os.environ, RUNTIME_PROXIMITY_WORKER_ENABLED='true',
               RUNTIME_PROXIMITY_DEV_HANDOVER_CONFIRMED='false')
    result = subprocess.run([sys.executable, '-m', 'shared.runtime_proximity_main'],
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert json.loads(result.stdout) == dict(component='runtime_proximity', status='failed', error_type='ValueError')
    assert 'fake_proximity_config_secret' not in result.stdout + result.stderr


def test_report_distinguishes_unmeasured_and_empty(capsys):
    module.report(ProximityWorkerState())
    assert json.loads(capsys.readouterr().out)['last_batch_counts'] is None
    module.report(ProximityWorkerState(status='idle', last_batch_counts=(('committed', 0),)))
    assert json.loads(capsys.readouterr().out)['last_batch_counts'] == {'committed': 0}


async def test_resource_factory_failure_still_closes_owned_pool(settings, monkeypatch):
    config = module.ProximityProcessConfig.from_environment()
    pool = type('Pool', (), {})()
    pool.close = AsyncMock()
    pool.terminate = lambda: pytest.fail('should close normally')

    def fail(_pool):
        raise RuntimeError('factory failure')

    from shared import runtime_proximity_isolation

    monkeypatch.setattr(runtime_proximity_isolation.asyncpg, 'create_pool', AsyncMock(return_value=pool))
    monkeypatch.setattr(module.ProximityProcessConfig, 'resource_factory', lambda _self, value: fail(value))
    with pytest.raises(RuntimeError, match='factory failure'):
        await runtime_proximity_isolation._batch(config)  # noqa: SLF001 -- actual child entry cleanup
    pool.close.assert_awaited_once()
