"""A real disconnect during pool release must resume committed effects once."""

import asyncio
from contextlib import asynccontextmanager

import asyncpg
import pytest

from bot.runtime_completed_import import import_completed_round
from shared.runtime_cache_consumer import CONSUMER as CACHE_CONSUMER
from shared.runtime_cache_worker import RuntimeCacheWorker
from shared.runtime_team_consumer import CONSUMER as TEAM_CONSUMER
from shared.runtime_team_worker import RuntimeTeamWorker
from tests.integration.test_runtime_events_pg import connection_options
from tests.integration.test_runtime_full_import_pg import completed_pair
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db

full_import_db = _full_import_db


@pytest.mark.parametrize('component', ['cache', 'team'])
async def test_release_disconnect_retries_committed_effect_without_duplicate(full_import_db, tmp_path,
                                                                           monkeypatch, component):
    manager, observer = full_import_db
    manager.defer_team_assignment = True
    sources = completed_pair(tmp_path, balanced=True)
    for index, source in enumerate(sources):
        assert (await import_completed_round(manager, source, first=sources[0] if index else None))[0]
    for name in ['EVENT_STREAM_ENABLED', 'RUNTIME_HTTP_CACHE_EVENTS_ENABLED', 'RUNTIME_HTTP_CACHE_WORKER_ENABLED',
                 'RUNTIME_TEAM_EVENTS_ENABLED', 'RUNTIME_TEAM_WORKER_ENABLED']:
        monkeypatch.setenv(name, 'true')
    options = connection_options()
    options['database'] = await observer.fetchval('SELECT current_database()')
    assert options['database'].startswith('slomix_fixture_')
    pool = await asyncpg.create_pool(**options, min_size=0, max_size=1)
    worker = (RuntimeCacheWorker if component == 'cache' else RuntimeTeamWorker)(poll_seconds=0.01)
    stop = asyncio.Event()
    backends = []

    @asynccontextmanager
    async def acquire():
        async with pool.acquire() as conn:
            backends.append(conn.get_server_pid())
            yield conn
            if len(backends) == 1:
                # Schedule the native disconnect before asyncpg's shielded
                # holder.release task, after the real consumer has committed.
                asyncio.get_running_loop().call_soon(conn.terminate)

    task = asyncio.create_task(worker.run(acquire, stop))
    try:
        async with asyncio.timeout(10):
            while not task.done() and not (len(backends) > 1 and worker.state.last_success_monotonic is not None):
                await asyncio.sleep(0.01)
        stop.set()
        await asyncio.wait_for(task, 5)
        assert len(backends) > 1 and backends[0] != backends[1]
        assert worker.state.error_type is None
        consumer = CACHE_CONSUMER if component == 'cache' else TEAM_CONSUMER
        receipts = await observer.fetch('SELECT event_id FROM runtime_consumer_receipts WHERE consumer_name=$1', consumer)
        expected = 2 if component == 'cache' else 1  # Team R2 intentionally remains pending.
        assert len(receipts) == await observer.fetchval(
            'SELECT count(*) FROM runtime_consumer_receipts WHERE consumer_name=$1', consumer) == expected
        if component == 'cache':
            assert await observer.fetchval("SELECT generation FROM runtime_cache_generations WHERE cache_name='http_api'") == 1
        else:
            assert len(await observer.fetch('SELECT id FROM session_teams')) == await observer.fetchval(
                'SELECT count(*) FROM session_teams') == 2
    finally:
        stop.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await pool.close()
