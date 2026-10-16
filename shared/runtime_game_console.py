"""One fixed console command to an already approved, mapless ET process.

No launch, RCON, signals, arbitrary commands or retry. A trusted supervisor owns
the private pipe exclusively, prevents prior commands and calls this hook only
from serve_match(on_ready=...). Kernel pipe identity is not engine attestation.
"""

import fcntl
import os
import stat
from contextlib import contextmanager
from threading import Lock

from shared.runtime_process_pin import ProcessPin

MAP_COMMAND = b'map supply\n'


def _check_pipe(pin, fd):
    identity = pin.assert_current()
    info = os.fstat(fd)
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    # /proc/PID/fd/0 is intentionally followed: it is the kernel's stdin handle,
    # not an application-controlled path. Pin is revalidated on both sides.
    stdin = os.stat(f'/proc/{identity.pid}/fd/0')
    if (not stat.S_ISFIFO(info.st_mode) or not stat.S_ISFIFO(stdin.st_mode)
            or (info.st_dev, info.st_ino) != (stdin.st_dev, stdin.st_ino)
            or info.st_uid != identity.uid or identity.uid != os.getuid()
            or flags & os.O_ACCMODE != os.O_WRONLY or not flags & os.O_NONBLOCK):
        raise ValueError('Exclusive nonblocking pipe to pinned process stdin required')
    pin.assert_current()


@contextmanager
def map_release(pin: ProcessPin, write_fd: int):
    """Own a duplicated FD and yield a once-only nonblocking readiness callback.

Caller retains its original FD. Any attempted invocation, including failure,
consumes this capability; never retry an ambiguous write. <= PIPE_BUF bytes
are sent in one syscall. Success means queued bytes, NOT a loaded map or round.
Callback after context exit is refused. Other writers/hostile same-UID changes
and readiness ordering remain the trusted supervisor's responsibility.
"""
    if not isinstance(pin, ProcessPin) or type(write_fd) is not int or write_fd < 0:
        raise ValueError('Explicit process pin and pipe descriptor required')
    fd = os.dup(write_fd)
    lock = Lock()
    attempted = False
    closed = False
    try:
        _check_pipe(pin, fd)
        if len(MAP_COMMAND) > os.fpathconf(fd, 'PC_PIPE_BUF'):
            raise ValueError('Console command exceeds atomic pipe write bound')

        def release():
            nonlocal attempted
            if not lock.acquire(blocking=False):
                raise ValueError('Concurrent console release refused')
            try:
                if attempted or closed:
                    raise ValueError('Console release already consumed or closed')
                attempted = True
                _check_pipe(pin, fd)
                if os.write(fd, MAP_COMMAND) != len(MAP_COMMAND):
                    raise OSError('Incomplete console map release; do not retry')
            finally:
                lock.release()

        yield release
    finally:
        with lock:
            closed = True
            os.close(fd)
