"""Caller-driven receipt-to-canonical-import composition; no scheduler or activation."""

import copy
import os
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from bot.runtime_round_mapping import StatsRoundBinding
from bot.runtime_snapshot_pair import RoundSnapshotInput, parse_sealed_round_pair
from shared.runtime_completed_snapshot import open_completed_snapshot
from shared.runtime_round_identity import RoundIdentity, stats_header_identity
from shared.runtime_snapshot_parser import parse_sealed_round_one


@dataclass(frozen=True)
class CompletedRoundInput:
    """Caller-authenticated expectation, not a trust assertion made by this record."""

    root: Path
    generation: str
    filename: str
    size: int
    sha256: str


class MissingRoundOne(ValueError):
    """Caller retains R2 for a later attempt; no database marker was written."""


@dataclass(frozen=True)
class _ImportSource:
    """Borrowed stream lifetime is bounded by the enclosing asynchronous import."""

    view: object
    size: int
    parsed: dict

    def read_bytes(self):
        """Read the immutable bytes from offset zero without changing stream position."""
        data = os.pread(self.view.fileno(), self.size, 0)
        if len(data) != self.size:
            raise OSError('Sealed import input length mismatch')
        return data

    def parse(self, _parser):
        """Canonical importer may annotate results without altering the prepared record."""
        return copy.deepcopy(self.parsed)


async def import_completed_round(manager, current: CompletedRoundInput, *,
                                 first: CompletedRoundInput | None = None,
                                 require_declared_identity: bool = False,
                                 expected_identity: RoundIdentity | None = None):
    """Keep receipt-verified snapshots open through the complete process_file await.

    Authenticate every expectation and choose the correct pair outside this API.
    Missing R1 raises a distinct exception before I/O/DB. All receipt/hash/header/
    pair validation and parsing occur before manager DB preflight, even if already
    processed. Return the canonical result unchanged; exceptions/cancellation
    propagate after closing owned descriptors. No source removal or ack/retry loop.
    Parsing currently recopies sealed input (up to32MiB snapshot storage for R2,
    plus parser allocations). This is not a live independent runtime entrypoint.
    require_declared_identity alone is contradiction checking. Supplying an
    independently trusted expected_identity additionally requests atomic canonical
    mapping (migration099, enabled journal, forward-only exclusive writer).
    Neither mode authenticates or allocates producer identities here.
    """
    if type(require_declared_identity) is not bool:
        raise ValueError('Explicit boolean identity policy required')
    if expected_identity is not None:
        if not isinstance(expected_identity, RoundIdentity):
            raise ValueError('Explicit expected identity required for canonical mapping')
        require_declared_identity = True
    if current.filename.endswith('-round-2.txt') and first is None:
        raise MissingRoundOne('Explicit completed R1 is required; retain R2 for retry')
    if first is not None and not current.filename.endswith('-round-2.txt'):
        raise ValueError('R1 dependency is only valid for a round-two import')
    with ExitStack() as stack:
        def open_input(item):
            return stack.enter_context(open_completed_snapshot(
                item.root, item.generation, item.filename,
                expected_size=item.size, expected_sha256=item.sha256,
            ))
        view = open_input(current)
        first_view = None if first is None else open_input(first)
        if first is None:
            parsed = parse_sealed_round_one(
                view.fileno(), filename=current.filename, expected_size=current.size,
                expected_sha256=current.sha256, parse_regular=manager.parser.parse_regular_stats_file,
                require_declared_identity=require_declared_identity,
            )
        else:
            parsed = parse_sealed_round_pair(
                RoundSnapshotInput(first.filename, first_view.fileno(), first.size, first.sha256),
                RoundSnapshotInput(current.filename, view.fileno(), current.size, current.sha256),
                require_declared_identity=require_declared_identity,
            )
        source = _ImportSource(view, current.size, parsed)
        if expected_identity is not None:
            def bind(item, stream, expected, dependency=None):
                header = os.pread(stream.fileno(), min(item.size, 4096), 0).splitlines(keepends=True)[0].decode('utf-8')
                if stats_header_identity(header) != expected:
                    raise ValueError('Sealed stats identity disagrees with expected identity')
                return StatsRoundBinding(expected, item.generation, item.filename, item.size,
                                         item.sha256, parsed['map_name'], dependency)
            dependency = None
            if first is not None:
                expected_first = RoundIdentity(expected_identity.source_id, expected_identity.match_id,
                    expected_identity.first_round_id, 1, expected_identity.first_round_id)
                dependency = bind(first, first_view, expected_first)
            binding = bind(current, view, expected_identity, dependency)
            return await manager.process_file(Path(current.filename), input_source=source, runtime_binding=binding)
        return await manager.process_file(Path(current.filename), input_source=source)
