"""Handoff binding preserves caller policy; no SQL or process activation."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot import runtime_captured_timing_import as adapter
from shared.runtime_captured_match import CapturedMatch
from shared.runtime_captured_timing_match import CapturedTimingMatch
from shared.runtime_host_capture import CapturedStats
from shared.runtime_stats_dispatch import CompletedStatsReference
from shared.runtime_timing_capture import CapturedTiming
from tests.unit.test_runtime_stats_dispatch import setup_pair


def captured(tmp_path):
    _, _, pair = setup_pair(tmp_path / 'rounds')
    stats_root, timing_root = tmp_path / 'stats', tmp_path / 'timings'
    stats_root.mkdir(mode=0o700)
    timing_root.mkdir(mode=0o700)
    def key(p):
        return p.stat().st_dev, p.stat().st_ino
    first = CapturedStats(stats_root, CompletedStatsReference('a' * 32, 'r1.txt', 42, 'c' * 64))
    second = CapturedStats(stats_root, CompletedStatsReference('b' * 32, 'r2.txt', 42, 'd' * 64))
    stats = CapturedMatch(first, second, pair.first, pair.second, key(stats_root))
    timings = tuple(CapturedTiming(timing_root, item.reference.generation,
                                  f'half-{half}.json', 42, 'e' * 64, identity, 'supply')
                    for half, item, identity in ((1, first, pair.first), (2, second, pair.second)))
    return CapturedTimingMatch(stats, timings, key(timing_root))


@pytest.mark.parametrize('execute', [False, None, 1])
async def test_no_explicit_authorization_never_calls_executor(execute, monkeypatch):
    operation = AsyncMock()
    monkeypatch.setattr(adapter, 'execute', operation)
    with pytest.raises(ValueError, match='authorization'):
        await adapter.import_captured_timing_match(SimpleNamespace(execute=execute), None, {})
    operation.assert_not_awaited()


def test_binding_preserves_options_and_uses_verified_references(tmp_path, monkeypatch):
    handoff = captured(tmp_path)
    options = SimpleNamespace(execute=True, env_file='explicit-config', timing_writer_handover_confirmed=False)
    seen = []
    monkeypatch.setattr(adapter, 'validate_arguments', lambda args: seen.append(args))
    bound = adapter.bind_captured_timing_arguments(options, handoff)
    assert bound is not options
    assert not hasattr(options, 'r1')
    assert bound.timing_writer_handover_confirmed is False
    assert bound.env_file == options.env_file
    assert bound.r1[0] == handoff.stats.first.reference.generation
    assert bound.timing_r2[0] == handoff.timings[1].generation
    assert bound.timing_generation_directories is True
    assert seen == [bound]
