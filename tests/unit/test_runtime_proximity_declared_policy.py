"""Explicit declaration policy survives real worker/checkpoint/batch wrappers."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock

import pytest

from shared import runtime_proximity_batch as batch
from shared import runtime_proximity_cursor as cursor
from shared import runtime_proximity_isolation as isolated
from shared.runtime_proximity_config import ProximityProcessConfig
from shared.runtime_proximity_queue import ProximityQueueResult
from shared.runtime_proximity_worker import RuntimeProximityWorker
from tests.unit.test_runtime_proximity_batch import SOURCE, populate
from tests.unit.test_runtime_proximity_main import settings  # noqa: F401


@pytest.mark.parametrize('value,expected', [(None, False), ('false', False), ('true', True)])
def test_environment_policy_is_explicit_and_default_off(settings, monkeypatch, value, expected):  # noqa: F811
    key = 'RUNTIME_PROXIMITY_DECLARED_MAPPING_ENABLED'
    if value is None:
        monkeypatch.delenv(key, raising=False)
    else:
        monkeypatch.setenv(key, value)
    assert ProximityProcessConfig.from_environment().allow_declared_mapping is expected


@pytest.mark.parametrize('value', ['', 'TRUE', '1', 'yes'])
def test_ambiguous_environment_policy_is_refused(settings, monkeypatch, value):  # noqa: F811
    monkeypatch.setenv('RUNTIME_PROXIMITY_DECLARED_MAPPING_ENABLED', value)
    with pytest.raises(ValueError, match='mapping policy'):
        ProximityProcessConfig.from_environment()


@pytest.mark.parametrize('entrypoint', ['worker', 'isolated'])
@pytest.mark.parametrize('enabled', [False, True])
async def test_policy_reaches_queue_through_real_wrappers(tmp_path, monkeypatch, entrypoint, enabled):
    populate(tmp_path, [1])
    stop = asyncio.Event()
    observed = []

    async def queue(directory, **kwargs):
        observed.append((directory.name, kwargs.get('allow_declared_mapping', False)))
        stop.set()
        return ProximityQueueResult('deferred', 'missing_manifest')

    @asynccontextmanager
    async def resources():
        yield None, None

    monkeypatch.setattr(batch, 'process_proximity_once', queue)
    if entrypoint == 'worker':
        subject = RuntimeProximityWorker(tmp_path, source_id=SOURCE, gametimes_dir=tmp_path,
                                        enabled=True, allow_declared_mapping=enabled)
        await asyncio.wait_for(subject.run(resources, stop), 2)
        assert subject.state.status == 'stopped'
    else:
        pool = Mock(close=AsyncMock())
        monkeypatch.setattr(isolated.asyncpg, 'create_pool', AsyncMock(return_value=pool))
        monkeypatch.setattr(ProximityProcessConfig, 'resource_factory', lambda self, pool: resources)
        config = ProximityProcessConfig(tmp_path, SOURCE, tmp_path, '127.0.0.1', 5432,
                                        'proof', 'fixture', 'public', 'synthetic',
                                        allow_declared_mapping=enabled)
        await isolated._batch(config)  # noqa: SLF001 -- actual child entry boundary, no process/server spawned.
        pool.close.assert_awaited_once()
    assert observed == [(f'{1:032x}', enabled)]
    assert (tmp_path / '.proximity-cursor.json').is_file()
    print(f'Policy forwarding proof: {entrypoint} -> checkpoint -> batch -> queue: {enabled}')


@pytest.mark.parametrize('entrypoint', ['worker', 'checkpoint', 'batch'])
async def test_nonboolean_policy_refuses_before_work(tmp_path, entrypoint):
    tmp_path.chmod(0o700)
    options = dict(source_id=SOURCE, gametimes_dir=tmp_path, allow_declared_mapping=1)
    with pytest.raises(ValueError, match='mapping policy'):
        if entrypoint == 'worker':
            RuntimeProximityWorker(tmp_path, **options)
        else:
            call = (cursor.process_proximity_checkpointed_batch if entrypoint == 'checkpoint'
                    else batch.process_proximity_batch)
            await call(tmp_path, now=1000, adapter=None, observer=None, **options)
    assert not list(tmp_path.iterdir())
