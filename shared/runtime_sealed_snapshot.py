"""Bounded Linux kernel-sealed read snapshots, not durable capture storage."""

import fcntl
import hashlib
import os
import re
import stat
from contextlib import contextmanager

_SEALS = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL


@contextmanager
def sealed_stats_snapshot(source_fd: int, *, expected_size: int, expected_sha256: str):
    """Yield an immutable copy of a trusted regular-file descriptor at offset zero.

    Caller authenticates identity/digest and owns the source descriptor throughout
    this call. pread preserves its offset; no source pathname is reopened. Limit
    is 8 MiB, independent of declared file size. Local reads are byte-bounded,
    not time-bounded. Metadata drift or a digest mismatch refuses delivery.
    Kernel seals prohibit writes/grow/shrink even through another writable fd.
    The returned binary stream is valid only inside the context; caller must not
    close it or retain duplicates. All snapshot descriptors owned here are closed
    on failure/exit. No disk durability, producer authentication, IPC, network,
    parsing, import acknowledgement or automatic source deletion is provided.
    """
    if type(source_fd) is not int or source_fd < 0:
        raise ValueError('Source must be an owned open file descriptor')
    if type(expected_size) is not int or not 0 < expected_size <= 8 * 1024 * 1024:
        raise ValueError('Snapshot size must be between 1 byte and 8 MiB')
    if not isinstance(expected_sha256, str) or re.fullmatch('[0-9a-f]{64}', expected_sha256) is None:
        raise ValueError('Snapshot requires trusted lowercase SHA-256')
    before = os.fstat(source_fd)
    if not stat.S_ISREG(before.st_mode) or before.st_size != expected_size:
        raise ValueError('Source must be a regular file of the expected size')
    fd = os.memfd_create('slomix-stats-snapshot', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    try:
        with os.fdopen(fd, 'w+b', closefd=False) as snapshot:
            digest = hashlib.sha256()
            total = 0
            while total < expected_size:
                chunk = os.pread(source_fd, min(65536, expected_size - total), total)
                if not chunk:
                    raise ValueError('Source ended before expected size')
                snapshot.write(chunk)
                digest.update(chunk)
                total += len(chunk)
            after = os.fstat(source_fd)
            if any(getattr(before, field) != getattr(after, field) for field in (
                'st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns',
            )):
                raise ValueError('Source changed while taking snapshot')
            if digest.hexdigest() != expected_sha256:
                raise ValueError('Snapshot SHA-256 mismatch')
            snapshot.flush()
            fcntl.fcntl(fd, fcntl.F_ADD_SEALS, _SEALS)
            if fcntl.fcntl(fd, fcntl.F_GET_SEALS) & _SEALS != _SEALS:
                raise RuntimeError('Snapshot sealing incomplete')
            snapshot.seek(0)
        with os.fdopen(fd, 'rb', closefd=False) as snapshot:
            yield snapshot
    finally:
        os.close(fd)
