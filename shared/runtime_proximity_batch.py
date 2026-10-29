"""Bounded local discovery and one serial round-robin batch; no service loop."""

import bisect
import os
import re
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

from shared.runtime_proximity_admission import _scope, read_proximity_admission
from shared.runtime_proximity_queue import ProximityQueueResult, process_proximity_once
from shared.runtime_proximity_retry import _time
from shared.runtime_source_reservation import _open_root

_TOKEN = re.compile(r'[0-9a-f]{32}', re.ASCII)


@dataclass(frozen=True)
class ProximityDiscovery:
    generations: tuple[str, ...]
    next_cursor: str | None
    entries_seen: int
    ignored_entries: int
    total_generations: int


@dataclass(frozen=True)
class ProximityBatchItem:
    generation: str
    result: ProximityQueueResult


@dataclass(frozen=True)
class ProximityBatchResult:
    discovery: ProximityDiscovery
    items: tuple[ProximityBatchItem, ...]


def discover_proximity_batch(
    root: Path, *, after: str | None = None, batch_size: int = 16, max_entries: int = 4096,
) -> ProximityDiscovery:
    """Select generation NAMES, not trusted/complete/eligible admissions.

    Scan a private stable local root, counting ALL entries against the hard cap
    (including ignored names). Overflow raises before returning any selection;
    never truncate an unsorted directory scan and silently starve later entries.
    Sort generation tokens, rotate after the exclusive caller cursor, then take
    at most32. No symlinks followed during discovery; per-entry admission remains
    a separate validation step. Matching file/symlink names are included so the
    batch can report them rather than hiding malformed generations as absent.

    Fair for a fixed finite set when caller carries next_cursor across batches.
    Cursor is a scheduling hint, not completion or durable state: caller scopes
    and persists it per source/root for restart fairness. No root changes,
    recursion, stat of unrelated entries, DB access, or filesystem time bound.
    """
    if after is not None and (not isinstance(after, str) or _TOKEN.fullmatch(after) is None):
        raise ValueError('Discovery cursor must be a generation token or None')
    if type(batch_size) is not int or not 1 <= batch_size <= 32:
        raise ValueError('Discovery batch size must be 1..32')
    if type(max_entries) is not int or not 1 <= max_entries <= 4096:
        raise ValueError('Discovery entry cap must be 1..4096')
    fd = _open_root(root, '0' * 32)
    names = []
    seen = 0
    try:
        with os.scandir(fd) as entries:
            for entry in entries:
                seen += 1
                if seen > max_entries:
                    raise ValueError('Discovery root exceeds entry cap; no batch selected')
                if _TOKEN.fullmatch(entry.name):
                    names.append(entry.name)
    finally:
        os.close(fd)
    names.sort()
    index = bisect.bisect_right(names, after) if after is not None else 0
    selected = tuple((names[index:] + names[:index])[:batch_size])
    return ProximityDiscovery(selected, selected[-1] if selected else None,
                              seen, seen - len(names), len(names))


async def process_proximity_batch(
    root: Path, *, source_id: str, now: int, adapter, observer, gametimes_dir: Path,
    after: str | None = None, batch_size: int = 16, max_entries: int = 4096,
    allow_declared_mapping: bool = False,
) -> ProximityBatchResult:
    """Process selected generations serially, reusing caller-owned resources.

    Bad local admission/state gets a bounded operator-facing reason and does not
    starve other selected entries. Admission I/O errors are reported separately
    from invalid content. Once queue work starts, I/O/DB errors and cancellation
    propagate: never hide a global outage by reporting an empty/successful batch.
    Prior successful items may already be committed; retry uses durable queue
    history and current receipts. Partial failure returns no new cursor.
    No background workers/connections/services, parallel queries, automatic
    retries, source deletion, or implicit terminal state. Caller owns operation
    timeouts, polling/backoff, cursor persistence and private root lifecycle.
    now is the batch-start UTC epoch. Add monotonic elapsed seconds per item so
    a slow earlier item does not give later attempts an already-expired deadline.
    """
    if type(allow_declared_mapping) is not bool:
        raise ValueError('Explicit declared mapping policy required')
    mapping_options = {'allow_declared_mapping': True} if allow_declared_mapping else {}
    _time(now)
    started = monotonic()
    _scope(root / ('0' * 32), source_id, '0' * 32)
    discovery = discover_proximity_batch(root, after=after, batch_size=batch_size, max_entries=max_entries)
    results = []
    for generation in discovery.generations:
        directory = root / generation
        try:
            admission = read_proximity_admission(directory, source_id=source_id, generation=generation)
        except ValueError:
            result = ProximityQueueResult('reconcile', 'invalid_admission')
        except OSError:
            result = ProximityQueueResult('deferred', 'admission_unavailable')
        else:
            if admission is None:
                result = ProximityQueueResult('deferred', 'missing_admission')
            else:
                try:
                    result = await process_proximity_once(
                        directory, source_id=source_id, generation=generation,
                        now=now + int(monotonic() - started),
                        adapter=adapter, observer=observer, gametimes_dir=gametimes_dir,
                        **mapping_options,
                    )
                except ValueError:
                    result = ProximityQueueResult('reconcile', 'invalid_queue_state')
        results.append(ProximityBatchItem(generation, result))
    return ProximityBatchResult(discovery, tuple(results))
