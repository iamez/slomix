"""Linux-only exclusive generation reservation; no producer or service activation."""

import os
import re
import stat
from pathlib import Path


def reserve_source_generation(directory: Path, generation: str) -> Path:
    """Create exactly one fresh private directory for a caller-chosen generation.

    Caller supplies a stable owner-only root and a unique 32-character lowercase
    hex token (for example UUID.hex). Atomic mkdir refuses ALL existing entries,
    even empty directories or symlinks. Fsync the child and parent before success.
    Any error after mkdir may leave the reserved directory; never delete/reuse it
    automatically. Retrying that same token then raises FileExistsError.

    This reserves a namespace, not a lease or a completed snapshot. Caller must
    give it to a sole producer, prevent later rewrites, and integrate completion
    receipts separately. No automatic tokens/retries, cleanup, payload writes,
    hashing, trusted identity delivery, Lua wiring or service control. Directory
    must remain stable through subsequent use; returned Path is not a capability.
    Local filesystem operations have no wall-clock bound.
    """
    if not isinstance(directory, Path) or not directory.is_absolute():
        raise ValueError('Source reservation root must be an absolute Path')
    if not isinstance(generation, str) or re.fullmatch(r'[0-9a-f]{32}', generation, re.ASCII) is None:
        raise ValueError('Source generation must be 32 lowercase hexadecimal characters')
    root_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        root = os.fstat(root_fd)
        if root.st_uid != os.getuid() or stat.S_IMODE(root.st_mode) != 0o700:
            raise ValueError('Source reservation root must be owned by this user with mode 0700')
        os.mkdir(generation, mode=0o700, dir_fd=root_fd)
        child_fd = os.open(generation, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        try:
            child = os.fstat(child_fd)
            if child.st_uid != os.getuid() or stat.S_IMODE(child.st_mode) != 0o700:
                raise ValueError('Source reservation must have owner-only mode 0700')
            os.fsync(child_fd)
        finally:
            os.close(child_fd)
        os.fsync(root_fd)
    finally:
        os.close(root_fd)
    return directory / generation
