"""Bounded read of an explicitly verified private proximity source, without writes."""

import hashlib
import os
import re
import stat
from pathlib import Path

_NAME = re.compile(r'\d{4}-\d{2}-\d{2}-\d{6}-[A-Za-z0-9_.+-]+-round-[12]_engagements\.txt', re.ASCII)


def read_verified_proximity_source(
    path: Path, *, expected_size: int, expected_sha256: str,
    max_bytes: int = 8 * 1024 * 1024,
) -> bytes:
    """Return the exact bytes to parse, not a path to reopen after verification.

    Caller supplies trusted metadata from a sealed source and a private local
    spool. This verifies bytes, not remote authenticity, fsync or a read deadline.
    Only a user-owned private regular file is accepted; no symlinks or FIFOs.
    The bound covers raw input, not the parser's expanded object memory usage.
    """
    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError('Proximity source must be an absolute Path')
    if not _NAME.fullmatch(path.name) or '..' in path.name:
        raise ValueError('Invalid proximity source filename')
    if (type(expected_size) is not int or type(max_bytes) is not int
            or not 0 < expected_size <= max_bytes):
        raise ValueError('Source size must be positive and within the byte limit')
    if not isinstance(expected_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', expected_sha256, re.ASCII):
        raise ValueError('Expected SHA-256 must be lowercase 64-character hex')
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        parent = os.fstat(directory)
        if parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) != 0o700:
            raise ValueError('Proximity spool must be user-owned with mode 0700')
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        try:
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                    or stat.S_IMODE(before.st_mode) not in (0o400, 0o600)):
                raise ValueError('Proximity source must be an owned private regular file (0400/0600)')
            if before.st_size != expected_size:
                raise ValueError('Proximity source size mismatch')
            chunks = []
            remaining = expected_size + 1
            while remaining:
                chunk = os.read(fd, min(64 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            after = os.fstat(fd)
            named = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
            for current in (after, named):
                if any(getattr(before, field) != getattr(current, field) for field in (
                    'st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode',
                )):
                    raise RuntimeError('Proximity source changed during read')
            payload = b''.join(chunks)
            if len(payload) != expected_size or hashlib.sha256(payload).hexdigest() != expected_sha256:
                raise ValueError('Proximity source digest/size mismatch')
            return payload
        finally:
            os.close(fd)
    finally:
        os.close(directory)


async def bind_proximity_source(adapter, filename: str, digest: str) -> None:
    """Verify the digest bound during receipt claim in the same transaction.

    Never adopt any existing legacy receipt with unknown content identity.
    This runtime-only protocol requires exclusive handover from legacy writers;
    the legacy parser does not enforce content identity yet.
    """
    row = await adapter.fetch_one(
        'SELECT file_hash FROM proximity_processed_files WHERE filename = ?',
        (filename,),
    )
    if row is None:
        raise RuntimeError('Proximity source binding requires a claimed receipt')
    previous_hash = row[0]
    if previous_hash is None:
        raise ValueError('Existing proximity receipt has unverified source identity')
    elif previous_hash != digest:
        raise ValueError('Proximity source conflicts with recorded content identity')
