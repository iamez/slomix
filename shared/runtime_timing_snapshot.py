"""Authenticated timing bytes sealed in memory; durable capture is a later step."""
import hashlib
import os
import stat
from contextlib import contextmanager
from pathlib import Path

from shared.runtime_host_timing_completion import verify_timing_completion
from shared.runtime_sealed_snapshot import sealed_stats_snapshot

_METADATA = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')


@contextmanager
def timing_snapshot(authority, pin, expected, *, accepted, completed,
                    expected_filename, source_directory):
    """Yield (sealed stream, SHA256) only while all owned descriptors remain open.

    Independently provisioned local directory and trusted same-UID ownership are
    required. No JSON identity inference, durable publication, source ACK or deletion.
    Source bytes and path are checked before yielding; sealed bytes cannot change.
    """
    def verify():
        verify_timing_completion(authority, pin, expected, accepted=accepted,
                                 completed=completed, expected_filename=expected_filename)

    verify()
    if not isinstance(source_directory, Path) or not source_directory.is_absolute():
        raise ValueError('Independent absolute timing source directory required')
    root = os.open(source_directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        root_info = os.fstat(root)
        if root_info.st_uid != pin.identity.uid or root_info.st_mode & 0o077:
            raise ValueError('Timing source directory must be private to producer')
        fd = os.open(completed.filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=root)
        try:
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != pin.identity.uid
                    or before.st_mode & 0o002 or before.st_nlink != 1 or before.st_size != completed.size):
                raise ValueError('Timing source must be owned, regular, single-link and exact size')
            digest = hashlib.sha256()
            offset = 0
            while offset < completed.size:
                chunk = os.pread(fd, min(65536, completed.size - offset), offset)
                if not chunk:
                    raise ValueError('Timing source ended before declared size')
                digest.update(chunk)
                offset += len(chunk)
            sha256 = digest.hexdigest()
            with sealed_stats_snapshot(fd, expected_size=completed.size, expected_sha256=sha256) as snapshot:
                named = os.stat(completed.filename, dir_fd=root, follow_symlinks=False)
                if any(getattr(before, field) != getattr(named, field) for field in _METADATA):
                    raise ValueError('Timing source name changed during capture')
                current = os.stat(source_directory, follow_symlinks=False)
                if (current.st_dev, current.st_ino, current.st_mode, current.st_uid) != (
                        root_info.st_dev, root_info.st_ino, root_info.st_mode, root_info.st_uid):
                    raise ValueError('Timing source directory changed')
                verify()
                yield snapshot, sha256
                verify()
        finally:
            os.close(fd)
    finally:
        os.close(root)
