"""Actual DEV lifecycle/resources/checkpoint against the private proof database."""

import asyncio

import asyncpg
import pytest

from shared.runtime_proximity_main import ProximityProcessConfig, serve
from shared.runtime_proximity_worker import RuntimeProximityWorker
from tests.integration.test_runtime_events_pg import connection_options, journal_db  # noqa: F401


@pytest.mark.asyncio
async def test_real_lifecycle_releases_pool_after_checkpoint(journal_db, tmp_path):  # noqa: F811
    owner, _ = journal_db
    options = connection_options()
    config = ProximityProcessConfig(
        tmp_path, 'fixture', tmp_path, options['host'], options.get('port', 5432),
        await owner.fetchval('SELECT current_database()'), await owner.fetchval('SELECT current_user'),
        await owner.fetchval('SELECT current_schema()'), options.get('password', ''),
    )
    tmp_path.chmod(0o700)
    (tmp_path / ('1' * 32)).mkdir(mode=0o700)
    worker = RuntimeProximityWorker(tmp_path, source_id='fixture', gametimes_dir=tmp_path, enabled=True)
    stop = asyncio.Event()
    states, pools = [], []

    async def pool_factory(**kwargs):
        pool = await asyncpg.create_pool(**kwargs)
        pools.append(pool)
        return pool

    def report(state):
        states.append(state)
        if state.last_success_monotonic is not None:
            stop.set()

    await asyncio.wait_for(serve(
        config, stop, worker=worker, resource_factory=config.resource_factory,
        pool_factory=pool_factory, reporter=report, health_seconds=0.01,
        task_prefix='runtime-proximity-proof',
    ), 10)
    assert pools[0].is_closing()
    assert states[0].status == 'starting' and states[-1].status == 'stopped'
    assert dict(states[-1].last_batch_counts)['deferred'] == 1
    assert (tmp_path / '.proximity-cursor.json').is_file()
    assert len(list(tmp_path.iterdir())) == 2
    print('Native lifecycle proof: two-connection pool, deferred generation, persisted cursor, stopped worker/closed pool')
