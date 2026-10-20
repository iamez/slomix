"""In-memory handoff from successful host capture; never a recovery credential."""

from dataclasses import dataclass

from shared.runtime_host_capture import CapturedStats
from shared.runtime_round_identity import RoundIdentity, require_round_pair
from shared.runtime_stats_dispatch import _root_key


@dataclass(frozen=True)
class CapturedMatch:
    """Caller retains the controller's result, not identities read from payloads.

    This plain record is not authentication by itself and must not be rebuilt
    from discovered files after an ambiguous capture/crash. The controller emits
    it only after both successful operations, including socket cleanup. Export
    does not acknowledge, import, delete, or change capture state. Stable private
    roots and trusted same-UID ownership remain required through import.
    """

    first: CapturedStats
    second: CapturedStats
    first_identity: RoundIdentity
    second_identity: RoundIdentity
    capture_key: tuple[int, int]

    def verify(self):
        require_round_pair(self.first_identity, self.second_identity)
        if not isinstance(self.first, CapturedStats) or not isinstance(self.second, CapturedStats):
            raise ValueError('Explicit captured halves required')
        if self.first.root != self.second.root:
            raise ValueError('Captured halves must share the bound capture root')
        if self.first.reference.generation == self.second.reference.generation:
            raise ValueError('Captured halves require separate generations')
        if tuple(_root_key(self.first.root, self.first_identity.match_id)) != self.capture_key:
            raise ValueError('Captured match root identity changed')
