"""One-shot host dispatch and completed-R1 handover; no transport or activation.

The caller authenticates game lifecycle and the completion reference. These
private records bind planned identities to artifact generations, NOT to physical
starts. Run outside game callbacks. Root ancestors must remain trusted/stable;
same-user tampering and replay by an uncooperative producer are outside scope.
"""

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from shared.runtime_completed_snapshot import open_completed_snapshot
from shared.runtime_identity_allocation import inspect_round_pair
from shared.runtime_manifest_reader import _decode_manifest, _read_private_manifest_bytes
from shared.runtime_round_identity import RoundIdentity, stats_header_identity
from shared.runtime_source_reservation import _open_root, claim_source_generation, reserve_source_generation


@dataclass(frozen=True)
class CompletedStatsReference:
    generation: str
    filename: str
    size: int
    sha256: str


@dataclass(frozen=True)
class StatsDispatch:
    identity: RoundIdentity
    generation: str
    map_name: str


def _root_key(root, token):
    fd = _open_root(root, token)
    try:
        info = os.fstat(fd)
        return [info.st_dev, info.st_ino]
    finally:
        os.close(fd)


def _dispatch_record(identity, generation, map_name, spool_key, previous, capture_key):
    record = {'version': 1, 'identity': identity.encode(), 'generation': generation,
              'map_name': map_name, 'spool': spool_key,
              'previous': asdict(previous) if previous else None}
    if capture_key is not None:
        record.update(version=2, capture_root=capture_key)
    return record


def _verify_first(authority, spool, pair, map_name, spool_key, previous, capture_root=None, capture_key=None):
    if not isinstance(previous, CompletedStatsReference):
        raise ValueError('R2 requires a completed R1 reference')
    payload = _read_private_manifest_bytes(authority / pair.first.round_id, 'dispatch.json')
    if payload is None:
        raise ValueError('R1 dispatch record missing')
    # Exact comparison also rejects unknown fields, wrong identity/map/root and
    # a copied identity written into some other generation of the same spool.
    record = _decode_manifest(payload)
    expected = _dispatch_record(pair.first, previous.generation, map_name, spool_key, None, capture_key)
    if (type(record) is not dict or type(record.get('version')) is not int
            or record != expected):
        raise ValueError('R1 completion does not match original dispatch')
    with open_completed_snapshot(capture_root if capture_root is not None else spool,
                                 previous.generation, previous.filename,
                                 expected_size=previous.size, expected_sha256=previous.sha256) as snapshot:
        header = snapshot.readline(4097).decode('utf-8')
        if stats_header_identity(header) != pair.first or header.split('\\')[1] != map_name:
            raise ValueError('Completed R1 header disagrees with dispatch')
        if previous.filename[18:] != f'{map_name}-round-1.txt':
            raise ValueError('Completed R1 filename disagrees with dispatch')


def prepare_stats_dispatch(
    authority: Path, spool: Path, match_id: str, *, expected_source: str,
    map_name: str, half: int, previous: CompletedStatsReference | None = None,
    capture_root: Path | None = None,
) -> StatsDispatch:
    """Consume one half and one fresh writer generation, fsync before returning.

    R2 needs verified completed bytes from the exact first dispatch. Completion
    means writer-close + host receipt, NOT canonical import acknowledgement or
    observed engine continuity. The caller must not dispatch until this function
    returns successfully. Every failure after claiming strands that half/token;
    there is intentionally no reset, redispatch, automatic repair or deletion.
    Inspecting dispatch.json after a crash does NOT grant permission to dispatch.
    Optional capture_root opts into v2 records binding BOTH the original producer
    spool and immutable capture root from R1 onward. R2 reads completed bytes only
    from that bound capture root; copying files or switching/downgrading roots is
    refused. Omission retains the original v1 same-spool contract unchanged.
    """
    if type(half) is not int or half not in (1, 2):
        raise ValueError('Dispatch requires half 1 or 2')
    if (not isinstance(map_name, str) or re.fullmatch(r'[A-Za-z0-9_.+\-]{1,64}', map_name) is None
            or '..' in map_name):
        raise ValueError('Invalid dispatch map')
    pair = inspect_round_pair(authority, match_id, expected_source=expected_source)
    authority_key = _root_key(authority, match_id)
    spool_key = _root_key(spool, match_id)
    if authority_key == spool_key:
        raise ValueError('Authority and artifact roots must be separate')
    capture_key = None
    if capture_root is not None:
        capture_key = _root_key(capture_root, match_id)
        roots = [path.resolve(strict=True) for path in (authority, spool, capture_root)]
        if (capture_key in (authority_key, spool_key)
                or any(a.is_relative_to(b) or b.is_relative_to(a)
                       for i, a in enumerate(roots) for b in roots[i + 1:])):
            raise ValueError('Authority, producer and capture roots must be separate')
    if half == 1:
        if previous is not None:
            raise ValueError('R1 cannot have a predecessor receipt')
    else:
        _verify_first(authority, spool, pair, map_name, spool_key, previous, capture_root, capture_key)
    identity = pair.first if half == 1 else pair.second
    claim_source_generation(authority, identity.round_id)
    generation = uuid.uuid4().hex
    reserve_source_generation(spool, generation)
    claim_source_generation(spool, generation)
    payload = json.dumps(_dispatch_record(identity, generation, map_name, spool_key, previous, capture_key),
                         separators=(',', ':'), sort_keys=True).encode('ascii') + b'\n'
    directory_fd = _open_root(authority / identity.round_id, identity.round_id)
    try:
        fd = os.open('dispatch.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory_fd)
        try:
            if os.write(fd, payload) != len(payload):
                raise OSError('Incomplete stats dispatch record')
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return StatsDispatch(identity, generation, map_name)
