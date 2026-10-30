"""Native resource/commit visibility proof; disposable PG only, no service start."""

import asyncio

import asyncpg
import pytest

from bot.core.database_adapter import PostgreSQLAdapter
from shared.runtime_proximity_resources import proximity_database_resources
from tests.integration.test_runtime_events_pg import connection_options, journal_db  # noqa: F401


@pytest.mark.asyncio
async def test_native_pair_observes_only_committed_adapter_writes(journal_db):  # noqa: F811
    owner, independent = journal_db
    schema = await owner.fetchval('SELECT current_schema()')
    pool = await asyncpg.create_pool(
        **connection_options(), min_size=0, max_size=2,
        server_settings={'search_path': schema, 'statement_timeout': '5000'},
    )
    # Existing adapter owns query translation/transaction behavior; this test
    # supplies an explicit pool and never invokes its connection defaults.
    adapter = PostgreSQLAdapter('127.0.0.1', 5432, 'unused', 'unused', '')
    adapter.pool = pool
    try:
        async with proximity_database_resources(adapter) as (writer, observer):
            async with writer.transaction() as connection:
                assert connection.get_server_pid() != observer.get_server_pid()
                await writer.execute(
                    'INSERT INTO rounds (id, round_number, gaming_session_id) VALUES (?, ?, ?)', (1, 1, 7))
                assert await observer.fetchval('SELECT COUNT(*) FROM rounds') == 0
            assert await observer.fetchval('SELECT COUNT(*) FROM rounds') == 1
            assert [tuple(row) for row in await independent.fetch('SELECT * FROM rounds')] == [(1, 1, 7)]
            with pytest.raises(RuntimeError, match='rollback proof'):
                async with writer.transaction():
                    await writer.execute('INSERT INTO rounds (id) VALUES (?)', (2,))
                    raise RuntimeError('rollback proof')
            assert await observer.fetchval('SELECT COUNT(*) FROM rounds') == 1
        assert pool.get_idle_size() == pool.get_size() == 2
        print('Native pair proof: distinct backends, observer sees zero before commit, one after; rollback unchanged')
    finally:
        try:
            async with asyncio.timeout(5):
                await pool.close()
        except (Exception, asyncio.CancelledError):
            pool.terminate()
            raise
