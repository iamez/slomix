"""Linux-only no-clobber publication into a caller-owned private stats spool."""

import os
import re
import stat
import uuid
from collections.abc import Iterable
from pathlib import Path

_NAME = re.compile(r'\d{4}-\d{2}-\d{2}-\d{6}-[A-Za-z0-9_.+-]+-round-[12]\.txt', re.ASCII)


def publish_stats_file(
    directory: Path, filename: str, chunks: Iterable[bytes], *,
    expected_size: int, max_bytes: int = 8 * 1024 * 1024,
) -> Path:
    """Expose a complete, fsynced file atomically, never replacing an old one.

    Requires an existing owner-only directory, immutable upstream snapshot and
    bounded chunk producer (including its timeouts). Size is not an integrity
    hash and cannot detect equal-length upstream mutation. Existing destinations
    raise FileExistsError, even for identical bytes; callers reconcile explicitly.
    A failure after link publication may leave the complete final file visible;
    retry must inspect it, never delete/overwrite it. Crash leftovers ending in
    .part are not import candidates. No retention or orphan cleanup is done here.
    """
    if not _NAME.fullmatch(filename) or '..' in filename:
        raise ValueError('Invalid stats filename')
    if (type(expected_size) is not int or type(max_bytes) is not int
            or not 0 < expected_size <= max_bytes):
        raise ValueError('Expected size must be positive and within the byte limit')
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
            for chunk in chunks:
                if not isinstance(chunk, bytes):
                    raise TypeError('Capture chunks must be bytes')
                total += len(chunk)
                if total > expected_size:
                    raise ValueError('Capture exceeds expected size')
                stream.write(chunk)
            if total != expected_size:
                raise ValueError('Capture is incomplete')
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
