"""Declared pair gate plus canonical import on an isolated full-schema database."""

from dataclasses import replace

import pytest

from bot.runtime_completed_import import import_completed_round
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db
from tests.unit.test_runtime_identity_contract import FIRST, SECOND
from tests.unit.test_runtime_identity_import import completed_identity_pair

full_import_db = _full_import_db


@pytest.mark.timeout(120)
async def test_declared_wrong_match_cannot_write_then_correct_pair_replays(full_import_db, tmp_path):
    manager, observer = full_import_db
    first, second = completed_identity_pair(tmp_path / 'correct')
    _, wrong = completed_identity_pair(tmp_path / 'wrong',
        [FIRST.encode(), replace(SECOND, match_id='d' * 32).encode()])
    assert (await import_completed_round(manager, first, require_declared_identity=True))[0]
    rounds = await observer.fetch('SELECT * FROM rounds ORDER BY id')
    events = await observer.fetch('SELECT * FROM runtime_events ORDER BY id')
    with pytest.raises(ValueError, match='pair disagrees'):
        await import_completed_round(manager, wrong, first=first, require_declared_identity=True)
    assert await observer.fetch('SELECT * FROM rounds ORDER BY id') == rounds
    assert await observer.fetch('SELECT * FROM runtime_events ORDER BY id') == events
    assert await observer.fetchval('SELECT count(*) FROM processed_files WHERE filename=$1', wrong.filename) == 0
    assert (await import_completed_round(manager, second, first=first, require_declared_identity=True))[0]
    committed = await observer.fetch('SELECT * FROM runtime_events ORDER BY id')
    assert len(committed) == 2
    assert (await import_completed_round(manager, second, first=first, require_declared_identity=True))[0]
    assert await observer.fetch('SELECT * FROM runtime_events ORDER BY id') == committed
    halves = await observer.fetch('SELECT id,gaming_session_id,round_start_unix FROM rounds '
                                   'WHERE round_number IN (1,2) ORDER BY round_number')
    assert len(halves) == await observer.fetchval('SELECT count(*) FROM rounds WHERE round_number IN (1,2)') == 2
    assert halves[0]['gaming_session_id'] == halves[1]['gaming_session_id'] is not None
    assert all(row['round_start_unix'] is None for row in halves)
    for item in (first, second, wrong):
        assert (item.root / item.generation / item.filename).exists()
    print('DECLARED ID PROOF: wrong match writes no R2/event/marker; correct R2 imports/replays '
          'once, one session, physical timing still unknown; no producer authentication claimed')


@pytest.mark.parametrize('deferred', [False, True])
@pytest.mark.parametrize('validation', [True, False])
async def test_bound_replay_reconciles_post_commit_team_step(full_import_db, tmp_path, monkeypatch, deferred, validation):
    import asyncio

    manager, observer = full_import_db
    manager.defer_team_assignment = deferred
    if not validation:
        from unittest.mock import AsyncMock

        monkeypatch.setattr(manager, '_validate_round_data', AsyncMock(return_value=(False, 'synthetic warning')))
    first, _ = completed_identity_pair(tmp_path, balanced=True)
    original_mark = manager.mark_file_processed

    async def cancelled_marker(*args, **kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(manager, 'mark_file_processed', cancelled_marker)
    with pytest.raises(asyncio.CancelledError):
        await import_completed_round(manager, first, expected_identity=FIRST)
    assert await observer.fetchval('SELECT count(*) FROM runtime_round_mappings') == 1
    assert await observer.fetchval('SELECT count(*) FROM session_teams') == 0
    assert await observer.fetchval('SELECT count(*) FROM processed_files') == 0
    monkeypatch.setattr(manager, 'mark_file_processed', original_mark)
    assert (await import_completed_round(manager, first, expected_identity=FIRST)) == (True, 'Already mapped')
    teams = await observer.fetch('SELECT * FROM session_teams ORDER BY id')
    assert len(teams) == await observer.fetchval('SELECT count(*) FROM session_teams') == (0 if deferred else 2)
    assert await observer.fetchval('SELECT count(*) FROM processed_files WHERE success') == 1
    assert await observer.fetchval('SELECT count(*) FROM runtime_events') == 1
    marker = await observer.fetchrow('SELECT * FROM processed_files WHERE filename=$1', first.filename)
    if not validation:
        assert marker['error_message'].startswith('WARN:')
    else:
        assert marker['error_message'] is None
    assert (await import_completed_round(manager, first, expected_identity=FIRST))[0] is True
    assert await observer.fetchrow('SELECT * FROM processed_files WHERE filename=$1', first.filename) == marker
    assert await observer.fetch('SELECT * FROM session_teams ORDER BY id') == teams
    print('BOUND REPLAY: canonical commit survives cancellation; default teams reconcile; deferred teams untouched')


async def test_bound_warning_pair_persists_and_replays(full_import_db, tmp_path, monkeypatch):
    from unittest.mock import AsyncMock

    manager, observer = full_import_db
    first, second = completed_identity_pair(tmp_path)
    monkeypatch.setattr(manager, '_validate_round_data', AsyncMock(return_value=(False, 'synthetic warning')))
    assert (await import_completed_round(manager, first, expected_identity=FIRST))[0] is True
    assert (await import_completed_round(manager, second, first=first, expected_identity=SECOND))[0] is True
    events = await observer.fetch('SELECT validation_passed FROM runtime_events ORDER BY id')
    assert [row['validation_passed'] for row in events] == [False, False]
    assert await observer.fetchval('SELECT count(*) FROM runtime_round_mappings') == 2
    assert await observer.fetchval("SELECT count(*) FROM processed_files WHERE success AND error_message LIKE 'WARN:%'") == 2
    markers = await observer.fetch('SELECT * FROM processed_files ORDER BY filename')
    assert (await import_completed_round(manager, first, expected_identity=FIRST))[0] is True
    assert (await import_completed_round(manager, second, first=first, expected_identity=SECOND))[0] is True
    assert await observer.fetch('SELECT validation_passed FROM runtime_events ORDER BY id') == events
    assert await observer.fetch('SELECT * FROM processed_files ORDER BY filename') == markers
    assert await observer.fetchval('SELECT count(*) FROM runtime_round_mappings') == 2
    print('BOUND WARNINGS: both canonical halves, false validation journal and mappings persist/replay once')


@pytest.mark.parametrize('map_name', ['map.v2', 'map+beta', 'SW_goldrush_te'])
async def test_map_alphabet_upgrade_and_bound_import(full_import_db, tmp_path, map_name):
    from pathlib import Path

    manager, conn = full_import_db
    first, _ = completed_identity_pair(tmp_path, map_name=map_name)
    if map_name != 'SW_goldrush_te':
        await conn.execute('ALTER TABLE runtime_round_mappings DROP CONSTRAINT runtime_round_mappings_map_name_check')
        await conn.execute("ALTER TABLE runtime_round_mappings ADD CONSTRAINT runtime_round_mappings_map_name_check CHECK (map_name ~ '^[A-Za-z0-9_-]{1,64}$')")
        assert (await import_completed_round(manager, first, expected_identity=FIRST))[0] is False
        assert await conn.fetchval('SELECT count(*) FROM rounds') == 0
        assert await conn.fetchval('SELECT count(*) FROM runtime_events') == 0
        assert await conn.fetchval('SELECT count(*) FROM processed_files') == 0
        migration = Path(__file__).resolve().parents[2] / 'migrations/104_runtime_round_mapping_map_alphabet.sql'
        await conn.execute(migration.read_text())
    assert (await import_completed_round(manager, first, expected_identity=FIRST))[0] is True
    assert await conn.fetchval('SELECT map_name FROM rounds WHERE round_number=1') == map_name
    assert await conn.fetchval('SELECT map_name FROM runtime_round_mappings') == map_name
    assert (await import_completed_round(manager, first, expected_identity=FIRST))[0] is True
    assert await conn.fetchval('SELECT count(*) FROM runtime_round_mappings') == 1
    print('MAP UPGRADE:', map_name, 'canonical mapping and replay verified')


async def test_explicit_fresh_wipe_orders_runtime_children_and_rolls_back(full_import_db, tmp_path):
    manager, conn = full_import_db
    first, second = completed_identity_pair(tmp_path, balanced=True)
    assert (await import_completed_round(manager, first, expected_identity=FIRST))[0] is True
    assert (await import_completed_round(manager, second, first=first, expected_identity=SECOND))[0] is True
    await conn.execute("INSERT INTO runtime_consumer_receipts(consumer_name,event_id) SELECT 'wipe-fixture',id FROM runtime_events")
    await conn.execute("INSERT INTO runtime_cache_generations(cache_name,generation) VALUES ('wipe-fixture',3)")
    await conn.execute("INSERT INTO user_permissions(discord_id,tier) VALUES (123,'admin')")
    config = await conn.fetch('SELECT * FROM user_permissions ORDER BY id')
    await conn.execute('ALTER TABLE proximity_processed_files ADD COLUMN IF NOT EXISTS linked_round_id INTEGER REFERENCES rounds(id) ON DELETE RESTRICT')
    linked = await conn.fetchval('SELECT id FROM rounds WHERE round_number=1')
    await conn.execute('INSERT INTO proximity_processed_files(filename,file_hash,aggregates_applied,runtime_parent_gate,linked_round_id) VALUES ($1,$2,true,true,$3)', 'preserved-proximity.txt', 'f' * 64, linked)
    await conn.execute('INSERT INTO player_teamplay_stats(player_guid,player_name,crossfire_kills) VALUES ($1,$2,7)', 'c' * 32, 'Fixture')
    proximity_receipt = dict(await conn.fetchrow('SELECT * FROM proximity_processed_files'))
    aggregates = await conn.fetch('SELECT * FROM player_teamplay_stats ORDER BY id')
    orders = {'rounds':'id', 'runtime_events':'id', 'runtime_round_mappings':'source_key,round_key',
              'runtime_consumer_receipts':'consumer_name,event_id', 'runtime_cache_generations':'cache_name',
              'player_comprehensive_stats':'id', 'weapon_comprehensive_stats':'id',
              'processed_files':'filename', 'session_teams':'id'}
    before = {name: await conn.fetch(f'SELECT * FROM {name} ORDER BY {order}') for name, order in orders.items()}
    assert all(before[name] for name in ('rounds', 'runtime_events', 'runtime_round_mappings'))
    # Native negative control: omit mapping cleanup, as in the old wipe list.
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    original_pool = manager.pool

    class SkipMappings:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        async def execute(self, query, *args):
            if query.startswith('DELETE FROM runtime_round_mappings'):
                return 'DELETE 0'
            return await self.connection.execute(query, *args)

    @asynccontextmanager
    async def skipping_pool():
        async with original_pool.acquire() as connection:
            yield SkipMappings(connection)

    manager.pool = SimpleNamespace(acquire=skipping_pool)
    try:
        with pytest.raises(RuntimeError, match='runtime_round_mappings'):
            await manager._wipe_all_tables()  # noqa: SLF001 -- native old-behavior negative control
    finally:
        manager.pool = original_pool
    for name, order in orders.items():
        assert await conn.fetch(f'SELECT * FROM {name} ORDER BY {order}') == before[name]
    assert dict(await conn.fetchrow('SELECT * FROM proximity_processed_files')) == proximity_receipt
    assert await conn.fetch('SELECT * FROM player_teamplay_stats ORDER BY id') == aggregates
    await conn.execute("CREATE FUNCTION fail_fixture_wipe() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic wipe failure'; END $$")
    await conn.execute('CREATE TRIGGER fail_fixture_wipe BEFORE DELETE ON runtime_events FOR EACH ROW EXECUTE FUNCTION fail_fixture_wipe()')
    with pytest.raises(RuntimeError, match='Transaction rolled back'):
        await manager._wipe_all_tables()  # noqa: SLF001 -- explicit fixture-only destructive boundary
    for name, order in orders.items():
        assert await conn.fetch(f'SELECT * FROM {name} ORDER BY {order}') == before[name]
    assert dict(await conn.fetchrow('SELECT * FROM proximity_processed_files')) == proximity_receipt
    assert await conn.fetch('SELECT * FROM player_teamplay_stats ORDER BY id') == aggregates
    await conn.execute('DROP TRIGGER fail_fixture_wipe ON runtime_events')
    await conn.execute('DROP FUNCTION fail_fixture_wipe()')
    await manager._wipe_all_tables()  # noqa: SLF001 -- isolated fixture only, never application DB
    for name in (*orders, 'processed_files', 'session_teams'):
        rows = await conn.fetch(f'SELECT * FROM {name}')
        assert len(rows) == await conn.fetchval(f'SELECT count(*) FROM {name}') == 0
    assert await conn.fetch('SELECT * FROM user_permissions ORDER BY id') == config
    assert dict(await conn.fetchrow('SELECT * FROM proximity_processed_files')) == (proximity_receipt | {'linked_round_id': None})
    assert await conn.fetch('SELECT * FROM player_teamplay_stats ORDER BY id') == aggregates
    print('FRESH WIPE: R2/R1 mapping, journal and receipts cleared atomically; config preserved; failure rolled back')


@pytest.mark.parametrize('kind', ['legacy', 'mapped', 'linked_proximity'])
async def test_legacy_date_repair_admission_is_explicit(full_import_db, tmp_path, monkeypatch, kind, caplog):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    manager, conn = full_import_db
    first, _ = completed_identity_pair(tmp_path, balanced=True)
    options = {'expected_identity': FIRST} if kind == 'mapped' else {}
    assert (await import_completed_round(manager, first, **options))[0] is True
    if kind == 'linked_proximity':
        await conn.execute('ALTER TABLE proximity_processed_files ADD COLUMN IF NOT EXISTS linked_round_id INTEGER REFERENCES rounds(id) ON DELETE RESTRICT')
        linked = await conn.fetchval('SELECT id FROM rounds WHERE round_number=1')
        await conn.execute('INSERT INTO proximity_processed_files(filename,file_hash,aggregates_applied,runtime_parent_gate,linked_round_id) VALUES ($1,$2,true,true,$3)', 'linked-proximity.txt', 'f' * 64, linked)
    before = await conn.fetch('SELECT * FROM rounds ORDER BY id')
    original_pool = manager.pool
    deletions = []

    class ObserveDeletes:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        async def execute(self, query, *args):
            if query.lstrip().startswith('DELETE '):
                deletions.append(query)
            return await self.connection.execute(query, *args)

    @asynccontextmanager
    async def observed_pool():
        async with original_pool.acquire() as connection:
            yield ObserveDeletes(connection)

    importer = AsyncMock()
    monkeypatch.setattr(manager, 'import_all_files', importer)
    manager.pool = SimpleNamespace(acquire=observed_pool)
    try:
        result = await manager.fix_date_range('2026-09-25', '2026-09-25')
    finally:
        manager.pool = original_pool
    if kind == 'legacy':
        assert result is True and deletions
        importer.assert_awaited_once_with(start_date='2026-09-25', end_date='2026-09-25')
        assert await conn.fetchval('SELECT count(*) FROM rounds') == 0
    else:
        assert result is False and not deletions
        importer.assert_not_awaited()
        assert await conn.fetch('SELECT * FROM rounds ORDER BY id') == before
        assert 'Legacy date repair refused' in caplog.text
    print('DATE REPAIR:', kind, result, 'legacy reimport mocked; bound/linked paths read-only')
