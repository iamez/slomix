"""In-memory successful controller handoff, not a recovery credential."""
from dataclasses import dataclass

from shared.runtime_captured_match import CapturedMatch
from shared.runtime_stats_dispatch import _root_key
from shared.runtime_timing_capture import CapturedTiming


@dataclass(frozen=True)
class CapturedTimingMatch:
    stats: CapturedMatch
    timings: tuple[CapturedTiming, CapturedTiming]
    timing_root_key: tuple[int, int]

    def verify(self):
        self.stats.verify()
        if len(self.timings) != 2 or not all(isinstance(t, CapturedTiming) for t in self.timings):
            raise ValueError('Both successful timing captures required')
        first, second = self.timings
        if first.map_name != second.map_name:
            raise ValueError('Timing halves disagree on map')
        if first.root != second.root:
            raise ValueError('Timing halves must share bound capture root')
        if tuple(_root_key(first.root, self.stats.first_identity.match_id)) != self.timing_root_key:
            raise ValueError('Timing root identity changed')
        for timing, stats, identity in zip(self.timings,
                (self.stats.first, self.stats.second),
                (self.stats.first_identity, self.stats.second_identity), strict=True):
            if timing.identity != identity or timing.generation != stats.reference.generation:
                raise ValueError('Timing handoff disagrees with captured stats identity/generation')
