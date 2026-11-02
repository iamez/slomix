"""Durable bounded retry admission, not a service, import ack or remote lease."""

import fcntl
import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from shared.runtime_manifest_reader import _decode_manifest, _read_private_manifest_bytes
from shared.runtime_proximity_admission import read_proximity_admission
from shared.runtime_source_reservation import _open_root
from shared.runtime_spool import _publish_file

_LIMIT = 64
_MAX_TIME = 253402298999  # Leave room for the largest delay before year 10000.


@dataclass(frozen=True)
class ProximityRetryPermit:
    """Only reserved permits work, and only inside the context holding its lock."""

    status: Literal['reserved', 'not_due', 'busy', 'exhausted', 'missing_admission']
    attempt: int | None = None
    retry_at: int | None = None


def _delay(attempt):
    return min(30 * (2 ** min(attempt - 1, 6)), 1800)


def _time(value):
    if type(value) is not int or not 0 <= value <= _MAX_TIME:
        raise ValueError('Retry clock must be bounded integer UTC epoch seconds')


def _name(attempt):
    return f'.proximity-attempt-{attempt:03d}.json'


def _identity(admission):
    data = asdict(admission)
    data['session_date'] = admission.session_date.isoformat()
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode('ascii')).hexdigest()


def _history(directory, identity):
    """Read at most 64 small records; reject gaps instead of resetting the count."""
    latest = None
    missing = False
    for number in range(1, _LIMIT + 1):
        raw = _read_private_manifest_bytes(directory, _name(number))
        if raw is None:
            missing = True
            continue
        if missing:
            raise ValueError('Retry history has a gap')
        entry = _decode_manifest(raw)
        if (type(entry) is not dict or set(entry) != {
            'version', 'attempt', 'identity_sha256', 'started_at', 'retry_at',
        } or type(entry['version']) is not int or entry['version'] != 1
                or type(entry['attempt']) is not int or entry['attempt'] != number
                or entry['identity_sha256'] != identity):
            raise ValueError('Invalid retry history identity or schema')
        _time(entry['started_at'])
        if (type(entry['retry_at']) is not int
                or entry['retry_at'] != entry['started_at'] + _delay(number)
                or (latest is not None and entry['started_at'] < latest['retry_at'])):
            raise ValueError('Invalid retry history deadline')
        latest = entry
    return latest


@contextmanager
def reserve_proximity_retry(directory: Path, *, source_id: str, generation: str, now: int):
    """Durably charge one attempt BEFORE work and retain backoff across restart.

    Caller supplies UTC epoch seconds and the stable private admission directory.
    A nonblocking Linux flock on that directory serializes cooperating workers;
    keep ALL attempt work inside this context. No background process is started.
    This is NOT a lease against legacy/remote/uncooperative writers. Do not use
    on a network filesystem; same-UID directory replacement is outside contract.

    Immutable attempt records use existing file/link/directory fsync publication.
    First delay is 30 seconds, doubles to 1800, maximum 64 attempts. Restart,
    exceptions, cancellation and crashes do not reset spent attempts. A crash
    after charging but before work deliberately spends an attempt. Post-link
    fsync errors propagate; a visible record conservatively consumes capacity,
    never proves work ran or committed. Exhaustion requires operator review;
    this API has no reset/delete. Backward clock steps delay work, not hot-loop.

    Outcomes/import success are NOT persisted or acknowledged here: the caller
    still classifies conflicts and verifies committed receipts before retiring
    work. No automatic loop/discovery, capture, DB access, deletion or service
    action. At most 64 * 4096 history bytes read; filesystem waits are unbounded.
    Missing admission/busy/exhausted/not_due do not permit work or publish files.
    """
    _time(now)
    # This shared opener validates private ownership/mode and token grammar.
    fd = _open_root(directory, generation)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield ProximityRetryPermit('busy')
            return
        admission = read_proximity_admission(directory, source_id=source_id, generation=generation)
        if admission is None:
            yield ProximityRetryPermit('missing_admission')
            return
        identity = _identity(admission)
        latest = _history(directory, identity)
        spent = latest['attempt'] if latest is not None else 0
        retry_at = latest['retry_at'] if latest is not None else None
        if spent == _LIMIT:
            yield ProximityRetryPermit('exhausted', spent, retry_at)
            return
        if retry_at is not None and now < retry_at:
            yield ProximityRetryPermit('not_due', spent, retry_at)
            return
        number = spent + 1
        entry = dict(version=1, attempt=number, identity_sha256=identity,
                     started_at=now, retry_at=now + _delay(number))
        payload = (json.dumps(entry, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')
        _publish_file(directory, _name(number), [payload], len(payload), hashlib.sha256(payload).hexdigest())
        yield ProximityRetryPermit('reserved', number, entry['retry_at'])
    finally:
        # Closing also releases flock on every return/exception/cancellation path.
        os.close(fd)
