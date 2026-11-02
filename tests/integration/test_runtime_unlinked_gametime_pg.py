"""Real Lua timing file is retained, never guessed onto a stats parent.

Synthetic ET inputs, actual extracted Lua writer, real files and opt-in PG.
No engine, source authentication, physical pairing, consumers or services claimed.
"""

import hashlib
import json
import shutil
from datetime import date

import pytest

from bot.core.database_adapter import PostgreSQLAdapter
from bot.runtime_completed_import import import_completed_round
from bot.runtime_gametime_linkage import inspect_gametime_link
from bot.runtime_gametime_retention import retain_gametime_source
from shared.proximity_import import import_proximity_file
from shared.round_timing_reconcile import reconcile_missing_round_timing
from shared.runtime_spool import publish_proximity_file
from tests.integration.test_runtime_full_import_pg import completed_pair
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db
from tests.unit.test_gametime_writer_io import run_writer

full_import_db = _full_import_db


@pytest.mark.timeout(120)
@pytest.mark.parametrize('timing_first', [True, False])
async def test_actual_timing_file_does_not_bootstrap_unproven_parent(full_import_db, tmp_path, timing_first):
    manager, observer = full_import_db
    adapter = PostgreSQLAdapter('127.0.0.1', 5432, 'unused', 'unused', '')
    adapter.pool = manager.pool  # Explicit disposable pool; no ambient connect.
    lua = shutil.which('lua5.4')
    assert lua is not None, 'Lua5.4 required for real producer-file proof'
    start, end = 1790336990, 1790337600  # Writer end agrees with stats filename time.
    assert 'RESULT=true' in run_writer(lua, tmp_path, start=start)
    timing_path = tmp_path / f'gametime-supply-R1-{end}.json'
    timing_raw = timing_path.read_bytes()
    decoded = json.loads(timing_raw)['meta']
    assert decoded['round_start_unix'] == start and decoded['round_end_unix'] == end
    assert decoded['actual_duration_seconds'] + decoded['pause_seconds'] == end - start
    source_id, generation = 'fixture-server', 'a' * 32

    async def retain():
        with timing_path.open('rb') as stream:
            return await retain_gametime_source(adapter, stream.fileno(),
                source_id=source_id, generation=generation, filename=timing_path.name,
                expected_size=len(timing_raw), expected_sha256=hashlib.sha256(timing_raw).hexdigest())

    retained = await retain() if timing_first else None
    first, second = completed_pair(tmp_path, balanced=True)
    assert (await import_completed_round(manager, first))[0] is True
    assert (await import_completed_round(manager, second, first=first))[0] is True
    parents = await observer.fetch('SELECT id,round_number,gaming_session_id,round_start_unix '
                                   'FROM rounds WHERE round_number IN (1,2) ORDER BY round_number')
    assert len(parents) == 2 and all(row['round_start_unix'] is None for row in parents)
    assert parents[0]['gaming_session_id'] is not None
    assert parents[0]['gaming_session_id'] == parents[1]['gaming_session_id']
    before_rounds = await observer.fetch('SELECT * FROM rounds ORDER BY id')
    before_events = await observer.fetch('SELECT * FROM runtime_events ORDER BY id')
    if retained is None:
        retained = await retain()
    assert await retain() == retained
    scope = [row['id'] for row in parents]
    evidence = await inspect_gametime_link(adapter, source_id=source_id,
                                          generation=generation, round_ids=scope)
    assert evidence.status == 'needs_timing_evidence'
    assert evidence.candidate_round_id is None
    assert [row.status for row in evidence.rounds] == ['missing_start', 'identity_mismatch']
    assert await reconcile_missing_round_timing(adapter, enabled=True, round_ids=scope) == 0
    assert await observer.fetch('SELECT * FROM lua_round_teams') == []

    payload = (f'# PROXIMITY_TRACKER_V4\n# map=supply\n# round=1\n'
               f'# round_start_unix={start}\n# round_end_unix={end}\n'
               '# capabilities=vehicle_tracking:1\n# VEHICLE_PROGRESS\n'
               'tank;script_mover;0;0;0;100;0;0;100;1000;900;0\n').encode()
    name = '2026-09-25-120000-supply-round-1_engagements.txt'
    digest = hashlib.sha256(payload).hexdigest()
    publish_proximity_file(tmp_path, name, [payload], expected_size=len(payload), expected_sha256=digest)
    for _ in range(2):
        result = await import_proximity_file(tmp_path / name, adapter=adapter,
            session_date=date(2026, 9, 25), gametimes_dir=tmp_path,
            expected_size=len(payload), expected_sha256=digest, require_linked_parent=True)
        assert not result.success and result.pending_reason == 'parent_missing'
        assert result.round_id is None and result.gaming_session_id is None

    # Independent observer verifies commit + no unintended parent/aggregate writes.
    assert await observer.fetch('SELECT * FROM rounds ORDER BY id') == before_rounds
    assert await observer.fetch('SELECT * FROM runtime_events ORDER BY id') == before_events
    assert await observer.fetch('SELECT * FROM proximity_processed_files') == []
    assert await observer.fetch('SELECT * FROM proximity_vehicle_progress') == []
    sources = await observer.fetch('SELECT source_key,generation,input_id FROM runtime_gametime_sources')
    assert [tuple(row) for row in sources] == [(source_id, generation, retained.input_id)]
    assert await observer.fetchval('SELECT count(*) FROM runtime_gametime_sources') == len(sources) == 1
    assert await observer.fetchval('SELECT count(*) FROM lua_correction_inputs') == 1
    assert await observer.fetchval('SELECT count(*) FROM proximity_processed_files') == 0
    assert timing_path.read_bytes() == timing_raw and (tmp_path / name).read_bytes() == payload
    for item in (first, second):
        raw = (item.root / item.generation / item.filename).read_bytes()
        assert len(raw) == item.size and hashlib.sha256(raw).hexdigest() == item.sha256
    print(f'UNLINKED FILE PROOF: timing_first={timing_first}, actual Lua file retained once, '
          'R1/R2 unchanged, strict proximity replay still deferred, raw sources preserved')
