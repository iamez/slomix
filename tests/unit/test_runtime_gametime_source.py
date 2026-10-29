"""Real sealed descriptor and producer-body evidence; no services or DB writes."""

import copy
import errno
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

import pytest

import bot.runtime_gametime_source as admission

NAME = 'gametime-supply-R1-1700000610.json'


def document():
    return {'meta': {'map': 'supply', 'round': 1, 'round_start_unix': 1700000000,
        'round_end_unix': 1700000610, 'actual_duration_seconds': 600,
        'pause_seconds': 10, 'pause_count': 1, 'spawn_stats': []},
        'payload': {'embeds': [{'fields': [{'name': key, 'value': value} for key, value in {
            'Map': 'supply', 'Round': '1', 'Lua_RoundStart': '1700000000',
            'Lua_RoundEnd': '1700000610', 'Lua_Playtime': '600 sec', 'Lua_Pauses': '1 (10 sec)',
        }.items()]}]}}


def parse(tmp_path, payload=None, **overrides):
    payload = json.dumps(document()).encode() if payload is None else payload
    source = tmp_path / 'input'
    source.write_bytes(payload)
    args = dict(source_id='fixture-server', generation='a' * 32, filename=NAME,
                expected_size=len(payload), expected_sha256=hashlib.sha256(payload).hexdigest())
    args.update(overrides)
    owned = []
    create_memfd = os.memfd_create

    def record_memfd(*args, **kwargs):
        fd = create_memfd(*args, **kwargs)
        owned.append(fd)
        return fd

    with source.open('rb') as stream:
        stream.seek(3)
        try:
            with patch.object(os, 'memfd_create', side_effect=record_memfd):
                return admission.parse_verified_gametime(stream.fileno(), **args)
        finally:
            assert stream.tell() == 3
            # Whole-process FD equality also observes unrelated GC/async cleanup.
            # Inspect the descriptors this operation actually allocated instead.
            for fd in owned:
                with pytest.raises(OSError) as closed:
                    os.fstat(fd)
                assert closed.value.errno == errno.EBADF


@pytest.mark.parametrize('reject', [False, True])
def test_unrelated_fd_cleanup_does_not_mask_admission(tmp_path, monkeypatch, reject):
    first, second = os.pipe()
    original = admission._decode_timing  # noqa: SLF001 -- synchronous cleanup injection seam.
    pending = [first, second]

    def decode(*args):
        while pending:
            os.close(pending.pop())
        return original(*args)

    monkeypatch.setattr(admission, '_decode_timing', decode)
    try:
        if reject:
            source = document()
            source['unused'] = [0] * 50_001
            with pytest.raises(ValueError, match='structure'):
                parse(tmp_path, json.dumps(source).encode())
        else:
            assert parse(tmp_path).round_number == 1
    finally:
        while pending:
            os.close(pending.pop())


def test_owned_fd_leak_still_fails_guard(tmp_path, monkeypatch):
    from _pytest.outcomes import Failed

    close = os.close
    leaked = []

    def retain_fd(fd):
        leaked.append(fd)

    # The snapshot's close is the only os.close in this synchronous operation.
    # Keep real cleanup in finally even when the guard catches the injected leak.
    try:
        with monkeypatch.context() as change:
            change.setattr(os, 'close', retain_fd)
            with pytest.raises(Failed, match='DID NOT RAISE'):
                parse(tmp_path)
        assert len(leaked) == 1
    finally:
        for fd in leaked:
            close(fd)


@pytest.mark.parametrize('encoded', [False, True])
def test_real_snapshot_returns_only_immutable_verified_projection(tmp_path, encoded):
    source = document()
    if encoded:
        source['payload'] = json.dumps(source['payload'])
    result = parse(tmp_path, json.dumps(source).encode())
    assert (result.map_name, result.round_number, result.actual_duration_seconds,
            result.total_pause_seconds, result.pause_count) == ('supply', 1, 600, 10, 1)
    assert result.round_end_unix - result.round_start_unix == 610
    assert (result.source_id, result.generation, result.filename) == ('fixture-server', 'a' * 32, NAME)
    assert not hasattr(result, 'spawn_stats') and not hasattr(result, 'round_id')
    with pytest.raises(FrozenInstanceError):
        result.round_number = 2


@pytest.mark.parametrize('field', ['map', 'round', 'round_start_unix', 'round_end_unix',
    'actual_duration_seconds', 'pause_seconds', 'pause_count'])
def test_missing_meta_evidence_rejects(tmp_path, field):
    source = document()
    source['meta'].pop(field)
    with pytest.raises(ValueError):
        parse(tmp_path, json.dumps(source).encode())


@pytest.mark.parametrize('field,value', [('map', 'oasis'), ('round', 2), ('round', 0),
    ('round', True), ('round_start_unix', 1700000001), ('round_end_unix', 1700000611),
    ('actual_duration_seconds', 601), ('pause_seconds', 11), ('pause_count', 2),
    ('actual_duration_seconds', '600'), ('actual_duration_seconds', 600.0),
    ('round_start_unix', 2**63), ('pause_count', 2**31)])
def test_meta_conflicts_or_invalid_types_reject(tmp_path, field, value):
    source = document()
    source['meta'][field] = value
    with pytest.raises(ValueError):
        parse(tmp_path, json.dumps(source).encode())


@pytest.mark.parametrize('index', range(6))
def test_missing_embed_evidence_rejects(tmp_path, index):
    source = document()
    source['payload']['embeds'][0]['fields'].pop(index)
    with pytest.raises(ValueError):
        parse(tmp_path, json.dumps(source).encode())


def test_conflicting_embed_and_case_duplicate_never_use_last_value(tmp_path):
    source = document()
    source['payload']['embeds'][0]['fields'][0]['value'] = 'oasis'
    with pytest.raises(ValueError, match='conflict'):
        parse(tmp_path, json.dumps(source).encode())
    source = document()
    source['payload']['embeds'][0]['fields'].append({'name': 'map', 'value': 'supply'})
    with pytest.raises(ValueError, match='Duplicate'):
        parse(tmp_path, json.dumps(source).encode())


@pytest.mark.parametrize('encoded', [False, True])
def test_duplicate_json_keys_are_rejected_at_both_envelopes(tmp_path, encoded):
    source = document()
    payload = json.dumps(source)
    if encoded:
        source['payload'] = '{"embeds":[],"embeds":' + json.dumps(source['payload']['embeds']) + '}'
        payload = json.dumps(source)
    else:
        payload = payload.replace('"meta":', '"meta":{},"meta":', 1)
    with pytest.raises(ValueError, match='Duplicate'):
        parse(tmp_path, payload.encode())


@pytest.mark.parametrize('constant', ['NaN', 'Infinity', '-Infinity', '1e999'])
def test_nonfinite_anywhere_is_rejected(tmp_path, constant):
    payload = json.dumps(document()).replace('"meta":', f'"unused":{constant},"meta":', 1)
    with pytest.raises(ValueError, match='Nonfinite'):
        parse(tmp_path, payload.encode())


@pytest.mark.parametrize('overrides', [dict(filename='../' + NAME), dict(filename=NAME.replace('R1', 'R0')),
    dict(filename=NAME.replace('supply', 'oasis')), dict(filename=NAME.replace('0610', '0611')),
    dict(source_id=''), dict(source_id='a/b'), dict(generation='B' * 32),
    dict(expected_size=True), dict(expected_size=admission.MAX_GAMETIME_BYTES + 1),
    dict(expected_sha256='0' * 64), dict(expected_sha256=None)])
def test_bad_caller_expectations_fail_before_admission(tmp_path, overrides):
    with pytest.raises(ValueError):
        parse(tmp_path, **overrides)


def test_snapshot_not_reopened_after_source_changes(tmp_path, monkeypatch):
    original = admission._decode_timing  # noqa: SLF001 -- mutate source at the exact sealed-decode boundary
    def decode(payload, identity, source_id, expected_round):
        (tmp_path / 'input').write_bytes(b'corrupt source after sealing')
        assert json.loads(payload)['meta']['round_start_unix'] == 1700000000
        return original(payload, identity, source_id, expected_round)
    monkeypatch.setattr(admission, '_decode_timing', decode)
    result = parse(tmp_path)
    assert result.actual_duration_seconds == 600
    print('GAMETIME SNAPSHOT PROOF: original timing survives source replacement; descriptors closed')


def test_agreeing_but_impossible_timing_rejects(tmp_path):
    source = document()
    source['meta']['actual_duration_seconds'] = 610
    source['payload']['embeds'][0]['fields'][4]['value'] = '610 sec'
    with pytest.raises(ValueError, match='wall-clock'):
        parse(tmp_path, json.dumps(source).encode())


def test_round_two_keeps_physical_half_and_explicit_zero_measurements(tmp_path):
    source = document()
    source['meta'].update(round=2, actual_duration_seconds=0, pause_seconds=0, pause_count=0)
    entries = source['payload']['embeds'][0]['fields']
    entries[1]['value'] = '2'
    entries[4]['value'] = '0 sec'
    entries[5]['value'] = '0 (0 sec)'
    result = parse(tmp_path, json.dumps(source).encode(), filename=NAME.replace('R1', 'R2'))
    assert result.round_number == 2 and result.actual_duration_seconds == result.total_pause_seconds == 0


def test_structure_node_limit(tmp_path):
    source = document()
    source['unused'] = [0] * 50_001
    with pytest.raises(ValueError, match='structure'):
        parse(tmp_path, json.dumps(source).encode())


def test_sanitized_filename_is_not_assumed_to_prove_original_map(tmp_path):
    source = document()
    source['meta']['map'] = 'supply.extra'
    source['payload']['embeds'][0]['fields'][0]['value'] = 'supply.extra'
    with pytest.raises(ValueError, match='conflict'):
        parse(tmp_path, json.dumps(source).encode(), filename=NAME.replace('supply', 'supply_extra'))


def test_fresh_process_admits_file_without_discord_or_bot_runtime(tmp_path):
    expected = parse(tmp_path)
    script = '''
import sys
from bot.runtime_gametime_source import parse_verified_gametime
with open(sys.argv[1], 'rb') as source:
    timing = parse_verified_gametime(source.fileno(), source_id='fixture-server',
        generation='a'*32, filename=sys.argv[2], expected_size=int(sys.argv[3]),
        expected_sha256=sys.argv[4])
assert 'discord' not in sys.modules and 'bot.ultimate_bot' not in sys.modules
print(timing.map_name, timing.round_number, timing.actual_duration_seconds)
'''
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path / 'input'),
        expected.filename, str(expected.size), expected.sha256],
        text=True, capture_output=True, timeout=10, check=True)
    assert result.stdout.strip() == 'supply 1 600'
    print('GAMETIME PROCESS PROOF: sealed file -> supply/R1/600s without Discord/runtime services')


def test_excessive_structure_and_invalid_utf8_reject(tmp_path):
    source = document()
    nested = []
    for _ in range(35):
        nested = [nested]
    source['unused'] = nested
    with pytest.raises(ValueError, match='structure'):
        parse(tmp_path, json.dumps(source).encode())
    with pytest.raises(ValueError):
        parse(tmp_path, b'\xff')


def test_decoder_cannot_override_verified_identity(tmp_path, monkeypatch):
    original = admission.WebhookRoundMetadataService.decode_gametime_document
    def corrupt(self, source):
        fields, metadata, spawns = original(self, source)
        metadata['round_number'] = 2
        return fields, metadata, spawns
    monkeypatch.setattr(admission.WebhookRoundMetadataService, 'decode_gametime_document', corrupt)
    with pytest.raises(ValueError, match='decoder disagrees'):
        parse(tmp_path)


def test_current_lua_writer_body_emits_admissible_timing(tmp_path):
    """Real writer formatting, stub filesystem/cvars; NOT live ET or transport."""
    lua = shutil.which('lua5.4')
    assert lua is not None, 'Lua5.4 is required for producer contract proof'
    source = (Path(__file__).resolve().parents[2] / 'vps_scripts/stats_discord_webhook.lua').read_text()
    start = source.index('local function write_gametime_file(')
    end = source.index('\n-- ============================================================================', start)
    writer = source[start:end]
    payload = json.dumps(document()['payload'])
    harness = '''
local captured, captured_name
configuration = {gametimes_enabled=true}
function get_gametimes_dir() return '/fixture' end
function ensure_dir(_) end
function log(_) end
function json_escape(s) return s end
et = {trap_Cvar_Get=function(_) return '' end}
io.open = function(name, _)
  captured_name = name
  return {write=function(self, bytes) captured=bytes; return self end, close=function(_) return true end}
end
'''
    # Fixed synthetic inputs have no Lua long-bracket terminator.
    harness += writer + '\nassert(write_gametime_file([=[' + payload + ']=], {'
    harness += "mapname='supply',round=1,round_start_unix=1700000000,round_end_unix=1700000610,"
    harness += "actual_duration_seconds=600,pause_seconds=10,pause_count=1,warmup_seconds=5,spawn_stats_json='[]'}))\n"
    harness += 'print(captured_name)\nprint(captured)\n'
    output = subprocess.run([lua, '-'], input=harness, text=True, capture_output=True, timeout=10, check=True)
    name, emitted = output.stdout.split('\n', 1)
    assert name == '/fixture/' + NAME
    # Independent field measurement of the emitted source, then actual sealed IO.
    actual = json.loads(emitted)
    assert actual['meta']['actual_duration_seconds'] == 600
    expected = copy.deepcopy(document()['meta'])
    assert {key: actual['meta'][key] for key in expected} == expected
    result = parse(tmp_path, emitted.encode())
    assert result.actual_duration_seconds == 600 and result.total_pause_seconds == 10
    print('LUA WRITER -> SEALED GAMETIME: supply/R1/600s + 10s pause, no database or service')
