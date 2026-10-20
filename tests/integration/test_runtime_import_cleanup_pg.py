"""Native transaction/connection cleanup under an injected pool-close failure."""

import asyncio
import hashlib
import uuid
from types import SimpleNamespace

import asyncpg
import pytest

from bot.runtime_completed_import import import_completed_round
from bot.runtime_import_session import open_import_session
from tests.integration.test_runtime_events_pg import connection_options
from tests.integration.test_runtime_full_import_pg import completed_pair
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db

full_import_db = _full_import_db


@pytest.mark.timeout(120)
@pytest.mark.parametrize('committed', [False, True], ids=['before-commit', 'after-commit'])
async def test_cancel_and_close_failure_preserve_import_outcome(full_import_db, tmp_path, committed):
    _, observer = full_import_db
    options = connection_options()
    options['database'] = await observer.fetchval('SELECT current_database()')
    application = 'import_cleanup_' + uuid.uuid4().hex
    native = await asyncpg.create_pool(
        **options, min_size=1, max_size=1, server_settings={'application_name': application},
    )
    reached = asyncio.Event()
    close_failure = OSError('injected close failure')
    terminated = []
    managers = []
    first, _ = completed_pair(tmp_path, balanced=True)
    source = first.root / first.generation / first.filename
    original_bytes = source.read_bytes()

    class FailingClosePool:
        acquire = native.acquire

        async def close(self):
            raise close_failure

        def terminate(self):
            terminated.append(True)
            native.terminate()

    async def factory():
        return FailingClosePool()

    async def run():
        async with open_import_session(SimpleNamespace(database_type='postgresql'),
                                       pool_factory=factory, journal_enabled=True,
                                       defer_team_assignment=True) as manager:
            managers.append(manager)
            if not committed:
                validate = manager._validate_round_data  # noqa: SLF001 -- pause the real pre-commit boundary.

                async def pause_before_commit(*args, **kwargs):
                    result = await validate(*args, **kwargs)
                    reached.set()
                    await asyncio.Event().wait()
                    return result

                manager._validate_round_data = pause_before_commit  # noqa: SLF001 -- fault injection only.
            assert (await import_completed_round(manager, first))[0] is True
            reached.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(run())
    tables = ('rounds', 'player_comprehensive_stats', 'weapon_comprehensive_stats',
              'runtime_events', 'processed_files')

    async def snapshot():
        result = {}
        for table in tables:
            rows = await observer.fetch(f'SELECT * FROM {table}')
            assert len(rows) == await observer.fetchval(f'SELECT count(*) FROM {table}')
            result[table] = rows
        return result

    try:
        await asyncio.wait_for(reached.wait(), 10)
        before = await snapshot()
        assert {table: len(rows) for table, rows in before.items()} == dict(
            zip(tables, (1, 2, 2, 1, 1) if committed else (0, 0, 0, 0, 0), strict=True),
        )
        task.cancel()
        with pytest.raises(asyncio.CancelledError) as caught:
            await asyncio.wait_for(task, 5)
        assert caught.value.__cause__ is close_failure
        assert terminated == [True] and managers[0].pool is None
        assert task.cancelled()
        assert await snapshot() == before

        async def wait_disconnected():
            while await observer.fetchval(
                'SELECT count(*) FROM pg_stat_activity WHERE application_name=$1', application,
            ):
                await asyncio.sleep(0.01)

        await asyncio.wait_for(wait_disconnected(), 2)
        assert await observer.fetch('SELECT pid FROM pg_stat_activity WHERE application_name=$1', application) == []
        assert source.read_bytes() == original_bytes
        assert hashlib.sha256(source.read_bytes()).hexdigest() == first.sha256

        async def healthy_factory():
            return await asyncpg.create_pool(
                **options, min_size=1, max_size=1, server_settings={'application_name': application},
            )

        async with open_import_session(SimpleNamespace(database_type='postgresql'),
                                       pool_factory=healthy_factory, journal_enabled=True,
                                       defer_team_assignment=True) as fresh_manager:
            assert (await import_completed_round(fresh_manager, first))[0] is True
        await asyncio.wait_for(wait_disconnected(), 2)
        retried = await snapshot()
        assert {table: len(rows) for table, rows in retried.items()} == dict(
            zip(tables, (1, 2, 2, 1, 1), strict=True),
        )
        if committed:
            assert retried == before
        assert source.read_bytes() == original_bytes
        print(f'native importer cleanup committed={committed}: cancellation preserved, retry exact, no connections')
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        native.terminate()  # Test-only containment after runtime assertions.
