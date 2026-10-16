"""Atomic team receipt proof against an explicitly isolated full-schema DB."""

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import asyncpg
import pytest

from bot.runtime_completed_import import import_completed_round
from shared import runtime_team_consumer as consumer_module
from shared.runtime_team_consumer import CONSUMER, consume_team_event
from shared.team_identity import TeamIdentityConflict
from shared.team_write_guard import TeamWriteBusy, team_write_transaction
from tests.integration.test_runtime_full_import_pg import completed_pair
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db

full_import_db = _full_import_db


@pytest.mark.timeout(120)
async def test_team_effect_receipt_rollback_retry_and_preservation(full_import_db, tmp_path, monkeypatch):
    importer, conn = full_import_db
    first, _ = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(importer, first))[0] is True
    event_id = await conn.fetchval('SELECT id FROM runtime_events WHERE round_number=1')
    original = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    assert len(original) == 2
    monkeypatch.setenv('EVENT_STREAM_ENABLED', 'true')
    monkeypatch.delenv('RUNTIME_TEAM_EVENTS_ENABLED', raising=False)
    assert (await consume_team_event(conn, event_id=event_id)).status == 'disabled'
    monkeypatch.setenv('RUNTIME_TEAM_EVENTS_ENABLED', 'true')
    await conn.execute('ALTER TABLE session_teams RENAME COLUMN session_identity TO legacy_identity')
    try:
        assert (await consume_team_event(conn, event_id=event_id)).reason == 'schema_unavailable'
        assert await conn.fetchval('SELECT count(*) FROM runtime_consumer_receipts') == 0
    finally:
        await conn.execute('ALTER TABLE session_teams RENAME COLUMN legacy_identity TO session_identity')
    for layout in ('complete', 'partial', 'empty'):
        if layout == 'partial':
            await conn.execute('DELETE FROM session_teams WHERE id=$1', original[1]['id'])
        if layout == 'empty':
            await conn.execute("UPDATE session_teams SET player_guids='[]', player_names='[]'")
        before = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
        result = await consume_team_event(conn, event_id=event_id)
        assert (result.status, result.reason) == ('pending', 'already_assigned')
        assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == before
        assert await conn.fetchval('SELECT count(*) FROM runtime_consumer_receipts') == 0
    await conn.execute('UPDATE session_teams SET gaming_session_id=NULL')
    ambiguous = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    with pytest.raises(TeamIdentityConflict):
        await consume_team_event(conn, event_id=event_id)
    assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == ambiguous
    assert await conn.fetch('SELECT * FROM runtime_consumer_receipts') == []
    await conn.execute('DELETE FROM session_teams')  # Synthetic fixture, not application data.
    async with importer.pool.acquire() as other, team_write_transaction(other):
        with pytest.raises(TeamWriteBusy):
            await consume_team_event(conn, event_id=event_id)
    assigned, resume = asyncio.Event(), asyncio.Event()
    original_assign = consumer_module.assign_round_teams

    async def paused_assign(*args, **kwargs):
        result = await original_assign(*args, **kwargs)
        assigned.set()
        await resume.wait()
        return result

    monkeypatch.setattr(consumer_module, 'assign_round_teams', paused_assign)
    task = asyncio.create_task(consume_team_event(conn, event_id=event_id))
    try:
        await asyncio.wait_for(assigned.wait(), 2)
        async with importer.pool.acquire() as observer:
            assert await observer.fetchval('SELECT count(*) FROM session_teams') == 0
            assert await observer.fetch('SELECT * FROM session_teams') == []
            with pytest.raises(TeamWriteBusy):
                await consume_team_event(observer, event_id=event_id)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        monkeypatch.setattr(consumer_module, 'assign_round_teams', original_assign)
    assert task.cancelled()
    assert await conn.fetch('SELECT * FROM session_teams') == []
    assert await conn.fetch('SELECT * FROM runtime_consumer_receipts') == []
    await conn.execute("ALTER TABLE runtime_consumer_receipts ADD CONSTRAINT reject_team_receipt CHECK(false)")
    with pytest.raises(asyncpg.CheckViolationError):
        await consume_team_event(conn, event_id=event_id)
    assert await conn.fetchval('SELECT count(*) FROM session_teams') == 0
    assert await conn.fetch('SELECT * FROM session_teams') == []
    assert await conn.fetch('SELECT * FROM runtime_consumer_receipts') == []
    await conn.execute('ALTER TABLE runtime_consumer_receipts DROP CONSTRAINT reject_team_receipt')
    assert (await consume_team_event(conn, event_id=event_id)).status == 'processed'
    teams = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
    assert len(teams) == await conn.fetchval('SELECT count(*) FROM session_teams') == 2
    receipts = await conn.fetch('SELECT consumer_name,event_id FROM runtime_consumer_receipts')
    assert [tuple(row) for row in receipts] == [(CONSUMER, event_id)]
    assert await conn.fetchval('SELECT count(*) FROM runtime_consumer_receipts') == 1
    assert (await consume_team_event(conn, event_id=event_id)).status == 'already_processed'
    assert await conn.fetch('SELECT * FROM session_teams ORDER BY id') == teams
    assert await conn.fetch('SELECT consumer_name,event_id FROM runtime_consumer_receipts') == receipts


@pytest.mark.timeout(120)
async def test_team_consumer_new_process_crash_and_replay(full_import_db, tmp_path, monkeypatch):
    if not os.environ.get('RUNTIME_EVENTS_TEST_SOCKET'):
        pytest.skip('Explicit local Unix proof socket required for subprocess crash test')
    importer, conn = full_import_db
    # Model the already-proven post-marker gap without changing importer behavior.
    monkeypatch.setattr(importer, '_auto_assign_teams_from_r1', AsyncMock(return_value=None))
    first, _ = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(importer, first))[0] is True
    event_id = await conn.fetchval('SELECT id FROM runtime_events WHERE round_number=1')
    assert await conn.fetchval('SELECT count(*) FROM session_teams') == 0
    tables = ('rounds', 'player_comprehensive_stats', 'weapon_comprehensive_stats', 'processed_files', 'runtime_events')
    before = {table: await conn.fetch(f'SELECT * FROM {table} ORDER BY id') for table in tables}
    from tests.integration.test_runtime_events_pg import connection_options
    options = {**connection_options(), 'database': await conn.fetchval('SELECT current_database()')}
    root = Path(__file__).resolve().parents[2]
    script = '''
import asyncio, json, os, sys
import asyncpg
from shared.runtime_team_consumer import consume_team_event
async def main():
    conn = await asyncpg.connect(**json.loads(sys.argv[1]), server_settings={'application_name':'team-receipt-proof'})
    class Wrapped:
        def __getattr__(self, name):
            return getattr(conn, name)
        async def execute(self, query, *args):
            result = await conn.execute(query, *args)
            if sys.argv[3] == 'before_commit' and 'INSERT INTO runtime_consumer_receipts' in query:
                assert await conn.fetchval('SELECT count(*) FROM session_teams') == 2
                assert await conn.fetchval('SELECT count(*) FROM runtime_consumer_receipts') == 1
                os._exit(71)
            return result
    result = await consume_team_event(Wrapped(), event_id=int(sys.argv[2]))
    if sys.argv[3] == 'after_commit':
        assert result.status == 'processed'
        os._exit(72)
    print(result.status)
    await conn.close()
asyncio.run(main())
'''
    snapshots = []
    for phase in ('before_commit', 'after_commit', 'replay', 'replay'):
        child = await asyncio.create_subprocess_exec(
            sys.executable, '-c', script, json.dumps(options), str(event_id), phase,
            cwd=tmp_path, env={**os.environ, 'PYTHONPATH': str(root),
                'EVENT_STREAM_ENABLED': 'true', 'RUNTIME_TEAM_EVENTS_ENABLED': 'true'},
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(child.communicate(), 10)
        finally:
            if child.returncode is None:
                child.terminate()
                await asyncio.wait_for(child.communicate(), 5)
        assert child.returncode == {'before_commit': 71, 'after_commit': 72, 'replay': 0}[phase], (stdout, stderr)
        assert stderr == b''
        assert stdout == (b'already_processed\n' if phase == 'replay' else b'')
        async with asyncio.timeout(3):
            while await conn.fetch("SELECT pid FROM pg_stat_activity WHERE application_name='team-receipt-proof'"):
                await asyncio.sleep(0.01)
        teams = await conn.fetch('SELECT * FROM session_teams ORDER BY id')
        receipts = await conn.fetch('SELECT * FROM runtime_consumer_receipts ORDER BY event_id')
        assert len(teams) == await conn.fetchval('SELECT count(*) FROM session_teams') == (0 if phase == 'before_commit' else 2)
        assert len(receipts) == await conn.fetchval('SELECT count(*) FROM runtime_consumer_receipts') == (0 if phase == 'before_commit' else 1)
        if phase != 'before_commit':
            snapshots.append((teams, receipts))
        for table in tables:
            assert await conn.fetch(f'SELECT * FROM {table} ORDER BY id') == before[table]
    assert snapshots[0] == snapshots[1] == snapshots[2]


@pytest.mark.parametrize('index_kind', ['constraint', 'standalone', 'wrong_columns', 'non_unique', 'partial'])
async def test_identity_unique_index_matches_upgraded_schema(full_import_db, tmp_path, monkeypatch, index_kind):
    manager, conn = full_import_db
    manager.defer_team_assignment = True
    first, _ = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(manager, first))[0] is True
    if index_kind != 'constraint':
        await conn.execute('ALTER TABLE session_teams DROP CONSTRAINT session_teams_identity_unique')
        definition = {
            'standalone': 'CREATE UNIQUE INDEX session_teams_identity_unique ON session_teams(session_identity,map_name,team_name)',
            'wrong_columns': 'CREATE UNIQUE INDEX session_teams_identity_unique ON session_teams(session_start_date,map_name,team_name)',
            'non_unique': 'CREATE INDEX session_teams_identity_unique ON session_teams(session_identity,map_name,team_name)',
            'partial': "CREATE UNIQUE INDEX session_teams_identity_unique ON session_teams(session_identity,map_name,team_name) WHERE map_name='ALL'",
        }[index_kind]
        await conn.execute(definition)
        assert await conn.fetchval("SELECT count(*) FROM pg_constraint WHERE conname='session_teams_identity_unique' AND conrelid='session_teams'::regclass") == 0
    if index_kind == 'standalone':
        await manager._migrate_schema_if_needed()  # noqa: SLF001 -- real legacy setup must accept migration036
        assert await conn.fetchval("SELECT count(*) FROM pg_constraint WHERE conname='session_teams_identity_unique' AND conrelid='session_teams'::regclass") == 0
    monkeypatch.setenv('EVENT_STREAM_ENABLED', 'true')
    monkeypatch.setenv('RUNTIME_TEAM_EVENTS_ENABLED', 'true')
    event_id = await conn.fetchval('SELECT id FROM runtime_events WHERE round_number=1')
    result = await consume_team_event(conn, event_id=event_id)
    accepted = index_kind in ('constraint', 'standalone')
    assert result.status == ('processed' if accepted else 'pending')
    if not accepted:
        assert result.reason == 'schema_unavailable'
    teams = await conn.fetch('SELECT * FROM session_teams')
    receipts = await conn.fetch('SELECT * FROM runtime_consumer_receipts')
    assert len(teams) == await conn.fetchval('SELECT count(*) FROM session_teams') == (2 if accepted else 0)
    assert len(receipts) == await conn.fetchval('SELECT count(*) FROM runtime_consumer_receipts') == int(accepted)
    if accepted:
        assert (await consume_team_event(conn, event_id=event_id)).status == 'already_processed'
    print('TEAM INDEX:', index_kind, result.status)
