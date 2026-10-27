"""Separate native readonly composition and opt-in isolated effect/lifecycle proofs."""

import asyncio
from contextlib import asynccontextmanager

import asyncpg

from shared.runtime_team_worker import RuntimeTeamWorker
from tests.integration.test_runtime_events_pg import connection_options
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db
from tests.integration.test_runtime_team_discovery_pg import SyntheticJournal

full_import_db = _full_import_db


async def exercise_readonly_worker(conn):
    """Caller supplies read-only PG connection; synthetic metadata is all pending.

    The factory borrows a statement fixture view of this one connection. Counts
    prove context lifecycle, not native connection creation/close or pool reset.
    """
    assert await conn.fetchval('SHOW transaction_read_only') == 'on'
    stop = asyncio.Event()
    worker = RuntimeTeamWorker(batch_size=2, poll_seconds=0.001)
    counts = {'acquired': 0, 'released': 0}
    journal = SyntheticJournal(conn)
    journal.is_in_transaction = lambda: False
    journal.add(1, round_number=2)
    journal.add(2, validation_passed=False)
    journal.add(3, schema_version=2)

    @asynccontextmanager
    async def factory():
        counts['acquired'] += 1
        try:
            yield journal
        finally:
            counts['released'] += 1
            if counts['released'] == 2:
                stop.set()

    await asyncio.wait_for(worker.run(factory, stop), 5)
    assert counts == {'acquired': 2, 'released': 2}
    assert journal.calls == 2
    assert worker.state.status == 'stopped'
    assert worker.state.next_hint is None
    assert worker.state.inspected == worker.state.pending == 1  # Last page only.
    assert worker.state.processed == 0
    assert worker.state.last_success_monotonic is not None
    return dict(counts, sql_pages=journal.calls, last_page_pending=worker.state.pending,
                status=worker.state.status, sweep_exhausted=True,
                scope='native SELECT composition; no effect, receipt or native pool lifecycle')


async def test_readonly_worker_native(monkeypatch):
    options = connection_options()
    options['server_settings'] = {'default_transaction_read_only': 'on'}
    for flag in ('EVENT_STREAM_ENABLED', 'RUNTIME_TEAM_EVENTS_ENABLED', 'RUNTIME_TEAM_WORKER_ENABLED'):
        monkeypatch.setenv(flag, 'true')
    conn = await asyncpg.connect(**options)
    try:
        async with conn.transaction(readonly=True):
            await exercise_readonly_worker(conn)
    finally:
        await conn.close(timeout=5)


async def test_native_worker_releases_pool_and_replays_commit(full_import_db, tmp_path, monkeypatch):
    from bot.runtime_completed_import import import_completed_round
    from shared import runtime_team_worker as worker_module
    from shared.runtime_team_batch import consume_team_page
    from shared.runtime_team_consumer import CONSUMER
    from tests.integration.test_runtime_full_import_pg import completed_pair

    importer, observer = full_import_db
    for flag in ('EVENT_STREAM_ENABLED', 'RUNTIME_TEAM_EVENTS_ENABLED', 'RUNTIME_TEAM_WORKER_ENABLED'):
        monkeypatch.setenv(flag, 'true')
    first, _ = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(importer, first))[0] is True
    await observer.execute('DELETE FROM session_teams')  # Isolated synthetic fixture only.
    stop = asyncio.Event()
    worker = RuntimeTeamWorker(poll_seconds=0.001)
    calls, outcomes, snapshots = [], [], []
    counts = {'acquired': 0, 'released': 0}

    @asynccontextmanager
    async def factory():
        try:
            async with importer.pool.acquire() as conn:
                counts['acquired'] += 1
                yield conn
        finally:
            counts['released'] += 1

    async def page_then_lost_response(conn, **kwargs):
        calls.append(kwargs['hint'])
        outcome = await consume_team_page(conn, **kwargs)
        outcomes.append(outcome)
        snapshots.append(await observer.fetch('SELECT * FROM session_teams ORDER BY id'))
        if len(calls) == 1:
            raise ConnectionError('synthetic lost page response after commit')
        stop.set()
        return outcome

    monkeypatch.setattr(worker_module, 'consume_team_page', page_then_lost_response)
    await asyncio.wait_for(worker.run(factory, stop), 10)
    assert calls == [None, None]
    assert outcomes[0].items[0].outcome.status == 'processed'
    assert outcomes[1].status == 'idle' and outcomes[1].items == ()
    assert len(snapshots[0]) == 2 and snapshots[1] == snapshots[0]
    rows = await observer.fetch('SELECT * FROM runtime_consumer_receipts WHERE consumer_name=$1', CONSUMER)
    assert len(rows) == 1
    assert await observer.fetchval('SELECT count(*) FROM runtime_consumer_receipts WHERE consumer_name=$1', CONSUMER) == 1
    assert counts == {'acquired': 2, 'released': 2}
    assert importer.pool.get_idle_size() == importer.pool.get_size()
    assert worker.state.status == 'stopped'


async def test_native_worker_cancel_rolls_back_and_releases_lock(full_import_db, tmp_path, monkeypatch):
    from bot.runtime_completed_import import import_completed_round
    from shared import runtime_team_consumer as consumer_module
    from shared.team_write_guard import TEAM_LOCK_NAMESPACE, TEAM_LOCK_RESOURCE
    from tests.integration.test_runtime_full_import_pg import completed_pair

    importer, observer = full_import_db
    for flag in ('EVENT_STREAM_ENABLED', 'RUNTIME_TEAM_EVENTS_ENABLED', 'RUNTIME_TEAM_WORKER_ENABLED'):
        monkeypatch.setenv(flag, 'true')
    first, _ = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(importer, first))[0] is True
    await observer.execute('DELETE FROM session_teams')
    assigned = asyncio.Event()
    original = consumer_module.assign_round_teams

    async def pause_before_receipt(*args, **kwargs):
        result = await original(*args, **kwargs)
        assigned.set()
        await asyncio.Event().wait()
        return result

    monkeypatch.setattr(consumer_module, 'assign_round_teams', pause_before_receipt)
    worker = RuntimeTeamWorker(attempt_timeout=10)
    task = asyncio.create_task(worker.run(importer.pool.acquire, asyncio.Event()))
    try:
        await asyncio.wait_for(assigned.wait(), 5)
        assert await observer.fetchval('SELECT count(*) FROM session_teams') == 0
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert task.cancelled()
        assert worker.state.status == 'stopped'
        assert await observer.fetch('SELECT * FROM session_teams') == []
        assert await observer.fetchval('SELECT count(*) FROM runtime_consumer_receipts') == 0
        assert await observer.fetch('SELECT * FROM runtime_consumer_receipts') == []
        assert importer.pool.get_idle_size() == importer.pool.get_size()
        async with observer.transaction():
            assert await observer.fetchval('SELECT pg_try_advisory_xact_lock($1::integer,$2::integer)',
                                           TEAM_LOCK_NAMESPACE, TEAM_LOCK_RESOURCE) is True
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
