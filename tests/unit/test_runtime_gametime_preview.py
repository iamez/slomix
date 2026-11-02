"""Bounded no-write timing policy, including whole shipped Lua/file execution."""

import copy
import hashlib
import json
from dataclasses import FrozenInstanceError

import pytest

from bot.runtime_gametime_preview import TIMING_FILL_FIELDS, preview_declared_timing_fill
from tests.unit.test_runtime_gametime_correlation import fixture_data
from tests.unit.test_runtime_gametime_independence import run as run_lua
from tests.unit.test_runtime_gametime_source import NAME
from tests.unit.test_runtime_round_identity import FIRST, SECOND


def current(**overrides):
    return dict(id=11, map_name='supply', round_number=1,
                **({'actual_duration_seconds': None, 'total_pause_seconds': 0,
                    'pause_count': 0} | overrides))


def preview(tmp_path, row=None, *, transform=None, identity=FIRST):
    raw, binding, _ = fixture_data(identity)
    if transform:
        doc = json.loads(raw)
        transform(doc)
        raw = json.dumps(doc).encode()
        binding.update(expected_size=len(raw), expected_sha256=hashlib.sha256(raw).hexdigest())
    path = tmp_path / 'timing.json'
    path.write_bytes(raw)
    if row is None:
        row = current()
        row['round_number'] = identity.round_number
    before = copy.deepcopy(row)
    with path.open('rb') as stream:
        stream.seek(3)
        try:
            return preview_declared_timing_fill(stream.fileno(), row, **binding)
        finally:
            assert stream.tell() == 3
            assert path.read_bytes() == raw
            assert row == before


def set_timing(doc, duration=600, pauses=10, count=1):
    doc['meta'].update(actual_duration_seconds=duration, pause_seconds=pauses, pause_count=count)
    for field in doc['payload']['embeds'][0]['fields']:
        if field['name'] == 'Lua_Playtime':
            field['value'] = f'{duration} sec'
        elif field['name'] == 'Lua_Pauses':
            field['value'] = f'{count} ({pauses} sec)'


@pytest.mark.parametrize('identity', [FIRST, SECOND])
@pytest.mark.parametrize('pause_default', [None, 0])
def test_fill_diff_is_explicit_immutable_and_only_three_scalars(tmp_path, identity, pause_default):
    row = current(total_pause_seconds=pause_default, pause_count=pause_default)
    row.update(round_number=identity.round_number, round_start_unix=42, round_end_unix=43,
               round_canonical_id='do-not-rekey', actual_time='20:00', winner_team=2,
               player_stats={'dpm': 123, 'time_played_seconds': 450})
    result = preview(tmp_path, row, identity=identity)
    assert result.status == 'proposed'
    assert [(item.field, item.before, item.after) for item in result.changes] == [
        ('actual_duration_seconds', None, 600), ('total_pause_seconds', pause_default, 10),
        ('pause_count', pause_default, 1)]
    assert tuple(item.field for item in result.changes) == TIMING_FILL_FIELDS
    with pytest.raises(FrozenInstanceError):
        result.status = 'applied'
    with pytest.raises(FrozenInstanceError):
        result.changes[0].after = 1


@pytest.mark.parametrize('duration', [0, 599, 600, 601])
def test_existing_duration_never_overwritten_even_if_equal(tmp_path, duration):
    result = preview(tmp_path, current(actual_duration_seconds=duration))
    assert result.status == 'conflict'
    assert result.reason == 'existing_duration_requires_reconciliation'
    assert result.changes == ()


def test_equal_values_without_receipt_are_not_success(tmp_path):
    result = preview(tmp_path, current(actual_duration_seconds=600, total_pause_seconds=10, pause_count=1))
    assert result.status == 'existing_values_unproven'
    assert result.changes == ()


@pytest.mark.parametrize('field,value', [('total_pause_seconds', 10), ('pause_count', 1),
                                        ('total_pause_seconds', 11), ('pause_count', 2)])
def test_nonzero_pause_measurements_are_not_default_slots(tmp_path, field, value):
    result = preview(tmp_path, current(**{field: value}))
    assert result.status == 'conflict'
    assert result.reason == 'existing_pause_measurement_requires_reconciliation'
    assert result.changes == ()


@pytest.mark.parametrize('duration,pauses,count,status,reason', [
    (0, 610, 1, 'unavailable', 'zero_duration_not_a_fill'),
    (599, 10, 1, 'conflict', 'source_timing_ledger_unbalanced'),
    (600, 10, 0, 'conflict', 'source_pause_ledger_inconsistent'),
    (610, 0, 0, 'proposed', 'null_duration_fill_preview_only'),
])
def test_source_ledger_and_no_pause_noop_fields(tmp_path, duration, pauses, count, status, reason):
    result = preview(tmp_path, transform=lambda doc: set_timing(doc, duration, pauses, count))
    assert (result.status, result.reason) == (status, reason)
    if status == 'proposed':
        assert [(item.field, item.after) for item in result.changes] == [('actual_duration_seconds', 610)]
    else:
        assert result.changes == ()


@pytest.mark.parametrize('field', ['actual_duration_seconds', 'total_pause_seconds', 'pause_count'])
@pytest.mark.parametrize('value', [True, -1, 1.0, '0', 2**31, float('inf')])
def test_invalid_current_measurement_fails_closed(tmp_path, field, value):
    with pytest.raises(ValueError, match='Invalid current timing'):
        preview(tmp_path, current(**{field: value}))


@pytest.mark.parametrize('field', ['id', 'map_name', 'round_number', *TIMING_FILL_FIELDS])
def test_missing_row_keys_are_not_null_defaults(tmp_path, field):
    row = current()
    del row[field]
    with pytest.raises(ValueError, match='incomplete'):
        preview(tmp_path, row)


@pytest.mark.parametrize('field,value', [('id', True), ('id', 0), ('id', 2**31),
                                       ('round_number', 0), ('round_number', True), ('map_name', None)])
def test_invalid_target_identity_rejected(tmp_path, field, value):
    row = current()
    row[field] = value
    with pytest.raises(ValueError):
        preview(tmp_path, row)


@pytest.mark.parametrize('field,value', [('map_name', 'oasis'), ('round_number', 2)])
def test_target_context_mismatch_has_no_diff(tmp_path, field, value):
    row = current()
    row[field] = value
    result = preview(tmp_path, row)
    assert result.status == 'conflict'
    assert result.changes == ()


@pytest.mark.parametrize('identity', [FIRST, SECOND])
def test_whole_lua_to_sealed_preview_preserves_file_and_original_stats(tmp_path, identity):
    output = run_lua(tmp_path, enabled=False, target=False, mode='frame', identity=identity)
    assert 'COUNTS launches=0 opens=1 shell=1' in output
    path = tmp_path / NAME.replace('R1', f'R{identity.round_number}')
    raw = path.read_bytes()
    doc = json.loads(raw)
    row = current()
    row.update(round_number=identity.round_number, actual_time='20:00',
               round_start_unix=1, round_canonical_id='original-stats-key')
    before = copy.deepcopy(row)
    with path.open('rb') as stream:
        result = preview_declared_timing_fill(stream.fileno(), row,
            source_id=identity.source_id, generation='a' * 32, filename=path.name,
            expected_size=len(raw), expected_sha256=hashlib.sha256(raw).hexdigest(), expected_identity=identity)
    assert result.status == 'proposed'
    values = {item.field: item.after for item in result.changes}
    assert values['actual_duration_seconds'] == doc['meta']['actual_duration_seconds'] == 600
    assert values['actual_duration_seconds'] == (doc['meta']['round_end_unix']
        - doc['meta']['round_start_unix'] - doc['meta']['pause_seconds'])
    assert values == dict(actual_duration_seconds=600, total_pause_seconds=10, pause_count=1)
    assert (row, path.read_bytes()) == (before, raw)
    print(f'WHOLE LUA R{identity.round_number} -> sealed dry-run: 3 explicit changes; '
          'duration600 = wall610 - pause10; source and original stats unchanged; NO DB writes')
