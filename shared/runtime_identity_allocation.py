"""Durable host-side ID reservation, independent of game-frame processing.

The trusted dispatcher associates these preallocated IDs with physical rounds.
Allocation alone is NOT evidence that a half started/ended, source authentication,
IPC delivery, or permission to link canonical database rows. Keep this private
authority root separate from the artifact spool and stable throughout each call.
"""

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from shared.runtime_manifest_reader import _decode_manifest, _read_private_manifest_bytes
from shared.runtime_round_identity import RoundIdentity, decode_round_identity, require_round_pair
from shared.runtime_source_reservation import _open_root, reserve_source_generation


@dataclass(frozen=True)
class AllocatedRoundPair:
    first: RoundIdentity
    second: RoundIdentity

    def __post_init__(self):
        require_round_pair(self.first, self.second)
        if len({self.first.match_id, self.first.round_id, self.second.round_id}) != 3:
            raise ValueError('Match and physical half IDs must be distinct')


def allocate_round_pair(root: Path, source_id: str) -> AllocatedRoundPair:
    """Reserve three never-reused IDs and fsync their pair record before return.

    Atomic mkdir supplies collision exclusion, not UUID probability alone. No
    retry on collision or I/O failure; every created directory/partial record is
    retained. Dispatcher must NOT send a ticket after an unsuccessful call.
    This allocates both planned halves, not a completed-R1 receipt or R2 handover.
    Operations may block on local disk; never invoke inside an ET frame callback.
    """
    match, first, second = (uuid.uuid4().hex for _ in range(3))
    pair = AllocatedRoundPair(RoundIdentity(source_id, match, first, 1, first),
                              RoundIdentity(source_id, match, second, 2, first))
    for token in (match, first, second):
        reserve_source_generation(root, token)
    record = json.dumps({'version': 1, 'first': pair.first.encode(), 'second': pair.second.encode()},
                        sort_keys=True, separators=(',', ':')).encode('ascii') + b'\n'
    directory_fd = _open_root(root / match, match)
    try:
        fd = os.open('round-pair.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory_fd)
        try:
            if os.write(fd, record) != len(record):
                raise OSError('Incomplete round identity record')
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return pair


def inspect_round_pair(root: Path, match_id: str, *, expected_source: str) -> AllocatedRoundPair:
    """Read a bounded record, checking namespace/source and all reservations.

    Read-only inspection, not recovered fsync durability, dispatch permission or
    evidence of game lifecycle. A partial/unsafe record fails without repair.
    The same trusted user could rewrite records; filesystem ownership is not a
    signature. Root ancestors must remain trusted and stable, as for the spool.
    """
    fd = _open_root(root, match_id)
    os.close(fd)
    payload = _read_private_manifest_bytes(root / match_id, 'round-pair.json')
    if payload is None:
        raise ValueError('Round identity record missing')
    data = _decode_manifest(payload)
    if (type(data) is not dict or set(data) != {'version', 'first', 'second'}
            or type(data['version']) is not int or data['version'] != 1):
        raise ValueError('Invalid round identity record')
    pair = AllocatedRoundPair(decode_round_identity(data['first']), decode_round_identity(data['second']))
    if pair.first.match_id != match_id or pair.first.source_id != expected_source:
        raise ValueError('Round identity namespace mismatch')
    for token in (pair.first.round_id, pair.second.round_id):
        fd = _open_root(root / token, token)
        os.close(fd)
    return pair
