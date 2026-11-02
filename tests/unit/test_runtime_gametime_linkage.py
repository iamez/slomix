"""Evidence classification is read-only and cannot authorize a bootstrap link."""

import json
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.runtime_gametime_linkage import inspect_gametime_link
from bot.services.lua_correction_inbox import correction_payload_digest

SOURCE = dict(source_id='fixture-server', generation='a' * 32)


def row(rid=1, *, start=1000, end=1610, map_name='supply', half=1):
    payload = dict(map_name='supply', round_number=1, round_start_unix=1000,
                   round_end_unix=1610, actual_duration_seconds=600,
                   total_pause_seconds=10, pause_count=1)
    return dict(input_id=7, filename='gametime-supply-R1-1610.json', source_sha256='a' * 64,
        payload_version=1, payload_digest=correction_payload_digest(payload), payload=json.dumps(payload),
        map_name='supply', round_number=1, round_start_unix=1000,
        candidate_id=rid, candidate_map=map_name, candidate_half=half,
        candidate_start=start, candidate_end=end)


@pytest.mark.parametrize('rows,scope,status,candidate', [
    ([], [1], 'source_missing', None),
    ([row(None)], [1], 'missing_parent', None),
    ([row()], [1], 'candidate_in_scope', 1),
    ([row(end=None)], [1], 'candidate_in_scope', 1),
    ([row(start=None)], [1], 'needs_timing_evidence', None),
    ([row(start=0)], [1], 'needs_timing_evidence', None),
    ([row(start=999)], [1], 'timing_conflict', None),
    ([row(end=1611)], [1], 'timing_conflict', None),
    ([row(map_name='oasis')], [1], 'identity_mismatch', None),
    ([row(half=0)], [1], 'identity_mismatch', None),
    ([row(half=2)], [1], 'identity_mismatch', None),
    ([row(), row(2)], [1, 2], 'ambiguous', None),
    ([row(), row(2, start=None)], [1, 2], 'ambiguous', None),
    ([row(), row(2, end=1600)], [1, 2], 'ambiguous', None),
    ([row(start=None), row(2, start=None)], [1, 2], 'ambiguous', None),
    ([row(), row(2, start=900)], [1, 2], 'candidate_in_scope', 1),
    ([row(), row(2, half=0)], [1, 2], 'candidate_in_scope', 1),
    ([row()], [1, 2], 'incomplete_scope', None),
])
async def test_classification_preserves_uncertainty(rows, scope, status, candidate):
    adapter = SimpleNamespace(fetch_all=AsyncMock(return_value=rows))
    result = await inspect_gametime_link(adapter, **SOURCE, round_ids=scope)
    assert result.status == status and result.candidate_round_id == candidate
    assert adapter.fetch_all.await_count == 1
    assert result.requested_round_ids == tuple(scope)
    if status == 'source_missing':
        assert result.missing_round_ids is None and result.input_id is None
    elif status == 'missing_parent':
        assert result.missing_round_ids == (1,) and result.input_id == 7
    elif status == 'incomplete_scope':
        assert result.missing_round_ids == (2,)
    with pytest.raises(FrozenInstanceError):
        result.status = 'candidate_in_scope'


@pytest.mark.parametrize('scope', [None, {1}, [True], [0], [-1], [2**31], [1.0], ['1'], [1] * 101])
async def test_invalid_scope_rejects_before_db(scope):
    with pytest.raises(ValueError):
        await inspect_gametime_link(None, **SOURCE, round_ids=scope)


async def test_empty_scope_is_not_unmeasured_missing_source():
    result = await inspect_gametime_link(None, **SOURCE, round_ids=[])
    assert result.status == 'empty_scope'
    assert result.missing_round_ids == () and result.candidate_round_id is None


@pytest.mark.parametrize('overrides', [dict(source_id='UPPER'), dict(source_id=''),
    dict(source_id='x\n'), dict(generation='B' * 32), dict(generation='../x')])
async def test_identity_rejects_before_db(overrides):
    with pytest.raises(ValueError):
        await inspect_gametime_link(None, **(SOURCE | overrides), round_ids=[1])


async def test_scope_is_copied_before_await_and_deduplicated():
    scope = [1, 1]

    async def read(query, params):
        scope.append(2)
        assert params == ([1], SOURCE['source_id'], SOURCE['generation'])
        return [row()]

    result = await inspect_gametime_link(SimpleNamespace(fetch_all=read), **SOURCE, round_ids=scope)
    assert result.requested_round_ids == (1,)


async def test_storage_errors_propagate_instead_of_missing():
    adapter = SimpleNamespace(fetch_all=AsyncMock(side_effect=RuntimeError('fixture offline')))
    with pytest.raises(RuntimeError, match='fixture offline'):
        await inspect_gametime_link(adapter, **SOURCE, round_ids=[1])


@pytest.mark.parametrize('fault', ['digest', 'incomplete', 'scope'])
async def test_invalid_evidence_is_not_a_candidate(fault):
    stored = row()
    if fault == 'digest':
        stored['payload_digest'] = '0' * 64
    elif fault == 'incomplete':
        payload = json.loads(stored['payload'])
        payload.pop('round_end_unix')
        stored.update(payload=json.dumps(payload), payload_digest=correction_payload_digest(payload))
    else:
        stored['candidate_id'] = 2
    adapter = SimpleNamespace(fetch_all=AsyncMock(return_value=[stored]))
    with pytest.raises(ValueError):
        await inspect_gametime_link(adapter, **SOURCE, round_ids=[1])
