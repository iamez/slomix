"""Real legacy parser over sealed input; no importer, database or services."""

import hashlib
import os
from pathlib import Path

import pytest

from bot.community_stats_parser import C0RNP0RN3StatsParser
from shared.runtime_snapshot_parser import parse_sealed_round_one

NAME = '2026-09-25-120000-supply-round-1.txt'
PAYLOAD = b'x\\supply\\x\\1\\2\\1\\20:00\\10:00\n12345678\\^1Player\\1\\1\\1 1 1 1 1 1\n'


def test_real_parser_reads_verified_bytes_after_source_replacement(tmp_path):
    """Actual parser never sees replacement path content and preserves header stats."""
    source = tmp_path / NAME
    source.write_bytes(PAYLOAD)
    parser = C0RNP0RN3StatsParser()
    expected = parser.parse_regular_stats_file(str(source))
    called = []
    def parse(path):
        called.append(path)
        source.write_bytes(b'corrupt replacement')
        assert Path(path).read_bytes() == PAYLOAD
        return parser.parse_regular_stats_file(path)
    with source.open('rb') as original:
        before = set(os.listdir('/proc/self/fd'))
        result = parse_sealed_round_one(original.fileno(), filename=NAME, expected_size=len(PAYLOAD),
                                       expected_sha256=hashlib.sha256(PAYLOAD).hexdigest(), parse_regular=parse)
        assert set(os.listdir('/proc/self/fd')) == before
    assert result['success'] is True
    assert {k: v for k, v in result.items() if k != 'timestamp'} == {
        k: v for k, v in expected.items() if k != 'timestamp'
    }
    assert called[0].startswith('/proc/self/fd/')
    assert not Path(called[0]).exists()
    print('Parser proof: source corrupted after sealing; real parser retains original R1 fields')


@pytest.mark.parametrize('filename,payload', [
    (NAME.replace('round-1', 'round-2'), PAYLOAD),
    (NAME, PAYLOAD.replace(b'\\1\\2\\1', b'\\2\\2\\1')),
    (NAME, PAYLOAD.replace(b'\\1\\2\\1', b'\\invalid\\2\\1')),
    (NAME.replace('supply', 'oasis'), PAYLOAD),
    ('../' + NAME, PAYLOAD),
    (NAME.replace('2026-09-25', '2026-02-30'), PAYLOAD),
    (NAME.replace('120000', '250000'), PAYLOAD),
    (NAME.replace('2026-09-25', '2026-13-25'), PAYLOAD),
])
def test_wrong_identity_never_calls_parser(tmp_path, filename, payload):
    """Do not turn R2, malformed round headers or another map into safe-looking R1."""
    source = tmp_path / 'source'
    source.write_bytes(payload)
    def forbidden(_):
        pytest.fail('invalid identity reached parser')
    with source.open('rb') as original, pytest.raises(ValueError):
        parse_sealed_round_one(original.fileno(), filename=filename, expected_size=len(payload),
                               expected_sha256=hashlib.sha256(payload).hexdigest(), parse_regular=forbidden)


def test_callback_exception_closes_snapshot(tmp_path):
    """Parser interruption propagates without abandoning the sealed descriptor."""
    source = tmp_path / NAME
    source.write_bytes(PAYLOAD)
    def interrupted(_):
        raise KeyboardInterrupt('fixture parser interrupted')
    with source.open('rb') as original:
        before = set(os.listdir('/proc/self/fd'))
        with pytest.raises(KeyboardInterrupt, match='fixture parser interrupted'):
            parse_sealed_round_one(original.fileno(), filename=NAME, expected_size=len(PAYLOAD),
                                   expected_sha256=hashlib.sha256(PAYLOAD).hexdigest(), parse_regular=interrupted)
        assert set(os.listdir('/proc/self/fd')) == before


@pytest.mark.parametrize('result', [None, {'success': True, 'round_num': 2, 'map_name': 'supply'},
                                   {'success': True, 'round_num': True, 'map_name': 'supply'},
                                   {'success': True, 'round_num': 1, 'map_name': 'oasis'}])
def test_successful_parser_result_must_retain_identity(tmp_path, result):
    """Parser output cannot silently contradict the checked header."""
    source = tmp_path / NAME
    source.write_bytes(PAYLOAD)
    with source.open('rb') as original, pytest.raises(ValueError):
        parse_sealed_round_one(original.fileno(), filename=NAME, expected_size=len(PAYLOAD),
                               expected_sha256=hashlib.sha256(PAYLOAD).hexdigest(), parse_regular=lambda _: result)


def test_legacy_error_result_is_preserved(tmp_path):
    """Error dictionaries remain errors, not a manufactured successful result."""
    source = tmp_path / NAME
    source.write_bytes(PAYLOAD)
    failure = {'success': False, 'error': 'fixture parse failure'}
    with source.open('rb') as original:
        result = parse_sealed_round_one(
            original.fileno(), filename=NAME, expected_size=len(PAYLOAD),
            expected_sha256=hashlib.sha256(PAYLOAD).hexdigest(), parse_regular=lambda _: failure,
        )
    assert result is failure
