"""Bounded Linux same-UID listener for exactly one independently allocated match.

No game launch, scheduler, service control, import, automatic retry or cleanup.
The operator must start this BEFORE the game's configured InitGame handshake;
the caller must already hold an independently approved live process pin. This
does not solve engine startup coordination, trusted Lua loading or fs_homepath
mapping. A Python protocol peer is not evidence of those engine prerequisites.
"""

import math
import os
import select
import socket
import stat
import time
from contextlib import contextmanager
from pathlib import Path

from shared.runtime_failure_cleanup import CleanupOnError
from shared.runtime_match_controller import RuntimeMatchController
from shared.runtime_socket_path import validate_socket_path
from shared.runtime_source_reservation import _open_root


def _timeout(value, maximum):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
        raise ValueError(f'Listener timeout must be positive and at most {maximum} seconds')
    return value


def _key(info):
    return info.st_dev, info.st_ino


@contextmanager
def _listener(path):
    # Stable, trusted ancestors and no hostile same-UID writes are required,
    # as for the controller's other private roots. Bind through the held dirfd
    # so replacement of the pathname cannot redirect the creation elsewhere.
    if not isinstance(path, Path):
        raise ValueError('Explicit canonical bounded Unix socket pathname required')
    validate_socket_path(str(path))
    if path.parent.resolve(strict=True) != path.parent:
        raise ValueError('Explicit canonical bounded Unix socket pathname required')
    root = _open_root(path.parent, '0' * 32)
    try:
        root_key = _key(os.fstat(root))
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            # Set BEFORE listen/accept: queued pre-accept bytes need credentials.
            server.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
            server.bind(f'/proc/self/fd/{root}/{path.name}')
            os.chmod(path.name, 0o600, dir_fd=root, follow_symlinks=False)
            socket_key = _key(os.stat(path.name, dir_fd=root, follow_symlinks=False))
            os.fsync(root)

            def verify():
                current = _open_root(path.parent, '0' * 32)
                try:
                    if _key(os.fstat(current)) != root_key:
                        raise ValueError('Listener directory identity changed')
                finally:
                    os.close(current)
                info = os.stat(path.name, dir_fd=root, follow_symlinks=False)
                if (_key(info) != socket_key or not stat.S_ISSOCK(info.st_mode)
                        or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600):
                    raise ValueError('Listener socket identity or permissions changed')

            verify()
            server.listen(4)
            server.setblocking(False)
            yield server, verify
            verify()
    finally:
        os.close(root)
    # Intentionally retain the pathname even on failure. Never unlink/rebind a
    # previous run's socket automatically; an existing entry always refuses bind.


def _accept(server, verify, controller, wait):
    deadline = time.monotonic() + wait
    while True:
        controller.check_waiting()
        verify()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Runtime listener connection deadline expired')
        # Detect dead source/root replacement without waiting an entire round.
        readable, _, _ = select.select([server], [], [], min(remaining, 0.25))
        if not readable:
            continue
        try:
            connection, _ = server.accept()
        except BlockingIOError:
            continue
        with CleanupOnError(connection.close):
            controller.check_waiting()
            verify()
            if time.monotonic() >= deadline:
                raise TimeoutError('Runtime listener connection deadline expired')
            return connection


def serve_match(controller: RuntimeMatchController, socket_path: Path, *,
                bootstrap_wait=30.0, completion_wait=1800.0, exchange_timeout=5.0,
                on_ready=None):
    """Exclusively own one ready controller until two captures or terminal failure.

    At most four admitted connections: bootstrap/close, bootstrap/close. The
    existing channel authenticates both peer PID/UID and each received message.
    Wrong peers/protocols fail closed, never consume an unbounded retry loop.
    Accept waits and IPC exchanges have separate deadlines; completion_wait is
    NOT a limit on actual ET round length and exceeding it requires explicit
    reconciliation. Filesystem syscall latency is not bounded by these timers.

    Close the listener before returning the verified import handoff. No source
    ACK, file deletion, import or success reconstruction from persisted claims.
    Caller must not share/reuse the controller concurrently with this function.

    Optional on_ready() is called exactly once AFTER listen(), first dispatch
    reservation and live process/root checks, before the first accept. It lets
    the operator observe readiness without polling private controller state.
    It is not proof of game initialization or permission to launch a game.
    The callback must return promptly, must not operate on the controller, and
    is not covered by IPC deadlines. Failure fences the controller normally.
    """
    _timeout(bootstrap_wait, 3600)
    _timeout(completion_wait, 7200)
    _timeout(exchange_timeout, 10)
    if on_ready is not None and not callable(on_ready):
        raise ValueError('Listener readiness observer must be callable')
    if not isinstance(controller, RuntimeMatchController) or controller.state != 'ready':
        raise ValueError('Listener requires an exclusively owned ready match controller')
    with CleanupOnError(controller.abort):
        with _listener(socket_path) as (server, verify):
            for half in (1, 2):
                controller.prepare_half()
                if half == 1 and on_ready is not None:
                    controller.check_waiting()
                    verify()
                    on_ready()
                connection = _accept(server, verify, controller, bootstrap_wait)
                controller.bootstrap(connection, timeout=exchange_timeout)
                connection = _accept(server, verify, controller, completion_wait)
                controller.complete(connection, timeout=exchange_timeout)
                verify()
        return controller.captured_match()
