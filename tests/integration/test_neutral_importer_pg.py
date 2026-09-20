"""Opt-in full canonical import proof, using only disposable PostgreSQL."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.integration.test_runtime_events_pg import connection_options


@pytest.mark.parametrize('scenario', [
    'single', 'ordered_pair', 'r2_first', 'late_r1', 'deferred_r1', 'zero_delta', 'verified_spool',
])
def test_neutral_import_commits_player_event_and_retry(tmp_path, scenario):
    """Real parser, SQL and commit work with presentation/setup imports blocked."""
    options = connection_options()
    root = Path(__file__).resolve().parents[2]
    fixture = tmp_path / '2026-09-20-120000-goldrush-round-1.txt'
    fixture.write_text(
        '\\'.join(['TestServer', 'goldrush', 'legacy6', '1', '1', '2', '12:00', '7:36', '456'])
        + '\n' + '\\'.join(['a' * 32, 'Fixture', '1', '1', '1 10 20 3 2 1']) + '\n',
        encoding='utf-8',
    )
    r2 = tmp_path / '2026-09-20-121000-goldrush-round-2.txt'
    r2.write_text(
        '\\'.join(['TestServer', 'goldrush', 'legacy6', '2', '2', '1', '12:00', '7:36', '456'])
        + '\n' + '\\'.join(['a' * 32, 'Fixture', '1', '1',
                            '1 10 20 3 2 1' if scenario == 'zero_delta' else '1 25 40 8 4 2']) + '\n',
        encoding='utf-8',
    )
    if scenario in {'late_r1', 'deferred_r1'}:
        fixture.rename(fixture.with_suffix('.pending'))
    if scenario == 'verified_spool':
        fixture.rename(fixture.with_suffix('.source'))
        r2.rename(r2.with_suffix('.source'))
    script = r'''
import asyncio
import hashlib
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
from shared.runtime_import import import_ready_file
from shared.runtime_capture_retry import capture_once
from shared.runtime_ingest import import_verified_file

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
        ), allow_legacy_r1_fallback=False)
        manager.pool = pool
        # Explicit test-only bootstrap, never part of neutral construction.
        await manager._create_schema_if_missing()
        await admin.execute((Path(sys.argv[2]) / 'migrations/083_runtime_events.sql').read_text())
        manager.event_stream_enabled = True
        scenario = sys.argv[3]
        if scenario != 'single':
            r1 = Path(sys.argv[1])
            r2 = r1.parent / '2026-09-20-121000-goldrush-round-2.txt'
            if scenario == 'verified_spool':
                sources = {path: path.with_suffix('.source').read_bytes() for path in (r1, r2)}
                legacy = r1.parent / 'local_stats'
                legacy.mkdir()
                (legacy / r1.name).write_bytes(sources[r1])
                async def verified(path, digest=None):
                    return await import_verified_file(
                        manager, path.parent, path.name, expected_size=len(sources[path]),
                        expected_sha256=digest or hashlib.sha256(sources[path]).hexdigest(),
                    )
                missing = await verified(r2)
                assert missing.capture_status == 'missing' and missing.import_result is None
                assert capture_once(r2.parent, r2.name, [sources[r2]], expected_size=len(sources[r2]),
                                    expected_sha256=hashlib.sha256(sources[r2]).hexdigest()) == 'published'
                conflict = await verified(r2, '0' * 64)
                assert conflict.capture_status == 'conflict' and conflict.import_result is None
                waiting = await verified(r2)
                assert waiting.import_result.status == 'waiting_for_r1', waiting
                for table in ('rounds', 'processed_files', 'runtime_events'):
                    assert await admin.fetchval(f'SELECT count(*) FROM {table}') == 0
                assert capture_once(r1.parent, r1.name, [sources[r1]], expected_size=len(sources[r1]),
                                    expected_sha256=hashlib.sha256(sources[r1]).hexdigest()) == 'published'
            if scenario == 'zero_delta':
                assert (await manager.process_file(r1))[0]
                r1.rename(r1.with_suffix('.retired'))
                waiting = await import_ready_file(manager, r2)
                assert waiting.status == 'waiting_for_r1', waiting
                assert not await manager.is_file_processed(r2.name)
                assert await admin.fetchval('SELECT count(*) FROM runtime_events') == 1
                r1.with_suffix('.retired').rename(r1)
            if scenario == 'deferred_r1':
                waiting = await import_ready_file(manager, r2)
                assert waiting.status == 'waiting_for_r1', waiting
                for table in ('rounds', 'processed_files', 'runtime_events'):
                    assert await admin.fetchval(f'SELECT count(*) FROM {table}') == 0
                r1.with_suffix('.pending').rename(r1)
            paths = [r1, r2] if scenario == 'ordered_pair' else [r2, r1]
            for path in paths:
                if scenario == 'late_r1' and path == r1:
                    r1.with_suffix('.pending').rename(r1)
                if scenario == 'verified_spool':
                    result = await verified(path)
                    assert result.capture_status == 'match' and result.import_result.status == 'imported'
                elif scenario == 'deferred_r1':
                    result = await import_ready_file(manager, Path(path.name))
                    assert result.status == 'imported', result
                else:
                    result = await manager.process_file(path)
                    assert result[0], result
            rows = await admin.fetch("""
                SELECT r.round_number, r.round_status, p.kills
                FROM rounds r JOIN player_comprehensive_stats p ON p.round_id=r.id
                ORDER BY r.round_number
            """)
            expected = [(1, 3), (2, 8)] if scenario == 'late_r1' else [(0, 8), (1, 3), (2, 5)]
            if scenario == 'zero_delta':
                expected = [(0, 3), (1, 3), (2, 0)]
            assert [(r['round_number'], r['kills']) for r in rows] == expected, rows
            if scenario == 'late_r1':
                assert rows[-1]['round_status'] == 'orphan_r2', rows
            events = await admin.fetch('SELECT round_number FROM runtime_events ORDER BY round_number')
            assert [r['round_number'] for r in events] == [1, 2]
            assert await admin.fetchval('SELECT count(*) FROM runtime_events') == len(events)
            assert await admin.fetchval('SELECT count(*) FROM processed_files WHERE success') == 2
            assert await manager.process_file(r2) == (True, 'Already processed')
            if scenario == 'verified_spool':
                def no_read():
                    raise AssertionError('Completed capture must not read source again')
                    yield b''
                assert capture_once(r2.parent, r2.name, no_read(), expected_size=len(sources[r2]),
                                    expected_sha256=hashlib.sha256(sources[r2]).hexdigest()) == 'content_present'
                retry = await verified(r2)
                assert retry.import_result.status == 'imported'
                assert retry.import_result.message == 'Already processed'
            after = await admin.fetch("""
                SELECT r.round_number, r.round_status, p.kills
                FROM rounds r JOIN player_comprehensive_stats p ON p.round_id=r.id
                ORDER BY r.round_number
            """)
            assert rows == after
            assert await admin.fetchval('SELECT count(*) FROM runtime_events') == 2
            assert await admin.fetchval('SELECT count(*) FROM rounds') == len(rows)
            if scenario == 'deferred_r1':
                r1.rename(r1.with_suffix('.retired'))
                processed = await import_ready_file(manager, Path(r2.name))
                assert processed.status == 'imported' and processed.message == 'Already processed'
                mirror = r2.with_name('2026-09-20-121500-goldrush-round-2.txt')
                mirror.write_bytes(r2.read_bytes())
                duplicate = await import_ready_file(manager, mirror)
                assert duplicate.status == 'imported' and 'Duplicate payload' in duplicate.message
                assert await manager.is_file_processed(mirror.name)
                malformed = r2.with_name('bad-round-2.txt')
                malformed.write_text('invalid fixture')
                invalid = await import_ready_file(manager, malformed)
                assert invalid.status == 'failed', invalid
                invalid_time = r2.with_name('2026-13-32-999999-goldrush-round-2.txt')
                invalid_time.write_text('invalid fixture')
                invalid = await import_ready_file(manager, invalid_time)
                assert invalid.status == 'failed', invalid
                assert await admin.fetchval(
                    'SELECT success FROM processed_files WHERE filename=$1', malformed.name
                ) is False
                assert await admin.fetchval('SELECT count(*) FROM runtime_events') == 2
                assert await admin.fetchval('SELECT count(*) FROM rounds') == len(rows)
            async with pool.acquire() as conn:
                assert await conn.fetchval('SELECT 1') == 1
            print('Neutral PG proof: ' + scenario + '; rows=' + str(expected) + '; retry unchanged')
            return
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
        [sys.executable, '-c', script, str(fixture), str(root), scenario], cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(root),
             'NEUTRAL_IMPORT_TEST_CONNECTION': json.dumps(options),
             'BOT_LOG_DIR': str(tmp_path / 'forbidden-logs')},
        capture_output=True, text=True, timeout=25,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Neutral PG proof:' in result.stdout
    assert not (tmp_path / 'forbidden-logs').exists()
    print(result.stdout.strip())
