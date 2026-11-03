"""Additional handoff checks assume the separately tested stats verifier."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from shared.runtime_captured_timing_match import CapturedTimingMatch
from shared.runtime_stats_dispatch import _root_key
from shared.runtime_timing_capture import CapturedTiming
from tests.unit.test_runtime_stats_dispatch import setup_pair


@pytest.mark.parametrize('fault', ['none', 'halves', 'generation', 'root'])
def test_handoff_rejects_identity_generation_and_root_drift(tmp_path, fault):
    _, _, pair = setup_pair(tmp_path / 'rounds')
    root = tmp_path / 'timings'
    root.mkdir(mode=0o700)
    first = CapturedTiming(root, 'a' * 32, 'first.json', 42, 'c' * 64, pair.first, 'supply')
    second = CapturedTiming(root, 'b' * 32, 'second.json', 42, 'd' * 64, pair.second, 'supply')
    stats = SimpleNamespace(verify=Mock(), first_identity=pair.first, second_identity=pair.second,
        first=SimpleNamespace(reference=SimpleNamespace(generation=first.generation)),
        second=SimpleNamespace(reference=SimpleNamespace(generation=second.generation)))
    key = tuple(_root_key(root, pair.first.match_id))
    if fault == 'halves':
        first, second = second, first
    elif fault == 'generation':
        second = replace(second, generation='f' * 32)
    elif fault == 'root':
        key = (0, 0)
    captured = CapturedTimingMatch(stats, (first, second), key)
    if fault == 'none':
        captured.verify()
    else:
        with pytest.raises(ValueError):
            captured.verify()
    stats.verify.assert_called_once()
