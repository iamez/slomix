"""Real closed native connections retry on explicitly disposable PostgreSQL."""
import asyncio
import uuid
from contextlib import asynccontextmanager

import asyncpg
import pytest

from shared.runtime_cache_worker import RuntimeCacheWorker
from shared.runtime_team_worker import RuntimeTeamWorker
from tests.integration.test_runtime_events_pg import connection_options
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db

full_import_db = _full_import_db


@pytest.mark.parametrize('kind', ['cache', 'team'])
async def test_actual_closed_native_connection_reacquires_and_releases(full_import_db, monkeypatch, kind):
    _, observer = full_import_db
    for flag in ('EVENT_STREAM_ENABLED', 'RUNTIME_HTTP_CACHE_EVENTS_ENABLED',
                 'RUNTIME_HTTP_CACHE_WORKER_ENABLED', 'RUNTIME_TEAM_EVENTS_ENABLED',
                 'RUNTIME_TEAM_WORKER_ENABLED'):
        monkeypatch.setenv(flag, 'true')
    options = connection_options()
    options['database'] = await observer.fetchval('SELECT current_database()')
    assert options['database'].startswith('slomix_fixture_')
    application = 'closed_native_' + uuid.uuid4().hex
    options['server_settings'] = {'application_name': application, 'search_path': 'public'}
    stop = asyncio.Event()
    worker = (RuntimeCacheWorker if kind == 'cache' else RuntimeTeamWorker)(poll_seconds=0.001)
    pids, released, failed_state = [], [], []

    @asynccontextmanager
    async def acquire():
        if pids:
            failed_state.append((worker.state.status, worker.state.error_type))
        conn = await asyncpg.connect(**options)
        pids.append(conn.get_server_pid())
        if len(pids) == 1:
            conn.terminate()  # Only this owned connection; never a database service.
        try:
            yield conn
        finally:
            if not conn.is_closed():
                await conn.close()
            released.append(True)
            if len(pids) == 2:
                stop.set()

    await asyncio.wait_for(worker.run(acquire, stop), 10)
    assert len(pids) == len(released) == 2 and pids[0] != pids[1]
    assert failed_state == [('unavailable', 'ConnectionError')]
    assert worker.state.status == 'stopped' and worker.state.error_type is None
    assert worker.state.last_success_monotonic is not None
    assert await observer.fetchval('SELECT count(*) FROM runtime_consumer_receipts') == 0
    async with asyncio.timeout(3):
        while await observer.fetchval('SELECT count(*) FROM pg_stat_activity WHERE application_name=$1', application):
            await asyncio.sleep(0.01)
    assert await observer.fetch('SELECT pid FROM pg_stat_activity WHERE application_name=$1', application) == []
    print(f'Actual closed native {kind} connection: unavailable -> fresh backend -> stopped; no leaked connection')
