"""Opt-in full canonical import proof, using only disposable PostgreSQL."""

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.integration.test_runtime_events_pg import connection_options


def test_neutral_import_commits_player_event_and_retry(tmp_path):
    """Real parser, SQL and commit work with presentation/setup imports blocked."""
    options = connection_options()
    root = Path(__file__).resolve().parents[2]
    fixture = tmp_path / '2026-09-20-120000-goldrush-round-1.txt'
    fixture.write_text(
        '\\'.join(['TestServer', 'goldrush', 'legacy6', '1', '1', '2', '12:00', '7:36', '456'])
        + '\n' + '\\'.join(['a' * 32, 'Fixture', '1', '1', '1 10 20 3 2 1']) + '\n',
        encoding='utf-8',
    )
    script = r'''
import asyncio
import importlib.abc
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid
import asyncpg

class BlockSetup(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'discord', 'dotenv', 'website'} or fullname in {
            'bot.config', 'bot.logging_config', 'shared.importer_startup',
        }:
            raise ModuleNotFoundError('Forbidden ingestion dependency: ' + fullname)
sys.meta_path.insert(0, BlockSetup())
from postgresql_database_manager import PostgreSQLDatabaseManager

async def main():
    options = json.loads(os.environ.pop('NEUTRAL_IMPORT_TEST_CONNECTION'))
    schema = 'neutral_import_test_' + uuid.uuid4().hex
    admin = await asyncpg.connect(**options)
    pool = None
    try:
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        await admin.execute(f'SET search_path TO "{schema}"')
        pool = await asyncpg.create_pool(
            **options, min_size=1, max_size=1,
            server_settings={'search_path': schema, 'statement_timeout': '10000'},
        )
        manager = PostgreSQLDatabaseManager(config=SimpleNamespace(
            database_type='postgresql', excluded_maps=frozenset(),
        ))
        manager.pool = pool
        # Explicit test-only bootstrap, never part of neutral construction.
        await manager._create_schema_if_missing()
        await admin.execute((Path(sys.argv[2]) / 'migrations/083_runtime_events.sql').read_text())
        manager.event_stream_enabled = True
        result = await manager.process_file(Path(sys.argv[1]))
        assert result[0], result
        assert manager.pool is pool
        assert await admin.fetchval('SELECT count(*) FROM rounds') == 1
        players = await admin.fetch('SELECT player_guid, kills FROM player_comprehensive_stats')
        assert len(players) == 1 and players[0]['kills'] == 3
        # Canonical regular stats use the 8-character GUID, unlike proximity.
        assert players[0]['player_guid'] == 'a' * 8
        assert await admin.fetchval('SELECT count(*) FROM player_comprehensive_stats') == len(players)
        events = await admin.fetch('SELECT round_id, event_type FROM runtime_events')
        assert len(events) == 1 and events[0]['event_type'] == 'round_stats_imported'
        assert await admin.fetchval('SELECT count(*) FROM runtime_events') == len(events)
        assert await admin.fetchval('SELECT success FROM processed_files') is True
        assert await admin.fetchval('SELECT id FROM rounds') == events[0]['round_id']
        retry = await manager.process_file(Path(sys.argv[1]))
        assert retry == (True, 'Already processed')
        assert await admin.fetchval('SELECT count(*) FROM runtime_events') == 1
        assert await admin.fetchval('SELECT count(*) FROM player_comprehensive_stats') == 1
        async with pool.acquire() as conn:
            assert await conn.fetchval('SELECT 1') == 1
        print('Neutral PG proof: one round, one player (3 kills), one event, marker true, retry unchanged')
    finally:
        try:
            if pool is not None:
                await asyncio.wait_for(pool.close(), 5)
        finally:
            try:
                await admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            finally:
                await admin.close(timeout=5)
asyncio.run(main())
'''
    result = subprocess.run(
        [sys.executable, '-c', script, str(fixture), str(root)], cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(root),
             'NEUTRAL_IMPORT_TEST_CONNECTION': json.dumps(options),
             'BOT_LOG_DIR': str(tmp_path / 'forbidden-logs')},
        capture_output=True, text=True, timeout=25,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Neutral PG proof:' in result.stdout
    assert not (tmp_path / 'forbidden-logs').exists()
    print(result.stdout.strip())
