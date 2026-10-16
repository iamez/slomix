"""Offline opt-in pair adapter; preserve the canonical differential assembly."""

import re
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime

from bot.community_stats_parser import C0RNP0RN3StatsParser
from shared.runtime_round_identity import require_round_pair, stats_header_identity
from shared.runtime_sealed_snapshot import sealed_stats_snapshot


@dataclass(frozen=True)
class RoundSnapshotInput:
    """Trusted logical identity and content expectation; descriptor remains caller-owned."""

    filename: str
    source_fd: int
    size: int
    sha256: str


def _identity(item, round_number):
    """Reject unsafe names and impossible timestamps before opening snapshots."""
    name = item.filename
    if (not isinstance(name, str) or len(name) > 240 or '..' in name
            or re.fullmatch(r'\d{4}-\d{2}-\d{2}-\d{6}-[A-Za-z0-9_.+-]+-round-'
                            + str(round_number) + r'\.txt', name, re.ASCII) is None):
        raise ValueError('Invalid sealed pair filename')
    stamp = datetime.strptime(name[:17] + '+0000', '%Y-%m-%d-%H%M%S%z')
    return name[18:-len('-round-1.txt')], stamp


def validate_pair_metadata(first, second):
    """Pure shared filename/calendar/pair guard; not a provenance assertion."""
    map_one, time_one = _identity(first, 1)
    map_two, time_two = _identity(second, 2)
    if map_one != map_two or not 0 <= (time_two - time_one).total_seconds() <= 45 * 60:
        raise ValueError('Sealed pair map or timestamp mismatch')
    return map_one


class _SealedPairParser(C0RNP0RN3StatsParser):
    """Only substitute source resolution, not differential or match-summary logic."""

    def __init__(self, paths, first, second):
        super().__init__()
        self._paths = paths
        self._first = first
        self._second = second

    def find_corresponding_round_1_file(self, round_2_file_path):
        """Select only the caller's validated R1; never search the filesystem."""
        if round_2_file_path != self._second:
            raise ValueError('Unexpected round-two identity')
        return self._first

    def parse_regular_stats_file(self, file_path):
        """Open only an already sealed descriptor while retaining logical names upstream."""
        return super().parse_regular_stats_file(self._paths[file_path])


def parse_sealed_round_pair(first: RoundSnapshotInput, second: RoundSnapshotInput, *,
                            require_declared_identity: bool = False) -> dict:
    """Parse both sealed inputs using the unchanged canonical R2 assembly.

    Caller authenticates receipts and chooses the correct pair; same-map and
    0..45-minute filename checks reject contradictions, not prove provenance.
    Both copies must be verified/sealed before any parsing. At most16MiB of
    anonymous snapshot storage; legacy parser allocations are additional.
    No missing-R1 fallback, discovery, DB writes, source cleanup or activation.
    This bot adapter still inherits the legacy parser's import dependencies.
    Optional declared-identity policy requires matching v1 source/match/R1 IDs;
    this rejects contradictions, but does not authenticate a producer or authorize DB links.
    """
    if type(require_declared_identity) is not bool:
        raise ValueError('Explicit boolean identity policy required')
    map_one = validate_pair_metadata(first, second)
    with ExitStack() as stack:
        paths = {}
        identities = []
        for number, item in enumerate((first, second), start=1):
            view = stack.enter_context(sealed_stats_snapshot(
                item.source_fd, expected_size=item.size, expected_sha256=item.sha256,
            ))
            raw_header = view.readline()
            if require_declared_identity:
                declared = stats_header_identity(raw_header.decode('utf-8'))
                if declared is None:
                    raise ValueError('Declared round identity required')
                identities.append(declared)
            fields = raw_header.decode('utf-8', errors='ignore').strip().split('\\')
            if len(fields) < 8 or fields[1] != map_one or fields[3] != str(number):
                raise ValueError('Sealed pair header identity mismatch')
            view.seek(0)
            paths[item.filename] = f'/proc/self/fd/{view.fileno()}'
        if require_declared_identity:
            require_round_pair(*identities)
        parser = _SealedPairParser(paths, first.filename, second.filename)
        return parser.parse_round_2_with_differential(second.filename)
