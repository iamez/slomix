"""A header-only reset is a pairing boundary, never a zero baseline."""

import hashlib
from contextlib import ExitStack

import pytest

from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.core.round_contract import derive_round_validity
from bot.runtime_snapshot_pair import RoundSnapshotInput, parse_sealed_round_pair


def _header(number):
    return f'x\\supply\\x\\{number}\\1\\2\\12:00\\11:43\n'


def _player(kills):
    return f'12345678\\Player\\1\\1\\1 5 10 {kills} 3 2\n'


@pytest.fixture
def reset_files(tmp_path):
    paths = [tmp_path / f'2026-10-26-{stamp}-supply-round-{number}.txt'
             for stamp, number in [('210000', 1), ('210130', 1), ('211400', 2)]]
    paths[0].write_text(_header(1) + _player(10))
    paths[1].write_text(_header(1))
    paths[2].write_text(_header(2) + _player(18))
    return paths


@pytest.mark.parametrize('trailing', ['', '\n\t\n'])
def test_reset_boundary_retains_raw_r2_without_counting_it(reset_files, trailing):
    """Older R1 subtraction would turn the known raw 18 kills into 8."""
    old, reset, second = reset_files
    reset.write_text(_header(1) + trailing)
    parser = C0RNP0RN3StatsParser(allow_legacy_r1_fallback=False)
    assert parser.find_corresponding_round_1_file(str(second)) == str(reset)
    assert parser.parse_stats_file(str(old))['success']
    assert not parser.parse_stats_file(str(reset))['success']
    raw = parser.parse_regular_stats_file(str(second))
    result = parser.parse_stats_file(str(second))
    assert result['success'] and result['round_num'] == 2
    assert result['players'] == raw['players']
    assert result['players'][0]['kills'] == 18
    assert result['r1_filename'] == reset.name
    assert result['is_orphan_r2'] is True
    assert result['orphan_r2_reason'] == 'header_only_r1'
    assert 'match_summary' not in result
    validity = derive_round_validity(result, 'supply', [])
    assert validity['is_valid'] is False
    assert validity['is_orphan_r2'] is True


@pytest.mark.parametrize('payload', [
    '', 'broken header\n', _header(1) + 'not a player\n',
    _header(1) + '12345678\\Player\\1\\1\\incomplete\n',
    _header(1).replace('\\12:00\\', '\\bad-time\\'),
    _header(1).replace('\\1\\2\\12:00', '\\1\\axis\\12:00'),
    _header(1).replace('\\supply\\', '\\oasis\\'),
    _header(2),
])
def test_malformed_or_mismatched_r1_is_not_an_empty_baseline(reset_files, payload):
    """Only the explicit valid-header/no-rows state permits orphan retention."""
    _, first, second = reset_files
    first.write_text(payload)
    result = C0RNP0RN3StatsParser().parse_stats_file(str(second))
    assert not result['success']
    assert not result.get('is_orphan_r2')
    assert 'match_summary' not in result


def test_header_only_r2_cannot_succeed(reset_files):
    _, _, second = reset_files
    second.write_text(_header(2))
    result = C0RNP0RN3StatsParser().parse_stats_file(str(second))
    assert not result['success']
    assert not result.get('is_orphan_r2')


@pytest.mark.parametrize('payload,error', [
    ('header only\n', 'insufficient lines'),
    ('header only\nnot a player\n', 'invalid header format'),
])
def test_malformed_header_keeps_historical_error_contract(tmp_path, payload, error):
    """Classifying intact empty headers must preserve existing failure messages."""
    path = tmp_path / '2026-10-26-210130-supply-round-1.txt'
    path.write_text(payload)
    result = C0RNP0RN3StatsParser().parse_stats_file(str(path))
    assert result['success'] is False
    assert result['error'] == error
    assert 'header_only_round' not in result


def test_sealed_reset_pair_keeps_same_orphan_contract(reset_files):
    """The immutable runtime adapter must not reopen mutable logical paths."""
    _, first, second = reset_files
    inputs = []
    with ExitStack() as stack:
        for path in (first, second):
            payload = path.read_bytes()
            stream = stack.enter_context(path.open('rb'))
            inputs.append(RoundSnapshotInput(path.name, stream.fileno(), len(payload),
                                             hashlib.sha256(payload).hexdigest()))
        result = parse_sealed_round_pair(*inputs)
    assert result['success'] and result['is_orphan_r2']
    assert result['players'][0]['kills'] == 18
    assert result['r1_filename'] == first.name
    assert result['orphan_r2_reason'] == 'header_only_r1'
    assert 'match_summary' not in result
