"""Real spawned processes + disposable PG: process exit never implies rollback."""

import asyncio
import json
import os
import threading
import time
from functools import partial

import asyncpg
import pytest

from shared.runtime_proximity_isolation import run_bounded_proximity_batch
from shared.runtime_proximity_main import ProximityProcessConfig
from shared.runtime_proximity_supervisor import supervise
from shared.runtime_worker import run_bounded_owned_task
from tests.integration.test_runtime_events_pg import connection_options, journal_db  # noqa: F401


async def config_for(owner, root):
    options = connection_options()
    root.chmod(0o700)
    return ProximityProcessConfig(
        root, 'fixture', root, options['host'], options.get('port', 5432),
        await owner.fetchval('SELECT current_database()'), await owner.fetchval('SELECT current_user'),
        await owner.fetchval('SELECT current_schema()'), options.get('password', ''),
    )


def blocked_transaction(config, marker, committed):
    """Trusted test task: create all DB resources AFTER spawn, then block Python."""
    async def run():
        pool = await asyncpg.create_pool(**config.pool_options())
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute('INSERT INTO rounds (id, round_number, gaming_session_id) VALUES (1,1,7)')
                    if not committed:
                        marker.write_text(json.dumps(dict(backend=conn.get_server_pid(), child=os.getpid())))
                        time.sleep(60)  # Deliberately uninterruptible by asyncio.timeout.
                marker.write_text(json.dumps(dict(backend=conn.get_server_pid(), child=os.getpid())))
                time.sleep(60)
        finally:
            await pool.close()
    asyncio.run(run())


@pytest.mark.asyncio
async def test_actual_spawned_batch_owns_pool_and_checkpoint(journal_db, tmp_path):  # noqa: F811
    owner, _ = journal_db
    config = await config_for(owner, tmp_path)
    (tmp_path / ('1' * 32)).mkdir(mode=0o700)
    result = run_bounded_proximity_batch(config, timeout_seconds=10)
    assert result.status == 'completed' and result.exit_code == 0
    assert result.pid != os.getpid()
    state = json.loads((tmp_path / '.proximity-cursor.json').read_text())
    assert state['after'] == '1' * 32
    assert len(list(tmp_path.iterdir())) == 2
    with pytest.raises(ProcessLookupError):
        os.kill(result.pid, 0)  # Read-only existence probe; never a stopping signal.
    print('Spawned batch proof: child-owned native pool, deferred input/cursor persisted, child reaped')


@pytest.mark.asyncio
@pytest.mark.parametrize('committed', [False, True])
async def test_timeout_reaps_child_but_commit_outcome_must_be_observed(journal_db, tmp_path, committed):  # noqa: F811
    owner, observer = journal_db
    config = await config_for(owner, tmp_path)
    marker = tmp_path / 'started.json'
    result = run_bounded_owned_task(partial(blocked_transaction, config, marker, committed),
                                    timeout_seconds=3, shutdown_grace=0.2)
    assert result.status == 'timed_out'
    child = json.loads(marker.read_text())  # Proves blocking code actually executed.
    assert child['child'] == result.pid
    with pytest.raises(ProcessLookupError):
        os.kill(result.pid, 0)
    async with asyncio.timeout(5):
        while await observer.fetchval('SELECT COUNT(*) FROM pg_stat_activity WHERE pid=$1', child['backend']):
            await asyncio.sleep(0.02)
    expected = [(1, 1, 7)] if committed else []
    assert await observer.fetchval('SELECT COUNT(*) FROM rounds') == len(expected)
    assert [tuple(row) for row in await observer.fetch('SELECT * FROM rounds')] == expected
    print(f'Timeout proof: reached sync block, child/backend gone; committed={committed}, rows={len(expected)}')


@pytest.mark.asyncio
async def test_parent_loop_with_native_batch_stops_without_second_spawn(journal_db, tmp_path):  # noqa: F811
    owner, _ = journal_db
    config = await config_for(owner, tmp_path)
    (tmp_path / ('1' * 32)).mkdir(mode=0o700)
    stop = threading.Event()
    states = []

    def report(state):
        states.append(state)
        if state['status'] == 'completed':
            stop.set()

    supervise(config, stop, reporter=report, timeout_seconds=10)
    assert [state['status'] for state in states] == ['starting', 'batch_running', 'completed', 'stopped']
    assert json.loads((tmp_path / '.proximity-cursor.json').read_text())['after'] == '1' * 32
    assert len(list(tmp_path.iterdir())) == 2
    print('Parent loop native proof: one isolated batch, persisted cursor, stop without a second spawn')
