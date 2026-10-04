"""Linux-only no-clobber publication into caller-owned private input spools."""

import hashlib
import os
import re
import stat
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

_NAME = re.compile(r'\d{4}-\d{2}-\d{2}-\d{6}-[A-Za-z0-9_.+-]+-round-[12]\.txt', re.ASCII)
_PROXIMITY_NAME = re.compile(
    r'\d{4}-\d{2}-\d{2}-\d{6}-[A-Za-z0-9_.+-]+-round-[12]_engagements\.txt', re.ASCII,
)


def validate_stats_filename(filename: str) -> None:
    """Shared structural admission; calendar validity belongs to the importer."""
    if not _NAME.fullmatch(filename) or '..' in filename:
        raise ValueError('Invalid stats filename')


def _validate_metadata(filename, expected_size, max_bytes, expected_sha256, *, name_pattern=_NAME):
    """Apply identical metadata bounds to publication and reconciliation."""
    if name_pattern is _NAME:
        validate_stats_filename(filename)
    elif not name_pattern.fullmatch(filename) or '..' in filename:
        raise ValueError('Invalid input filename')
    if expected_sha256 is not None and (
        not isinstance(expected_sha256, str)
        or re.fullmatch(r'[0-9a-f]{64}', expected_sha256, re.ASCII) is None
    ):
        raise ValueError('Expected SHA-256 must be lowercase 64-character hex')
    if (type(expected_size) is not int or type(max_bytes) is not int
            or not 0 < expected_size <= max_bytes):
        raise ValueError('Expected size must be positive and within the byte limit')


def publish_stats_file(
    directory: Path, filename: str, chunks: Iterable[bytes], *,
    expected_size: int, max_bytes: int = 8 * 1024 * 1024,
    expected_sha256: str | None = None,
) -> Path:
    """Expose a complete, fsynced file atomically, never replacing an old one.

    Requires an existing owner-only directory, immutable upstream snapshot and
    bounded chunk producer (including its timeouts). Size is not an integrity
    hash and cannot detect equal-length upstream mutation. Supply expected_sha256
    from a trusted immutable source snapshot for content verification; omission
    retains size-only validation. The digest must be lowercase 64-character hex.
    This does not authenticate the source or establish snapshot immutability.
    Existing destinations
    raise FileExistsError, even for identical bytes; callers reconcile explicitly.
    A failure after link publication may leave the complete final file visible;
    retry must inspect it, never delete/overwrite it. Crash leftovers ending in
    .part are not import candidates. No retention or orphan cleanup is done here.
    """
    _validate_metadata(filename, expected_size, max_bytes, expected_sha256)
    return _publish_file(directory, filename, chunks, expected_size, expected_sha256)


def publish_proximity_file(
    directory: Path, filename: str, chunks: Iterable[bytes], *,
    expected_size: int, expected_sha256: str, max_bytes: int = 8 * 1024 * 1024,
) -> Path:
    """Publish verified proximity bytes, keeping the stats allowlist separate.

    Requires an absolute private directory and trusted size/digest from a sealed
    upstream snapshot. Publication mechanics and failure semantics are those of
    publish_stats_file: no overwrite, file and directory fsync, final entry may
    survive a post-link error. Reconcile that entry; never overwrite or delete it.
    Caller bounds chunk allocation and streaming time, and owns source lifecycle.
    This is not remote authentication, sealing, a deadline or a worker. Shared
    legacy input directories must not be chmodded to satisfy this contract.
    """
    if not isinstance(directory, Path) or not directory.is_absolute():
        raise ValueError('Proximity spool must be an absolute Path')
    if expected_sha256 is None:
        raise ValueError('Proximity publication requires an expected SHA-256')
    _validate_metadata(filename, expected_size, max_bytes, expected_sha256,
                       name_pattern=_PROXIMITY_NAME)
    return _publish_file(directory, filename, chunks, expected_size, expected_sha256)


def _publish_file(directory, filename, chunks, expected_size, expected_sha256):
    """Shared publication mechanics; only validated wrappers may call this."""
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = '.incoming-' + uuid.uuid4().hex + '.part'
    created = False
    try:
        info = os.fstat(directory_fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('Spool must be owned by this user with mode 0700')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory_fd)
        created = True
        with os.fdopen(fd, 'wb') as stream:
            total = 0
            digest = hashlib.sha256() if expected_sha256 is not None else None
            for chunk in chunks:
                if not isinstance(chunk, bytes):
                    raise TypeError('Capture chunks must be bytes')
                total += len(chunk)
                if total > expected_size:
                    raise ValueError('Capture exceeds expected size')
                stream.write(chunk)
                if digest is not None:
                    digest.update(chunk)
            if total != expected_size:
                raise ValueError('Capture is incomplete')
            if digest is not None and digest.hexdigest() != expected_sha256:
                raise ValueError('Capture SHA-256 mismatch')
            stream.flush()
            os.fsync(stream.fileno())
        # Same-directory hard link is atomic and fails if the final name exists.
        os.link(temporary, filename, src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
                follow_symlinks=False)
        os.fsync(directory_fd)
    finally:
        try:
            if created:
                os.unlink(temporary, dir_fd=directory_fd)
        finally:
            os.close(directory_fd)
    return directory / filename


def inspect_published_stats_file(
    directory: Path, filename: str, *, expected_size: int, expected_sha256: str,
    max_bytes: int = 8 * 1024 * 1024,
) -> Literal['missing', 'match', 'conflict']:
    """Inspect an immutable private spool entry without replacing/removing it.

    Only missing final entries return missing; inaccessible/unsafe paths raise.
    Match means observed size/content, NOT fsync durability or successful import.
    Caller must retain the immutable directory/file through subsequent use;
    descriptor/name checks detect changes during inspection, not future changes.
    Reading is byte-bounded, not time-bounded (requires a local regular file).
    Owner-readable private modes 0400/0600 are accepted: publication respects
    umask, and inspection must not widen deliberately restrictive permissions.
    """
    if expected_sha256 is None:
        raise ValueError('Inspection requires an expected SHA-256')
    _validate_metadata(filename, expected_size, max_bytes, expected_sha256)
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(directory_fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('Spool must be owned by this user with mode 0700')
        try:
            fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=directory_fd)
        except FileNotFoundError:
            return 'missing'
        try:
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                    or stat.S_IMODE(before.st_mode) not in (0o400, 0o600)):
                raise ValueError('Published entry must be an owned owner-readable private regular file (0400/0600)')
            digest = hashlib.sha256()
            remaining = expected_size + 1 if before.st_size == expected_size else 0
            total = 0
            while remaining:
                chunk = os.read(fd, min(64 * 1024, remaining))
                if not chunk:
                    break
                digest.update(chunk)
                total += len(chunk)
                remaining -= len(chunk)
            after = os.fstat(fd)
            named = os.stat(filename, dir_fd=directory_fd, follow_symlinks=False)
            for current in (after, named):
                if any(getattr(before, field) != getattr(current, field) for field in (
                    'st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode',
                )):
                    raise RuntimeError('Published entry changed during inspection')
            return 'match' if total == expected_size and digest.hexdigest() == expected_sha256 else 'conflict'
        finally:
            os.close(fd)
    finally:
        os.close(directory_fd)
