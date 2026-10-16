"""Opt-in native owned-session proof; private disposable Unix-socket PG only.

No service startup or ambient application target. Native acceptance remains
pending until these scenarios execute on an explicitly approved running cluster.
"""

import asyncio
import uuid

import pytest

from bot.runtime_completed_import import import_completed_round
from shared import runtime_team_consumer as consumer_module
from shared import runtime_team_session as session_module
from shared import runtime_team_worker as worker_module
from shared.runtime_import_pool import ImportDatabaseConfig
from shared.runtime_team_batch import consume_team_page
from shared.runtime_team_worker import RuntimeTeamWorker
from shared.team_write_guard import TEAM_LOCK_NAMESPACE, TEAM_LOCK_RESOURCE
from tests.integration.test_runtime_events_pg import connection_options
from tests.integration.test_runtime_full_import_pg import completed_pair
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db

full_import_db = _full_import_db


@pytest.fixture
def unix_target():
    # This dependency is resolved before full_import_db can create a database.
    options = connection_options()
    if not options['host'].startswith('/'):
        pytest.skip('Owned development session requires an explicit private Unix test socket')
    return options


@pytest.fixture
async def native_session(unix_target, full_import_db, monkeypatch):
    importer, observer = full_import_db
    config = ImportDatabaseConfig(
        unix_target['host'], await observer.fetchval('SELECT current_database()'),
        unix_target['user'], '', port=unix_target['port'],
        application_name='team_session_test_' + uuid.uuid4().hex,
    )
    for flag in ('EVENT_STREAM_ENABLED', 'RUNTIME_TEAM_EVENTS_ENABLED', 'RUNTIME_TEAM_WORKER_ENABLED'):
        monkeypatch.setenv(flag, 'true')
    importer.defer_team_assignment = True
    pools = []
    original = session_module.create_import_pool

    async def create(configured):
        assert configured is config
        pool = await original(configured)  # Actual asyncpg pool, not a protocol double.
        pools.append(pool)
        return pool

    monkeypatch.setattr(session_module, 'create_import_pool', create)
    try:
        yield importer, observer, config, pools
    finally:
        # Failure containment only, AFTER assertions prove adapter cleanup.
        # This fixture depends on full_import_db so cleanup precedes DROP.
        for pool in pools:
            pool.terminate()


async def assert_disconnected(observer, config, pools):
    assert pools and all(pool.is_closing() for pool in pools)
    query = 'SELECT pid FROM pg_stat_activity WHERE application_name=$1'

    async def disconnected():
        while await observer.fetch(query, config.application_name):
            await asyncio.sleep(0.01)

    await asyncio.wait_for(disconnected(), 2)
    assert await observer.fetch(query, config.application_name) == []
    assert await observer.fetchval(
        'SELECT count(*) FROM pg_stat_activity WHERE application_name=$1', config.application_name,
    ) == 0


async def import_deferred(importer, observer, tmp_path):
    first, _ = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(importer, first))[0] is True
    assert await observer.fetch('SELECT * FROM session_teams') == []
    assert await observer.fetchval('SELECT count(*) FROM session_teams') == 0
    assert await observer.fetchval('SELECT count(*) FROM runtime_events') == 1


@pytest.mark.timeout(120)
async def test_owned_session_native_commit_replay_and_distinct_pools(native_session, tmp_path, monkeypatch):
    importer, observer, config, pools = native_session
    await import_deferred(importer, observer, tmp_path)
    stop = asyncio.Event()
    worker = RuntimeTeamWorker(poll_seconds=0.001)
    outcomes, hints = [], []

    async def one_page(conn, **kwargs):
        hints.append(kwargs['hint'])
        assert await conn.fetchval('SELECT current_database()') == config.database
        assert await conn.fetchval('SHOW application_name') == config.application_name
        result = await consume_team_page(conn, **kwargs)
        outcomes.append(result)
        stop.set()
        return result

    monkeypatch.setattr(worker_module, 'consume_team_page', one_page)
    snapshots = []
    for _ in range(2):
        stop.clear()
        state = await asyncio.wait_for(session_module.run_team_worker(config, worker, stop), 10)
        assert state is worker.state and state.status == 'stopped'
        assert state.last_success_monotonic is not None
        await assert_disconnected(observer, config, pools)
        teams = await observer.fetch('SELECT * FROM session_teams ORDER BY id')
        receipts = await observer.fetch('SELECT * FROM runtime_consumer_receipts ORDER BY event_id')
        assert len(teams) == await observer.fetchval('SELECT count(*) FROM session_teams') == 2
        assert len(receipts) == await observer.fetchval('SELECT count(*) FROM runtime_consumer_receipts') == 1
        snapshots.append((teams, receipts))
    assert len(pools) == 2 and pools[0] is not pools[1]
    assert hints == [None, None]
    assert outcomes[0].items[0].outcome.status == 'processed'
    assert outcomes[1].status == 'idle' and outcomes[1].items == ()
    assert snapshots[0] == snapshots[1]
    print('native owned session: two distinct closed pools, two teams, one receipt, unchanged replay')


@pytest.mark.timeout(120)
async def test_owned_session_native_cancel_rolls_back_and_disconnects(native_session, tmp_path, monkeypatch):
    importer, observer, config, pools = native_session
    await import_deferred(importer, observer, tmp_path)
    assigned = asyncio.Event()
    original = consumer_module.assign_round_teams

    async def pause_before_receipt(*args, **kwargs):
        result = await original(*args, **kwargs)
        assigned.set()
        await asyncio.Event().wait()
        return result

    monkeypatch.setattr(consumer_module, 'assign_round_teams', pause_before_receipt)
    worker = RuntimeTeamWorker(attempt_timeout=10)
    task = asyncio.create_task(session_module.run_team_worker(config, worker, asyncio.Event()))
    try:
        await asyncio.wait_for(assigned.wait(), 5)
        assert await observer.fetchval('SELECT count(*) FROM session_teams') == 0
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        assert worker.state.status == 'stopped'
        await assert_disconnected(observer, config, pools)
        for table in ('session_teams', 'runtime_consumer_receipts'):
            assert await observer.fetch(f'SELECT * FROM {table}') == []
            assert await observer.fetchval(f'SELECT count(*) FROM {table}') == 0
        async with observer.transaction():
            assert await observer.fetchval(
                'SELECT pg_try_advisory_xact_lock($1::integer,$2::integer)',
                TEAM_LOCK_NAMESPACE, TEAM_LOCK_RESOURCE,
            ) is True
        print('native owned cancellation: no effect or receipt, connection gone, team lock reacquired')
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.timeout(120)
async def test_owned_session_native_program_error_closes_connected_pool(native_session, monkeypatch):
    _, observer, config, pools = native_session
    failure = ValueError('synthetic program failure after native connection acquisition')
    worker = RuntimeTeamWorker()
    acquired = []

    async def fail_after_connect(conn, **kwargs):
        acquired.append(await conn.fetchval('SELECT pg_backend_pid()'))
        assert await conn.fetchval('SHOW application_name') == config.application_name
        raise failure

    monkeypatch.setattr(worker_module, 'consume_team_page', fail_after_connect)
    with pytest.raises(ValueError) as caught:
        await asyncio.wait_for(session_module.run_team_worker(config, worker, asyncio.Event()), 10)
    assert caught.value is failure
    assert len(acquired) == 1 and worker.state.status == 'failed'
    await assert_disconnected(observer, config, pools)
    print('native owned failure: original error retained, acquired connection closed')


@pytest.mark.timeout(120)
@pytest.mark.parametrize('after_commit', [False, True], ids=['before-effect', 'after-commit'])
async def test_owned_session_native_reconnect_without_duplicate_effect(
    native_session, tmp_path, monkeypatch, after_commit,
):
    """Same worker/pool recovers a real closed connection, including lost progress after commit."""
    importer, observer, config, pools = native_session
    await import_deferred(importer, observer, tmp_path)
    stop = asyncio.Event()
    worker = RuntimeTeamWorker(poll_seconds=0.001, attempt_timeout=5)
    attempts, snapshots = [], []

    async def effect_snapshot():
        teams = await observer.fetch('SELECT * FROM session_teams ORDER BY id')
        receipts = await observer.fetch('SELECT * FROM runtime_consumer_receipts ORDER BY event_id')
        assert len(teams) == await observer.fetchval('SELECT count(*) FROM session_teams')
        assert len(receipts) == await observer.fetchval('SELECT count(*) FROM runtime_consumer_receipts')
        return teams, receipts

    async def interrupt_one_connection(conn, **kwargs):
        attempts.append((await conn.fetchval('SELECT pg_backend_pid()'), kwargs['hint']))
        assert await conn.fetchval('SELECT current_database()') == config.database
        assert await conn.fetchval('SHOW application_name') == config.application_name
        if len(attempts) == 1:
            if after_commit:
                page = await consume_team_page(conn, **kwargs)
                assert [item.outcome.status for item in page.items] == ['processed']
            snapshots.append(await effect_snapshot())
            assert tuple(map(len, snapshots[0])) == ((2, 1) if after_commit else (0, 0))
            # Close only this borrowed test connection, never a server/service.
            # Its next real query raises asyncpg.InterfaceError, exercising the
            # worker's closed-connection classification and actual pool renewal.
            await conn.close()
            await conn.fetchval('SELECT 1')
            pytest.fail('A closed native connection unexpectedly accepted a query')
        assert len(attempts) == 2
        assert worker.state.status == 'unavailable'
        assert worker.state.error_type == 'ConnectionError'
        assert worker.state.last_success_monotonic is None
        assert kwargs['hint'] is None
        result = await consume_team_page(conn, **kwargs)
        assert [item.outcome.status for item in result.items] == ([] if after_commit else ['processed'])
        stop.set()
        return result

    monkeypatch.setattr(worker_module, 'consume_team_page', interrupt_one_connection)
    state = await asyncio.wait_for(session_module.run_team_worker(config, worker, stop), 15)
    assert len(attempts) == 2 and attempts[0][0] != attempts[1][0]
    assert len(pools) == 1
    assert state.status == 'stopped' and state.error_type is None
    assert state.last_success_monotonic is not None and state.next_hint is None
    assert state.processed == (0 if after_commit else 1)
    final = await effect_snapshot()
    assert tuple(map(len, final)) == (2, 1)
    if after_commit:
        assert final == snapshots[0]
    assert await observer.fetchval(
        'SELECT count(*) FROM runtime_events e JOIN runtime_consumer_receipts r ON r.event_id=e.id '
        "WHERE e.round_number=1 AND r.consumer_name='round-team-assignment-v1'",
    ) == 1
    await assert_disconnected(observer, config, pools)
    print(f'native reconnect after_commit={after_commit}: new backend, one pool, two teams, one receipt, closed')
