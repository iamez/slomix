"""Timing and stats close notices must never be interchangeable."""
import pytest

from shared.runtime_host_completion import decode_stats_completion
from shared.runtime_timing_completion import TimingCompletion, decode_timing_completion


def test_timing_round_trip_and_stats_protocol_separation():
    notice = TimingCompletion('a' * 32, 'round-1.json', 128)
    assert decode_timing_completion(notice.encode()) == notice
    with pytest.raises(ValueError):
        decode_stats_completion(notice.encode())
    with pytest.raises(ValueError):
        decode_timing_completion(notice.encode().replace('slomix_timing_closed_v1', 'slomix_stats_closed_v1'))


@pytest.mark.parametrize('name', ['../x.json', '/x.json', 'x/round.json', 'x.txt',
                                 'x|y.json', 'x\n.json', 'x..json', 'x.json\x00'])
def test_unsafe_names_rejected(name):
    with pytest.raises(ValueError):
        TimingCompletion('a' * 32, name, 128).encode()


@pytest.mark.parametrize('size', [True, 0, -1, 8388609, 1.5, '128'])
def test_invalid_sizes_rejected(size):
    with pytest.raises(ValueError):
        TimingCompletion('a' * 32, 'round.json', size).encode()


@pytest.mark.parametrize('size', ['01', '+1', '1\n', '1.0'])
def test_noncanonical_wire_size_rejected(size):
    with pytest.raises(ValueError):
        decode_timing_completion(f'slomix_timing_closed_v1|{"a" * 32}|round.json|{size}')
