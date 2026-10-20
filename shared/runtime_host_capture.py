"""Host-side writer-close to sealed bytes to durable private stats publication."""

import hashlib
import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from shared.runtime_completion_manifest import publish_completion_manifest
from shared.runtime_host_bootstrap import BootstrapAcceptance
from shared.runtime_host_completion import StatsCompletion, verify_stats_completion
from shared.runtime_process_authority import ProcessEpoch
from shared.runtime_process_pin import ProcessPin
from shared.runtime_round_identity import stats_header_identity
from shared.runtime_sealed_snapshot import sealed_stats_snapshot
from shared.runtime_source_reservation import reserve_source_generation
from shared.runtime_spool import publish_stats_file
from shared.runtime_stats_dispatch import CompletedStatsReference

_METADATA = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')


@dataclass(frozen=True)
class CapturedStats:
    """Reference belongs to this capture root, NOT the mutable producer spool."""

    root: Path
    reference: CompletedStatsReference

    @property
    def directory(self) -> Path:
        return self.root / self.reference.generation


def _separate_roots(authority, source, capture):
    roots = (authority, source, capture)
    if any(not isinstance(path, Path) or not path.is_absolute() for path in roots):
        raise ValueError('Capture requires absolute independently approved roots')
    resolved = [path.resolve(strict=True) for path in roots]
    for i, left in enumerate(resolved):
        for right in resolved[i + 1:]:
            if left.is_relative_to(right) or right.is_relative_to(left):
                raise ValueError('Authority, producer and capture roots must be separate')


def _require_source(info, uid, size):
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid
            or info.st_mode & 0o022 or info.st_nlink != 1 or info.st_size != size):
        raise ValueError('Source must be a sole-link regular file owned by the approved producer, '
                         'not group/world writable, with exactly the closed size')


def capture_closed_stats(authority: Path, pin: ProcessPin, expected: ProcessEpoch, *,
                         accepted: BootstrapAcceptance, completed: StatsCompletion,
                         source_directory: Path, capture_root: Path) -> CapturedStats:
    """Capture a successful authenticated receipt outside game callbacks.

    Caller passes the successful receive_stats_completion return in the SAME
    controller attempt, never a record recovered after a failed/ambiguous call.
    Disk equality cannot establish that an earlier fsync succeeded. The producer
    must still be pinned/live; its independently provisioned output directory and
    all root ancestors must stay stable. These checks do not discover the engine
    output path, defend against hostile same-UID/root writers, or replace source
    isolation. No network filesystem or wall-clock deadline is supported here.

    Read at most 8 MiB twice from the sole open source fd (hash then sealed copy),
    check metadata and exact dispatched identity/map/half in a bounded header,
    then publish the sealed bytes and their manifest with existing fsync/no-clobber
    helpers. No stats formula/parsing/import is done. A fresh generation is
    consumed BEFORE opening source bytes; all post-reservation failures retain
    it for explicit reconciliation, never automatic retry, overwrite or cleanup.
    A failure after publication can leave payload/manifest, without success.

    Capture storage is separate from producer and authority storage. R2 dispatch
    still requires its own existing root-bound handover; returning this reference
    does not authorize substituting capture_root for a different dispatch spool.
    No source ACK/deletion, process/service activation, DB write or scheduler.
    """
    verify_stats_completion(authority, pin, expected, accepted=accepted, completed=completed)
    _separate_roots(authority, source_directory, capture_root)
    # Calendar admission only, not an inference about the engine's time zone.
    datetime.strptime(completed.filename[:17] + '+0000', '%Y-%m-%d-%H%M%S%z')
    source_root_fd = os.open(source_directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        root_info = os.fstat(source_root_fd)
        if root_info.st_uid != pin.identity.uid or root_info.st_mode & 0o022:
            raise ValueError('Source directory must be owned by the approved producer and not shared writable')
        directory = reserve_source_generation(capture_root, completed.generation)
        source_fd = os.open(completed.filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                            dir_fd=source_root_fd)
        try:
            before = os.fstat(source_fd)
            _require_source(before, pin.identity.uid, completed.size)
            digest = hashlib.sha256()
            offset = 0
            while offset < completed.size:
                chunk = os.pread(source_fd, min(65536, completed.size - offset), offset)
                if not chunk:
                    raise ValueError('Closed source ended before declared size')
                digest.update(chunk)
                offset += len(chunk)
            sha256 = digest.hexdigest()
            with sealed_stats_snapshot(source_fd, expected_size=completed.size, expected_sha256=sha256) as snapshot:
                after = os.fstat(source_fd)
                if any(getattr(before, field) != getattr(after, field) for field in _METADATA):
                    raise ValueError('Closed source changed during capture')
                # Verify the name still identifies this fd; never reopen its bytes.
                named = os.stat(completed.filename, dir_fd=source_root_fd, follow_symlinks=False)
                if any(getattr(before, field) != getattr(named, field) for field in _METADATA):
                    raise ValueError('Closed source name changed during capture')
                _require_source(named, pin.identity.uid, completed.size)
                header = snapshot.readline(4097)
                if len(header) > 4096 or not header.endswith(b'\n'):
                    raise ValueError('Closed stats requires a bounded complete header')
                text = header.decode('utf-8', errors='strict')
                dispatch = accepted.delivery.dispatch
                if (stats_header_identity(text) != dispatch.identity
                        or text.split('\\')[1] != dispatch.map_name):
                    raise ValueError('Closed stats header disagrees with accepted dispatch')
                verify_stats_completion(authority, pin, expected, accepted=accepted, completed=completed)
                snapshot.seek(0)
                publish_stats_file(directory, completed.filename, iter(lambda: snapshot.read(65536), b''),
                                   expected_size=completed.size, expected_sha256=sha256)
                verify_stats_completion(authority, pin, expected, accepted=accepted, completed=completed)
                publish_completion_manifest(directory, completed.receipt(), expected_sha256=sha256)
                verify_stats_completion(authority, pin, expected, accepted=accepted, completed=completed)
        finally:
            os.close(source_fd)
    finally:
        os.close(source_root_fd)
    return CapturedStats(capture_root, CompletedStatsReference(
        completed.generation, completed.filename, completed.size, sha256,
    ))
