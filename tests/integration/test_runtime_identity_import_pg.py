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
