"""Real stats -> timing -> strict proximity on one isolated full-schema DB.

Lua transport is deliberately not simulated: its pre-linked synthetic source
row is explicit. This proves composition, not autonomous source delivery.
"""

import hashlib
from datetime import date

import pytest

from bot.core.database_adapter import PostgreSQLAdapter
from bot.runtime_completed_import import import_completed_round
from shared.proximity_import import import_proximity_file
from shared.round_timing_reconcile import reconcile_missing_round_timing
from shared.runtime_spool import publish_proximity_file
from tests.integration.test_runtime_full_import_pg import completed_pair
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db

full_import_db = _full_import_db


@pytest.mark.timeout(120)
async def test_canonical_stats_timing_and_proximity_share_one_round(full_import_db, tmp_path):
    manager, observer = full_import_db
    first, second = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(manager, first))[0] is True
    assert (await import_completed_round(manager, second, first=first))[0] is True
    parents = await observer.fetch('SELECT id,match_id,round_number,gaming_session_id,round_start_unix '
                                   'FROM rounds WHERE round_number IN (1,2) ORDER BY round_number')
    assert len(parents) == 2
    assert len({r['gaming_session_id'] for r in parents}) == 1
    assert parents[0]['gaming_session_id'] is not None
    assert all(r['round_start_unix'] is None for r in parents)
    adapter = PostgreSQLAdapter('127.0.0.1', 5432, 'unused', 'unused', '')
    adapter.pool = manager.pool  # Caller-owned explicit test pool; never connect defaults.
    start = 1790337600
    payload = (f'# PROXIMITY_TRACKER_V4\n# map=supply\n# round=1\n'
               f'# round_start_unix={start}\n# round_end_unix={start + 600}\n'
               '# capabilities=vehicle_tracking:1\n# VEHICLE_PROGRESS\n'
               'tank;script_mover;0;0;0;100;0;0;100;1000;900;0\n').encode()
    path = tmp_path / '2026-09-25-120000-supply-round-1_engagements.txt'
    publish_proximity_file(tmp_path, path.name, [payload], expected_size=len(payload),
                           expected_sha256=hashlib.sha256(payload).hexdigest())
    options = dict(adapter=adapter, session_date=date(2026, 9, 25), gametimes_dir=tmp_path,
                   expected_size=len(payload), expected_sha256=hashlib.sha256(payload).hexdigest(),
                   require_linked_parent=True)
    pending = await import_proximity_file(path, **options)
    assert pending.pending_reason == 'parent_missing' and not pending.success
    assert await observer.fetchval('SELECT count(*) FROM proximity_processed_files') == 0
    assert await observer.fetch('SELECT * FROM proximity_vehicle_progress') == []
    await observer.execute('INSERT INTO lua_round_teams '
        '(match_id,round_number,round_id,map_name,round_start_unix,round_end_unix,actual_duration_seconds) '
        'VALUES ($1,1,$2,\'supply\',$3,$4,600)', parents[0]['match_id'], parents[0]['id'], start, start + 600)
    # An unrelated eligible historical round must not be changed by this import.
    historical_id = await observer.fetchval("INSERT INTO rounds "
        "(round_number,gaming_session_id,map_name) VALUES (1,999,'historical') RETURNING id")
    await observer.execute("INSERT INTO lua_round_teams "
        "(match_id,round_number,round_id,map_name,round_start_unix,round_end_unix,actual_duration_seconds) "
        "VALUES ('historical',1,$1,'historical',1000,1060,60)", historical_id)
    scope = (parents[0]['id'],)
    assert await reconcile_missing_round_timing(adapter, enabled=True, round_ids=scope) == 1
    assert await reconcile_missing_round_timing(adapter, enabled=True, round_ids=scope) == 0
    assert await observer.fetchrow('SELECT actual_duration_seconds,round_start_unix,round_canonical_id '
                                  'FROM rounds WHERE id=$1', historical_id) == (None, None, None)
    for _ in range(2):
        result = await import_proximity_file(path, **options)
        assert result.success and result.round_id == parents[0]['id']
        assert result.gaming_session_id == parents[0]['gaming_session_id']
    rows = await observer.fetch('SELECT v.round_id,v.total_distance,r.round_start_unix '
                                'FROM proximity_vehicle_progress v JOIN rounds r ON r.id=v.round_id')
    assert [tuple(r) for r in rows] == [(parents[0]['id'], 100.0, start)]
    async with manager.pool.acquire() as independent:
        assert await independent.fetchval('SELECT count(*) FROM proximity_vehicle_progress') == 1
        assert await independent.fetchval('SELECT sum(total_distance) FROM proximity_vehicle_progress') == 100
    assert await observer.fetchval('SELECT count(*) FROM runtime_events WHERE event_type=\'round_timing_reconciled\'') == 1
    assert await observer.fetchval('SELECT count(*) FROM proximity_processed_files WHERE runtime_parent_gate AND aggregates_applied') == 1
    assert path.read_bytes() == payload
    print('Combined proof: actual R1/R2 -> missing timing defers proximity -> linked synthetic Lua '
          'timing reconciled once in explicit scope -> strict vehicle import/replay, '
          'one shared parent/session, unrelated eligible history untouched, no consumers')
