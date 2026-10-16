"""Canonical full R2 result parity with actual Linux-sealed files."""

import hashlib
import os
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path

import pytest

from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.runtime_snapshot_pair import RoundSnapshotInput, parse_sealed_round_pair


def _without_timestamps(value):
    """Discard only nondeterministic parser wall-clock fields at any depth."""
    if isinstance(value, dict):
        return {k: _without_timestamps(v) for k, v in value.items() if k != 'timestamp'}
    if isinstance(value, list):
        return [_without_timestamps(v) for v in value]
    return value


@pytest.fixture
def pair(tmp_path):
    """Real minimal stats inputs with valid canonical player records."""
    with ExitStack() as stack:
        inputs, paths = [], []
        for number in (1, 2):
            name = f'2026-09-25-120000-supply-round-{number}.txt'
            payload = (f'x\\supply\\x\\{number}\\2\\1\\20:00\\10:00\n'
                       f'12345678\\^1Player\\1\\1\\{number} {number} {number} {number} {number} {number}\n').encode()
            path = tmp_path / name
            path.write_bytes(payload)
            stream = stack.enter_context(path.open('rb'))
            inputs.append(RoundSnapshotInput(name, stream.fileno(), len(payload), hashlib.sha256(payload).hexdigest()))
            paths.append(path)
        yield inputs, paths


def test_full_differential_and_summary_match_despite_source_rewrite(pair, monkeypatch):
    """Both inputs remain immutable; the real legacy assembly supplies every field."""
    inputs, paths = pair
    parser = C0RNP0RN3StatsParser()
    baseline = parser.parse_round_2_with_differential(str(paths[1]))
    assert baseline['success'] and baseline['players']
    assert baseline['match_summary']['players']
    real_parse = C0RNP0RN3StatsParser.parse_regular_stats_file
    seen = []
    def parse(self, path):
        seen.append(path)
        for source in paths:
            source.write_bytes(b'changed after both snapshots sealed')
        assert path.startswith('/proc/self/fd/')
        return real_parse(self, path)
    def forbid_discovery(*args):
        pytest.fail('mutable filesystem discovery attempted')
    monkeypatch.setattr(C0RNP0RN3StatsParser, 'parse_regular_stats_file', parse)
    monkeypatch.setattr(C0RNP0RN3StatsParser, 'find_corresponding_round_1_file', forbid_discovery)
    before = set(os.listdir('/proc/self/fd'))
    result = parse_sealed_round_pair(*inputs)
    assert _without_timestamps(result) == _without_timestamps(baseline)
    assert result['r1_filename'] == inputs[0].filename
    assert len(seen) == 2 and len(set(seen)) == 2
    assert all(not Path(path).exists() for path in seen)
    assert set(os.listdir('/proc/self/fd')) == before
    print('R2 proof: full differential and match summary match legacy; both sources corrupted; no discovery')


@pytest.mark.parametrize('change', [
    {'filename': '2026-09-25-110000-supply-round-2.txt'},
    {'filename': '2026-09-25-124501-supply-round-2.txt'},
    {'filename': '2026-09-25-120000-oasis-round-2.txt'},
    {'filename': '2026-02-30-120000-supply-round-2.txt'},
    {'sha256': '0' * 64},
])
def test_invalid_second_input_never_parses_or_leaks(pair, monkeypatch, change):
    """Even if R1 was already copied, failed R2 validation closes all snapshots."""
    inputs, _ = pair
    def forbidden(*args):
        pytest.fail('invalid pair reached parser')
    monkeypatch.setattr(C0RNP0RN3StatsParser, 'parse_regular_stats_file', forbidden)
    before = set(os.listdir('/proc/self/fd'))
    with pytest.raises(ValueError):
        parse_sealed_round_pair(inputs[0], replace(inputs[1], **change))
    assert set(os.listdir('/proc/self/fd')) == before


@pytest.mark.parametrize('first_name,second_name', [
    ('2026-09-25-120000-supply-round-1.txt', '2026-09-25-124500-supply-round-2.txt'),
    ('2026-09-25-235000-supply-round-1.txt', '2026-09-26-001000-supply-round-2.txt'),
])
def test_boundary_and_midnight_pair_keep_logical_identity(pair, first_name, second_name):
    """Explicit valid matching includes the window edge and previous-day R1."""
    inputs, _ = pair
    result = parse_sealed_round_pair(replace(inputs[0], filename=first_name),
                                     replace(inputs[1], filename=second_name))
    assert result['success'] is True
    assert result['r1_filename'] == first_name
    assert result['round_num'] == 2
    assert result['match_summary']['round_num'] == 0


def test_valid_digest_with_wrong_round_header_is_rejected(pair, monkeypatch):
    """A digest of authentic bytes still does not prove correct round identity."""
    inputs, paths = pair
    payload = paths[1].read_bytes().replace(b'\\2\\2\\1\\20:00', b'\\1\\2\\1\\20:00')
    paths[1].write_bytes(payload)
    changed = replace(inputs[1], size=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    def forbidden(*args):
        pytest.fail('wrong header reached parser')
    monkeypatch.setattr(C0RNP0RN3StatsParser, 'parse_regular_stats_file', forbidden)
    before = set(os.listdir('/proc/self/fd'))
    with pytest.raises(ValueError, match='header identity'):
        parse_sealed_round_pair(inputs[0], changed)
    assert set(os.listdir('/proc/self/fd')) == before
