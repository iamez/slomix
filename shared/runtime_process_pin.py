"""Read-only Linux process evidence for a future trusted host bootstrap.

No epoch allocation, discovery, signals, service management or dispatch. Trusted
procfs in this PID namespace and stable trusted executable ancestors required.
PID/UID/path/hash must come from independent operator configuration, not the
candidate's own claims. Does not authenticate Lua modules or physical rounds.
"""

import hashlib
import os
import re
import select
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from shared.runtime_failure_cleanup import CleanupOnError

_MAX_EXECUTABLE = 64 * 1024 * 1024


def _read_at(directory, name, maximum):
    fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory)
    try:
        chunks, size = [], 0
        while size <= maximum:
            chunk = os.read(fd, maximum + 1 - size)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        if size > maximum:
            raise ValueError('Process evidence exceeds read limit')
        return b''.join(chunks)
    finally:
        os.close(fd)


def _boot_id():
    value = _read_at(None, '/proc/sys/kernel/random/boot_id', 64).strip()
    if re.fullmatch(rb'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value) is None:
        raise ValueError('Invalid kernel boot identity')
    return value.decode('ascii')


def _start_ticks(raw, pid):
    # comm may contain spaces, ')' or newlines. Only fields AFTER its final
    # closing delimiter have whitespace-separated numeric positions.
    head, separator, tail = raw.rpartition(b') ')
    fields = tail.split()
    if (not separator or not head.startswith(f'{pid} ('.encode('ascii')) or len(fields) < 20
            or fields[0] not in (b'R', b'S', b'D', b'T', b't', b'K', b'W', b'P', b'I')
            or not fields[19].isdigit() or len(fields[19]) > 20):
        raise ValueError('Invalid or exited process stat')
    ticks = int(fields[19])
    if not 0 <= ticks <= 2**64 - 1:
        raise ValueError('Invalid process start identity')
    return ticks


def _uids(raw):
    rows = [line.split()[1:] for line in raw.splitlines() if line.startswith(b'Uid:')]
    if len(rows) != 1 or len(rows[0]) != 4 or not all(value.isdigit() for value in rows[0]):
        raise ValueError('Invalid process UID evidence')
    return tuple(int(value) for value in rows[0])


def _file_identity(fd):
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= _MAX_EXECUTABLE
            or info.st_mode & 0o022):
        raise ValueError('Executable must be bounded, regular and not group/world writable')
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_mode)


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    uid: int
    boot_id: str
    start_ticks: int
    executable_sha256: str


class ProcessPin:
    """Scoped, fail-closed evidence; not a dispatch capability or process lock.

    Checks do not freeze a process. Same-binary exec and Lua reload cannot be
    detected by these pins; lifecycle/module evidence must be supplied separately.
    No guarantee that a process survives or stays unchanged after assert_current.
    """

    def __init__(self, identity, pidfd, procfd, executable):
        self.identity = identity
        self._pidfd, self._procfd, self._executable = pidfd, procfd, executable
        self._invalidated = False

    def invalidate(self):
        """Permanently refuse further checks; the owning context closes FDs."""
        self._invalidated = True

    def assert_current(self):
        if self._invalidated:
            raise ValueError('Process pin is closed or invalidated')
        with CleanupOnError(self.invalidate):
            poller = select.poll()
            poller.register(self._pidfd, select.POLLIN)
            if poller.poll(0):
                raise ValueError('Pinned process exited or became unavailable')
            if (_boot_id() != self.identity.boot_id
                    or _start_ticks(_read_at(self._procfd, 'stat', 4096), self.identity.pid) != self.identity.start_ticks
                    or _uids(_read_at(self._procfd, 'status', 65536)) != (self.identity.uid,) * 4):
                raise ValueError('Pinned process identity changed')
            # /proc/PID/exe is intentionally a kernel magic link; do not apply
            # O_NOFOLLOW here. The proc directory itself was opened no-follow.
            fd = os.open('exe', os.O_RDONLY | os.O_CLOEXEC, dir_fd=self._procfd)
            try:
                if _file_identity(fd) != self._executable:
                    raise ValueError('Pinned process executable changed')
            finally:
                os.close(fd)
            if poller.poll(0):
                raise ValueError('Pinned process exited during inspection')
        return self.identity


@contextmanager
def pin_process(pid, *, expected_uid, expected_executable: Path, expected_sha256):
    """Hold native handles for one independently selected, already running PID.

    Hash at most 64 MiB once, recheck metadata/liveness after hashing. Short-lived
    native FDs close on all outcomes. No fallback when procfs/pidfd is unavailable.
    Path must be absolute and its final component not a symlink. Owners may write
    their binaries; hostile same-user/root mutation is outside this evidence model.
    """
    if type(pid) is not int or not 0 < pid <= 2_147_483_647:
        raise ValueError('Explicit positive Linux PID required')
    if type(expected_uid) is not int or not 0 <= expected_uid < 2**32 - 1:
        raise ValueError('Explicit Linux UID required')
    if not isinstance(expected_executable, Path) or not expected_executable.is_absolute():
        raise ValueError('Explicit absolute executable path required')
    if not isinstance(expected_sha256, str) or re.fullmatch(r'[0-9a-f]{64}', expected_sha256) is None:
        raise ValueError('Explicit approved executable SHA256 required')
    owned, pin = [], None
    try:
        pidfd = os.pidfd_open(pid, 0)
        owned.append(pidfd)
        procfd = os.open(f'/proc/{pid}', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        owned.append(procfd)
        approved = os.open(expected_executable, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        owned.append(approved)
        executable = _file_identity(approved)
        actual = os.open('exe', os.O_RDONLY | os.O_CLOEXEC, dir_fd=procfd)
        owned.append(actual)
        if _file_identity(actual) != executable:
            raise ValueError('Process does not run the approved executable inode')
        digest, offset = hashlib.sha256(), 0
        while offset < executable[2]:
            chunk = os.pread(actual, min(1024 * 1024, executable[2] - offset), offset)
            if not chunk:
                raise ValueError('Executable shortened while hashing')
            digest.update(chunk)
            offset += len(chunk)
        if digest.hexdigest() != expected_sha256 or _file_identity(actual) != executable:
            raise ValueError('Executable digest or metadata disagrees with approval')
        identity = ProcessIdentity(pid, expected_uid, _boot_id(),
                                   _start_ticks(_read_at(procfd, 'stat', 4096), pid), expected_sha256)
        pin = ProcessPin(identity, pidfd, procfd, executable)
        pin.assert_current()
        yield pin
    finally:
        if pin is not None:
            pin.invalidate()
        for fd in reversed(owned):
            os.close(fd)
