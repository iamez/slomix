"""Sealed raw evidence and fresh native-style snapshot guards, without DB writes."""

import copy
import hashlib
import json
from contextlib import asynccontextmanager
from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from bot.runtime_gametime_correlation import inspect_declared_gametime
from bot.services.lua_correction_inbox import correction_payload_digest
from tests.unit.test_runtime_gametime_source import NAME, document
from tests.unit.test_runtime_round_identity import FIRST, SECOND


def fixture_data(identity=FIRST, *, generation='d' * 32, map_name='supply', round_id=11):
    doc = document()
    doc['meta'].update(map=map_name, round=identity.round_number, runtime_identity=identity.encode())
    for field in doc['payload']['embeds'][0]['fields']:
        if field['name'] == 'Round':
            field['value'] = str(identity.round_number)
        elif field['name'] == 'Map':
            field['value'] = map_name
    raw = json.dumps(doc).encode()
    filename = NAME.replace('supply', map_name).replace('R1', f'R{identity.round_number}')
    args = dict(source_id=identity.source_id, generation=generation, filename=filename,
                expected_size=len(raw), expected_sha256=hashlib.sha256(raw).hexdigest(),
                expected_identity=identity)
    projection = dict(map_name=map_name.lower(), round_number=identity.round_number,
        round_start_unix=1700000000, round_end_unix=1700000610,
        actual_duration_seconds=600, total_pause_seconds=10, pause_count=1)
    retained = dict(id=7, source_key=identity.source_id, payload_version=1,
        payload_digest=correction_payload_digest(projection), payload=json.dumps(projection),
        map_name=map_name.lower(), round_number=identity.round_number, round_start_unix=1700000000)
    source = dict(source_key=identity.source_id, generation=generation, filename=filename,
        source_size=len(raw), source_sha256=args['expected_sha256'], input_id=7)
    declared = dict(source_key=identity.source_id, generation=generation, match_id=identity.match_id,
        round_id=identity.round_id, round_number=identity.round_number, first_round_id=identity.first_round_id)
    mappings, parents, events = {}, {}, {}
    halves = ((FIRST, 10), (identity, round_id)) if identity.round_number == 2 else ((identity, round_id),)
    for current, rid in halves:
        current = replace(current, source_id=identity.source_id)
        stats_name = f'2026-10-08-{120000 + (current.round_number - 1) * 1000:06d}-{map_name}-round-{current.round_number}.txt'
        mappings[(current.source_id, current.round_id)] = (
            current.source_id, current.round_id, current.match_id, current.round_number,
            current.first_round_id, map_name, stats_name, rid, 'e' * 64,
        )
        parents[rid] = (map_name, current.round_number, 20, '2026-10-08-120000',
                        stats_name[:10], stats_name[11:17])
        events[rid] = (stats_name, 'e' * 64, True, current.round_number, 20)
    return raw, args, dict(source=source, declared=declared, retained=retained,
                          mappings=mappings, parents=parents, events=events)


def make_observer(data):
    phases = []

    @asynccontextmanager
    async def transaction(**options):
        assert options == dict(isolation='repeatable_read', readonly=True)
        phases.append('open')
        try:
            yield
        finally:
            phases.append('close')

    async def fetchrow(query, *params):
        assert phases[-1] == 'open'
        assert query.startswith('SELECT ') and 'FOR ' not in query
        if 'FROM runtime_gametime_sources' in query:
            assert params == (data['requested_source'], data['requested_generation'])
            return data['source']
        if 'FROM runtime_gametime_identities' in query:
            assert params == (data['requested_source'], data['requested_generation'])
            return data['declared']
        if 'FROM lua_correction_inputs' in query:
            assert params == (7, data['requested_source'])
            return data['retained']
        if 'FROM runtime_round_mappings' in query:
            return data['mappings'].get(params)
        if 'FROM rounds ' in query:
            return data['parents'].get(params[0])
        if 'FROM runtime_events' in query:
            return data['events'].get(params[0])
        raise AssertionError(f'Unexpected query: {query}')

    return SimpleNamespace(is_in_transaction=Mock(return_value=False), transaction=transaction,
                           fetchrow=AsyncMock(side_effect=fetchrow), phases=phases)


def setup(tmp_path, identity=FIRST, **options):
    raw, args, data = fixture_data(identity, **options)
    data.update(requested_source=args['source_id'], requested_generation=args['generation'])
    directory = tmp_path / args['generation']
    directory.mkdir(exist_ok=True)
    path = directory / args['filename']
    path.write_bytes(raw)
    return SimpleNamespace(path=path, args=args, data=data, observer=make_observer(data))


async def inspect(case, **options):
    with case.path.open('rb') as source:
        source.seek(3)
        try:
            return await inspect_declared_gametime(case.observer, source.fileno(), **(case.args | options))
        finally:
            assert source.tell() == 3


@pytest.mark.parametrize('identity', [FIRST, SECOND])
async def test_actual_sealed_projection_to_canonical_parent(identity, tmp_path):
    case = setup(tmp_path, identity)
    before = copy.deepcopy(case.data)
    result = await inspect(case)
    assert (result.status, result.round_id, result.gaming_session_id, result.input_id) == (
        'canonical_target_verified', 11, 20, 7,
    )
    assert case.data == before and case.observer.phases == ['open', 'close']
    with pytest.raises(FrozenInstanceError):
        result.round_id = 99


async def test_raw_map_case_is_only_normalized_for_inbox(tmp_path):
    case = setup(tmp_path, map_name='Supply')
    assert case.data['retained']['map_name'] == 'supply'
    assert (await inspect(case)).status == 'canonical_target_verified'


@pytest.mark.parametrize('value', [None, True, {}, FIRST.encode()])
async def test_independent_identity_is_mandatory_before_any_db_access(tmp_path, value):
    case = setup(tmp_path)
    with pytest.raises(ValueError, match='Independently supplied'):
        await inspect(case, expected_identity=value)
    case.observer.is_in_transaction.assert_not_called()
    case.observer.fetchrow.assert_not_awaited()


@pytest.mark.parametrize('changed', [
    dict(source_id='Fixture-server'), dict(source_id='wrong'),
    dict(expected_identity=replace(FIRST, match_id='f' * 32)),
    dict(generation='D' * 32), dict(expected_sha256='0' * 64),
    dict(expected_size=1), dict(filename=NAME.replace('R1', 'R2')),
])
async def test_bad_binding_or_bytes_fail_before_db(tmp_path, changed):
    case = setup(tmp_path)
    with pytest.raises(ValueError):
        await inspect(case, **changed)
    case.observer.is_in_transaction.assert_not_called()
    case.observer.fetchrow.assert_not_awaited()


@pytest.mark.parametrize('state', [True, None, 0, 'false'])
async def test_existing_or_unknown_transaction_is_refused(tmp_path, state):
    case = setup(tmp_path)
    case.observer.is_in_transaction.return_value = state
    with pytest.raises(RuntimeError, match='outside any transaction'):
        await inspect(case)
    assert case.observer.phases == []
    case.observer.fetchrow.assert_not_awaited()


async def test_missing_retention_is_not_missing_mapping(tmp_path):
    case = setup(tmp_path)
    case.data['source'] = None
    result = await inspect(case)
    assert result.status == 'missing_retention' and result.input_id is None
    assert case.observer.fetchrow.await_count == 1


@pytest.mark.parametrize('field,value', [
    ('source_key', 'other'), ('generation', 'f' * 32), ('filename', 'other.json'),
    ('source_size', 1), ('source_sha256', '0' * 64), ('input_id', None), ('input_id', True),
])
async def test_raw_provenance_contradiction_is_conflict(tmp_path, field, value):
    case = setup(tmp_path)
    case.data['source'][field] = value
    result = await inspect(case)
    assert result.status == 'conflict' and result.round_id is None
    assert case.observer.fetchrow.await_count == 1


@pytest.mark.parametrize('field,value', [
    ('source_key', 'other'), ('generation', 'f' * 32), ('match_id', 'f' * 32),
    ('round_id', 'f' * 32), ('round_number', 2), ('first_round_id', 'f' * 32),
])
async def test_each_retained_declaration_field_is_checked(tmp_path, field, value):
    case = setup(tmp_path)
    case.data['declared'][field] = value
    assert (await inspect(case)).status == 'conflict'


@pytest.mark.parametrize('table', ['declared', 'retained'])
async def test_missing_declared_identity_or_normalized_input_is_conflict(tmp_path, table):
    case = setup(tmp_path)
    case.data[table] = None
    assert (await inspect(case)).status == 'conflict'


@pytest.mark.parametrize('fault', ['source', 'id', 'digest', 'version', 'invalid_json',
                                  'incomplete', 'different', 'extra_field', 'half'])
async def test_normalized_inbox_integrity_and_exact_projection_are_both_required(tmp_path, fault):
    case = setup(tmp_path)
    row = case.data['retained']
    if fault == 'source':
        row['source_key'] = 'other'
    elif fault == 'id':
        row['id'] = 8
    elif fault == 'digest':
        row['payload_digest'] = '0' * 64
    elif fault == 'version':
        row['payload_version'] = 2
    elif fault == 'invalid_json':
        row['payload'] = '{'
    elif fault == 'half':
        row['round_number'] = 2
    else:
        payload = json.loads(row['payload'])
        if fault == 'incomplete':
            payload.pop('pause_count')
        elif fault == 'different':
            payload['actual_duration_seconds'] = 599
        else:
            payload['winner_team'] = 1
        row.update(payload=json.dumps(payload), payload_digest=correction_payload_digest(payload))
    result = await inspect(case)
    assert result.status == 'conflict' and result.round_id is None


@pytest.mark.parametrize('identity', [FIRST, SECOND])
async def test_missing_current_or_first_mapping_stays_pending(tmp_path, identity):
    case = setup(tmp_path, identity)
    key = (FIRST.source_id, FIRST.round_id)
    case.data['mappings'].pop(key)
    result = await inspect(case)
    assert result.status == 'mapping_pending' and result.input_id == 7 and result.round_id is None


@pytest.mark.parametrize('fault', ['mapping_half', 'mapping_map', 'parent_map', 'parent_session',
                                  'event_missing', 'event_validation', 'event_digest'])
async def test_canonical_mapping_parent_and_initial_event_are_checked(tmp_path, fault):
    case = setup(tmp_path)
    mapping_key = (FIRST.source_id, FIRST.round_id)
    if fault.startswith('mapping'):
        row = list(case.data['mappings'][mapping_key])
        row[3 if fault == 'mapping_half' else 5] = 2 if fault == 'mapping_half' else 'oasis'
        case.data['mappings'][mapping_key] = tuple(row)
    elif fault.startswith('parent'):
        row = list(case.data['parents'][11])
        row[0 if fault == 'parent_map' else 2] = 'oasis' if fault == 'parent_map' else None
        case.data['parents'][11] = tuple(row)
    elif fault == 'event_missing':
        case.data['events'].pop(11)
    else:
        row = list(case.data['events'][11])
        row[2 if fault == 'event_validation' else 1] = False if fault == 'event_validation' else '0' * 64
        case.data['events'][11] = tuple(row)
    assert (await inspect(case)).status == 'conflict'


async def test_equal_projection_does_not_transfer_another_artifacts_identity(tmp_path):
    first = setup(tmp_path)
    other_id = replace(FIRST, match_id='f' * 32, round_id='e' * 32, first_round_id='e' * 32)
    other = setup(tmp_path, other_id, generation='f' * 32, round_id=12)
    assert first.data['retained'] == other.data['retained']
    assert (await inspect(first)).round_id == 11
    assert (await inspect(other)).round_id == 12
    other.data['declared'] = first.data['declared']
    assert (await inspect(other)).status == 'conflict'


async def test_different_source_never_borrows_an_inbox_or_mapping(tmp_path):
    other = setup(tmp_path, replace(FIRST, source_id='other'))
    other.data['retained']['source_key'] = FIRST.source_id
    assert (await inspect(other)).status == 'conflict'


async def test_storage_failure_propagates_and_closes_snapshot(tmp_path):
    case = setup(tmp_path)
    case.observer.fetchrow.side_effect = OSError('fixture primary unavailable')
    with pytest.raises(OSError, match='fixture primary unavailable'):
        await inspect(case)
    assert case.observer.phases == ['open', 'close']
