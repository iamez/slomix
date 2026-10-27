"""Standalone team process admission and health contracts; no live transport."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from shared import runtime_team_main as module
from shared.runtime_team_worker import TeamWorkerState

FLAGS = ('EVENT_STREAM_ENABLED', 'RUNTIME_TEAM_EVENTS_ENABLED', 'RUNTIME_TEAM_WORKER_ENABLED')


@pytest.fixture
def enabled(monkeypatch):
    for flag in FLAGS:
        monkeypatch.setenv(flag, 'true')
    values = dict(BOT_ENVIRONMENT='dev', RUNTIME_TEAM_DEV_HANDOVER_CONFIRMED='true',
                  POSTGRES_HOST='/tmp/explicit-proof', POSTGRES_PORT='5432',
                  POSTGRES_DATABASE='fixture', POSTGRES_USER='fixture', POSTGRES_PASSWORD='SECRET')
    for key, value in values.items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize('flag', FLAGS)
async def test_disabled_never_reads_configuration_or_creates_pool(enabled, monkeypatch, flag, capsys):
    monkeypatch.delenv(flag)
    monkeypatch.setattr(module, 'database_from_environment', lambda: pytest.fail('configuration touched'))
    serve = AsyncMock()
    monkeypatch.setattr(module, 'serve', serve)
    assert await module.run() == 0
    serve.assert_not_awaited()
    assert json.loads(capsys.readouterr().out)['status'] == 'disabled'


@pytest.mark.parametrize('key,value', [
    ('BOT_ENVIRONMENT', 'production'), ('RUNTIME_TEAM_DEV_HANDOVER_CONFIRMED', 'false'),
    ('POSTGRES_HOST', 'localhost'), ('POSTGRES_HOST', '127.0.0.1'),
    ('POSTGRES_DATABASE', ''), ('POSTGRES_USER', 'bad role'), ('POSTGRES_PORT', '0'),
])
async def test_invalid_target_precedes_pool(enabled, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    serve = AsyncMock()
    monkeypatch.setattr(module, 'serve', serve)
    with pytest.raises(ValueError):
        await module.run()
    serve.assert_not_awaited()


def test_config_explicit_single_lazy_connection_and_no_password_repr(enabled):
    config = module.database_from_environment()
    assert 'SECRET' not in repr(config)
    options = config.pool_options()
    assert options['min_size'] == 0 and options['max_size'] == 1
    assert options['server_settings']['application_name'] == 'slomix-runtime-team-dev'


@pytest.mark.parametrize('failure', [False, True])
async def test_process_owns_signals_and_reuses_lifecycle(enabled, monkeypatch, failure):
    loop = asyncio.get_running_loop()
    installed, removed = [], []
    monkeypatch.setattr(loop, 'add_signal_handler', lambda signum, callback: installed.append((signum, callback)))
    monkeypatch.setattr(loop, 'remove_signal_handler', removed.append)

    async def serve(config, stop, **options):
        assert options['task_prefix'] == 'runtime-team'
        assert options['reporter'] is module.report
        assert not stop.is_set()
        installed[0][1]()
        assert stop.is_set()
        if failure:
            raise RuntimeError('fixture')
        options['worker'].state = TeamWorkerState(status='stopped')

    monkeypatch.setattr(module, 'serve', serve)
    if failure:
        with pytest.raises(RuntimeError):
            await module.run()
    else:
        assert await module.run() == 0
    assert removed == [signum for signum, _ in installed] == [module.signal.SIGTERM, module.signal.SIGINT]


def test_report_distinguishes_starting_and_prior_success(capsys):
    module.report(TeamWorkerState(status='starting'))
    first = json.loads(capsys.readouterr().out)
    assert first['last_page'] is None and first['last_success_age_seconds'] is None
    module.report(TeamWorkerState(status='unavailable', inspected=2, processed=1, pending=1,
                                  last_success_monotonic=0, error_type='ConnectionError'))
    second = json.loads(capsys.readouterr().out)
    assert second['status'] == 'unavailable' and second['error_type'] == 'ConnectionError'
    assert second['last_page']['processed'] == 1 and second['source_acknowledged'] is False


def test_main_redacts_failure(enabled, monkeypatch, capsys):
    async def fail():
        raise ValueError('SECRET private connection details')
    monkeypatch.setattr(module, 'run', fail)
    assert module.main() == 1
    output = capsys.readouterr()
    assert 'SECRET' not in output.out + output.err
    assert json.loads(output.out)['error_type'] == 'ValueError'
