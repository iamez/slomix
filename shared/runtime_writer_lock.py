"""Linux local cooperative writer exclusion; no service/PID management."""

import fcntl
import os
import stat
from contextlib import contextmanager
from pathlib import Path


class ImportWriterBusy(RuntimeError):
    """Another cooperating process owns the same local lock inode."""


@contextmanager
def local_import_writer(directory: Path):
    """Fail fast if a cooperating writer already owns this private directory.

    Caller supplies one stable owner-only local directory shared by all writers
    of the target. This is NOT a distributed/DB lock or database identity check;
    existing bot/manual/uncooperative writers do not participate automatically.
    Ancestors and the lock pathname must remain stable. Never unlink/replace the
    persistent empty lock file: doing so permits different lock inodes. No PID
    file, process termination, stale-lock removal or automatic directory creation.
    Closing our descriptor (including process exit) releases the kernel lock.
    Do not fork while holding it: children may inherit the open descriptor.
    """
    if not isinstance(directory, Path) or not directory.is_absolute():
        raise ValueError('Explicit absolute writer lock directory required')
    root_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    lock_fd = None
    try:
        root = os.fstat(root_fd)
        if root.st_uid != os.getuid() or stat.S_IMODE(root.st_mode) != 0o700:
            raise ValueError('Writer lock directory must be owned by this user with mode 0700')
        lock_fd = os.open(
            '.import-writer.lock',
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
            0o600, dir_fd=root_fd,
        )
        info = os.fstat(lock_fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise ValueError('Writer lock must be a private owned regular file with one link')
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ImportWriterBusy('Local import writer is already active') from None
        yield
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        os.close(root_fd)
