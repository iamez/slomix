"""Declared timing identity, actual bound Lua and sealed admission, no live ET."""

import hashlib
import json
from dataclasses import replace

import pytest

from bot.runtime_gametime_retention import retain_gametime_source
from bot.runtime_gametime_source import parse_verified_gametime
from shared.runtime_round_identity import RoundIdentity, stats_header_identity
from tests.unit.test_runtime_gametime_independence import run
from tests.unit.test_runtime_gametime_source import NAME, document, parse
from tests.unit.test_runtime_stats_dispatch import dispatched_pair

IDENTITY = RoundIdentity('fixture-server', 'a' * 32, 'b' * 32, 1, 'b' * 32)


@pytest.mark.parametrize('expected', [None, IDENTITY])
def test_valid_declaration_retained_by_reader(tmp_path, expected):
    data = document()
    data['meta']['runtime_identity'] = IDENTITY.encode()
    result = parse(tmp_path, json.dumps(data).encode(), expected_identity=expected)
    assert result.declared_identity == IDENTITY
    assert result.actual_duration_seconds == 600


def test_legacy_absence_is_explicit_and_strict_policy_rejects(tmp_path):
    assert parse(tmp_path).declared_identity is None
    with pytest.raises(ValueError, match='missing or conflicts'):
        parse(tmp_path, expected_identity=IDENTITY)


@pytest.mark.parametrize('wire', [None, '', True, {}, 12, 'x' * 201,
    IDENTITY.encode().replace('fixture-server', 'other'),
    RoundIdentity('fixture-server', 'a' * 32, 'c' * 32, 2, 'b' * 32).encode()])
def test_present_invalid_or_inconsistent_declaration_never_degrades_to_legacy(tmp_path, wire):
    data = document()
    data['meta']['runtime_identity'] = wire
    with pytest.raises(ValueError):
        parse(tmp_path, json.dumps(data).encode())


@pytest.mark.parametrize('expected', [True, {}, 'wire'])
def test_bad_expected_type_rejects_before_descriptor(expected):
    with pytest.raises(ValueError, match='Explicit expected'):
        parse_verified_gametime(-1, source_id='fixture-server', generation='a' * 32,
            filename=NAME, expected_size=1, expected_sha256='a' * 64, expected_identity=expected)


async def test_conflicting_expected_match_rejects_before_database(tmp_path):
    data = document()
    data['meta']['runtime_identity'] = IDENTITY.encode()
    raw = json.dumps(data).encode()
    path = tmp_path / NAME
    path.write_bytes(raw)
    with path.open('rb') as stream, pytest.raises(ValueError, match='missing or conflicts'):
        await retain_gametime_source(None, stream.fileno(), source_id='fixture-server',
            generation='c' * 32, filename=NAME, expected_size=len(raw),
            expected_sha256=hashlib.sha256(raw).hexdigest(),
            expected_identity=replace(IDENTITY, match_id='d' * 32))


@pytest.mark.parametrize('half', [1, 2])
@pytest.mark.parametrize('fault', ['none', 'replace'])
def test_actual_bound_hook_freezes_identity_and_writes_admissible_file(tmp_path, half, fault):
    identity = IDENTITY if half == 1 else replace(IDENTITY, round_id='c' * 32, round_number=2)
    output = run(tmp_path, enabled=False, target=False, mode='frame', identity=identity, binding_fault=fault)
    assert 'BIND=true:' + identity.encode() in output
    assert 'COUNTS launches=0 opens=1 shell=1' in output
    name = NAME.replace('R1', f'R{half}')
    raw = (tmp_path / name).read_bytes()
    assert json.loads(raw)['meta']['runtime_identity'] == identity.encode()
    admitted = parse(tmp_path, raw, filename=name, expected_identity=identity)
    assert admitted.declared_identity == identity


@pytest.mark.parametrize('fault', ['noinit', 'wrong-half', 'wrong-map', 'warmup'])
def test_binding_requires_observed_matching_active_context(tmp_path, fault):
    output = run(tmp_path, enabled=False, target=False, mode='frame', identity=IDENTITY, binding_fault=fault)
    assert 'BIND=false:' in output
    assert 'COUNTS launches=0 opens=0 shell=0' in output
    assert not (tmp_path / NAME).exists()


@pytest.mark.parametrize('half', [1, 2])
@pytest.mark.parametrize('fault', ['reset', 'end-half', 'end-map', 'end-counter', 'end-state', 'end-gametype'])
def test_bound_context_change_never_falls_back_to_legacy(tmp_path, fault, half):
    identity = IDENTITY if half == 1 else replace(IDENTITY, round_id='c' * 32, round_number=2)
    output = run(tmp_path, enabled=False, target=False, mode='send', identity=identity, binding_fault=fault)
    assert 'BIND=true:' in output
    assert 'crashed:' in output
    assert 'COUNTS launches=0 opens=0 shell=0' in output
    assert not list(tmp_path.glob('gametime-*.json'))


def test_actual_stats_ipc_and_timing_share_explicit_pair(tmp_path):
    stats = dispatched_pair(tmp_path / 'stats', ipc=True)
    identities = []
    for half, artifact in enumerate(stats, 1):
        with (artifact.root / artifact.generation / artifact.filename).open() as stream:
            identity = stats_header_identity(stream.readline())
        timing = tmp_path / f'timing{half}'
        timing.mkdir()
        output = run(timing, enabled=False, target=False, mode='frame', identity=identity)
        assert 'COUNTS launches=0 opens=1 shell=1' in output
        name = NAME.replace('R1', f'R{half}')
        result = parse(timing, (timing / name).read_bytes(), filename=name, expected_identity=identity)
        assert result.declared_identity == identity
        identities.append(identity)
    assert identities[0].match_id == identities[1].match_id
    assert identities[0].round_id == identities[1].first_round_id
    assert identities[0].round_id != identities[1].round_id
