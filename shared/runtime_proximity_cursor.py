"""Source-bound scheduling checkpoint; never an import receipt or service."""

import fcntl
import json
import os
from pathlib import Path
from uuid import uuid4

from shared.runtime_manifest_reader import _decode_manifest, _read_private_manifest_bytes
from shared.runtime_proximity_admission import _scope
from shared.runtime_proximity_batch import _TOKEN, ProximityBatchResult, process_proximity_batch
from shared.runtime_proximity_retry import _time
from shared.runtime_source_reservation import _open_root

_ENTRY = '.proximity-cursor.json'


def _read_cursor(root, source_id):
    payload = _read_private_manifest_bytes(root, _ENTRY)
    if payload is None:
        return None
    data = _decode_manifest(payload)
    if (type(data) is not dict or set(data) != {'version', 'source_id', 'after'}
            or type(data['version']) is not int or data['version'] != 1
            or data['source_id'] != source_id
            or (data['after'] is not None and (
                not isinstance(data['after'], str) or _TOKEN.fullmatch(data['after']) is None))):
        raise ValueError('Invalid proximity cursor schema or configured source')
    return data


def _save_cursor(fd, source_id, after):
    """Atomic replacement of OUR mutable hint only; retain temp on any failure."""
    payload = (json.dumps(dict(version=1, source_id=source_id, after=after),
                          sort_keys=True) + '\n').encode('ascii')
    temporary = '.proximity-cursor-next-' + uuid4().hex
    child = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600, dir_fd=fd)
    try:
        if os.write(child, payload) != len(payload):
            raise OSError('Incomplete proximity cursor write')
        os.fsync(child)
    finally:
        os.close(child)
    os.replace(temporary, _ENTRY, src_dir_fd=fd, dst_dir_fd=fd)
    os.fsync(fd)


async def process_proximity_checkpointed_batch(
    root: Path, *, source_id: str, now: int, adapter, observer, gametimes_dir: Path,
    batch_size: int = 16, max_entries: int = 4096,
    allow_declared_mapping: bool = False,
) -> ProximityBatchResult:
    """Resume one serial batch under a nonblocking Linux root flock.

    Stable owned0700 LOCAL root belongs to one configured source. Hold this root
    lock across read, work and checkpoint; contenders raise BlockingIOError,
    including another coroutine opening its own descriptor. Generation locks
    still protect queue turns. Legacy/uncooperative writers are NOT fenced.
    A missing checkpoint initializes/binds the source before any batch work.
    Malformed, foreign-source or unsafe files fail closed, never reset to zero.

    Advance only after the entire batch returns (including reported local error
    states); preserve the cursor on empty inventory. Cancellation/global failure
    retains the old hint: earlier commits can replay safely through queue rules.
    Replace only this mutable scheduling hint with file-then-directory fsync.
    Fsync failure propagates even if a new hint is visible. Crash/power-loss
    durability is not inferred from a successful read; no source deletion ever.
    Failed temporary files remain for operator inspection and count toward the
    root entry cap, as does this checkpoint. No unbounded journal or cleanup.

    Caller owns operation timeouts, outage backoff, stable root lifecycle and
    dedicated connections. Fairness assumes a finite stable inventory and normal
    completed batches, not endless crashes/failures or adversarial arrivals.
    No service, loop, deployment, connection creation or source acknowledgment.
    """
    if type(allow_declared_mapping) is not bool:
        raise ValueError('Explicit declared mapping policy required')
    mapping_options = {'allow_declared_mapping': True} if allow_declared_mapping else {}
    _scope(root / ('0' * 32), source_id, '0' * 32)
    _time(now)
    if type(batch_size) is not int or not 1 <= batch_size <= 32:
        raise ValueError('Discovery batch size must be 1..32')
    if type(max_entries) is not int or not 1 <= max_entries <= 4096:
        raise ValueError('Discovery entry cap must be 1..4096')
    fd = _open_root(root, '0' * 32)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = _read_cursor(root, source_id)
        if state is None:
            _save_cursor(fd, source_id, None)
        after = state['after'] if state is not None else None
        result = await process_proximity_batch(
            root, source_id=source_id, now=now, adapter=adapter, observer=observer,
            gametimes_dir=gametimes_dir, after=after, batch_size=batch_size,
            max_entries=max_entries, **mapping_options,
        )
        next_cursor = result.discovery.next_cursor
        if next_cursor is not None and next_cursor != after:
            _save_cursor(fd, source_id, next_cursor)
        return result
    finally:
        os.close(fd)
