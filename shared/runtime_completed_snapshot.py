"""Bind a trusted generation expectation to its receipt and sealed processing bytes."""

import os
import re
import stat
from contextlib import contextmanager
from pathlib import Path

from shared.runtime_manifest_reader import inspect_completion_manifest
from shared.runtime_sealed_snapshot import sealed_stats_snapshot
from shared.runtime_spool import _validate_metadata


def _private_directory(fd):
    """Require the same private directory contract as reservation/publication."""
    info = os.fstat(fd)
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Completion root and generation must be owned mode 0700')


@contextmanager
def open_completed_snapshot(
    root: Path, generation: str, filename: str, *, expected_size: int, expected_sha256: str,
):
    """Yield sealed bytes only if the named generation's receipt matches expectation.

    Caller authenticates root/generation/name/size/hash together before this call;
    a local JSON receipt alone is not provenance. Stable root ancestry is required.
    Open root/generation with no-follow; open payload relative to the held generation
    descriptor, never by a subsequently re-resolved payload path. Existing receipt
    inspection may observe concurrent changes and fail; rehash the actual opened
    payload while sealing before delivery. At most16MiB content reads plus4097
    receipt bytes,8MiB anonymous storage. No time bound, retry loop, write/delete,
    producer claim, import acknowledgement or durable-sealing assertion.
    """
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError('Completion root must be an absolute Path')
    if not isinstance(generation, str) or re.fullmatch('[0-9a-f]{32}', generation) is None:
        raise ValueError('Invalid completion generation')
    if not isinstance(filename, str) or len(filename) > 240 or expected_sha256 is None:
        raise ValueError('Completion requires bounded filename and trusted digest')
    _validate_metadata(filename, expected_size, 8 * 1024 * 1024, expected_sha256)
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        _private_directory(root_fd)
        generation_fd = os.open(generation, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        try:
            _private_directory(generation_fd)
            observed = inspect_completion_manifest(root / generation, filename)
            if (observed.status != 'match' or observed.size != expected_size
                    or observed.sha256 != expected_sha256):
                raise ValueError('Completion receipt/content does not match trusted expectation')
            payload_fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=generation_fd)
            try:
                info = os.fstat(payload_fd)
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                        or stat.S_IMODE(info.st_mode) not in (0o400, 0o600)):
                    raise ValueError('Completed payload must be an owned mode 0400/0600 regular file')
                with sealed_stats_snapshot(payload_fd, expected_size=expected_size,
                                           expected_sha256=expected_sha256) as snapshot:
                    yield snapshot
            finally:
                os.close(payload_fd)
        finally:
            os.close(generation_fd)
    finally:
        os.close(root_fd)
