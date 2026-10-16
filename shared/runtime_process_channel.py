"""Bounded Linux local channel to an independently pinned, trusted game process.

Caller owns listener creation in a protected pathname and enables SO_PASSCRED
BEFORE accept. No listener/service/discovery/epoch issuance here. This context
takes exclusive ownership of the accepted socket, including on failure. Never
share/duplicate it. Kernel credentials authenticate process, NOT Lua lifecycle
or physical rounds; privileged/same-process attackers are outside this contract.
See Linux unix(7): peer credentials are connect-time; per-message credentials
also reject a forked child writing an inherited descriptor.
"""

import array
import math
import os
import select
import socket
import struct
import time
from contextlib import contextmanager

from shared.runtime_failure_cleanup import CleanupOnError
from shared.runtime_process_pin import ProcessPin

_CREDENTIALS = struct.Struct('iII')
_MAX_LINE = 512


def _wire(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= _MAX_LINE
            or any(not 32 <= ord(char) <= 126 for char in value)):
        raise ValueError('Channel requires bounded printable ASCII line')
    return value.encode('ascii') + b'\n'


class ProcessChannel:
    def __init__(self, connection, pin, timeout):
        self._socket, self._pin = connection, pin
        self._closed, self._buffer = False, b''
        self._deadline = time.monotonic() + timeout
        self._check()

    def close(self):
        self._closed, self._buffer = True, b''
        self._socket.close()

    def _check(self):
        if self._closed:
            raise ValueError('Process channel closed')
        if time.monotonic() >= self._deadline:
            raise TimeoutError('Process channel deadline expired')
        identity = self._pin.assert_current()
        pid, uid, _ = _CREDENTIALS.unpack(self._socket.getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, _CREDENTIALS.size))
        if (pid, uid) != (identity.pid, identity.uid):
            raise ValueError('Channel peer disagrees with pinned process')
        if not self._socket.getsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED):
            raise ValueError('Channel credential reception disabled')
        return identity

    def _wait(self, writing=False):
        self._check()
        remaining = max(0, self._deadline - time.monotonic())
        reads, writes, _ = select.select([] if writing else [self._socket],
                                        [self._socket] if writing else [], [], remaining)
        self._check()
        if not (reads or writes):
            raise TimeoutError('Process channel deadline expired')

    def _credentials(self, ancillary, flags, identity):
        credentials, unexpected = [], False
        # Close every descriptor the kernel installed, even when control data
        # is truncated. Linux closes excess descriptors that do not fit.
        for level, kind, data in ancillary:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                received = array.array('i')
                received.frombytes(data[:len(data) - len(data) % received.itemsize])
                for fd in received:
                    os.close(fd)
                unexpected = True
            elif level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS:
                if len(data) == _CREDENTIALS.size:
                    credentials.append(_CREDENTIALS.unpack(data))
                else:
                    unexpected = True
            else:
                unexpected = True
        if flags & (socket.MSG_CTRUNC | socket.MSG_TRUNC) or unexpected or len(credentials) != 1:
            raise ValueError('Missing, truncated or unexpected channel credentials')
        pid, uid, _ = credentials[0]
        if (pid, uid) != (identity.pid, identity.uid):
            raise ValueError('Channel message sender disagrees with pinned process')

    def receive_line(self):
        """One bounded ASCII frame, one absolute channel deadline; no slow drip reset."""
        with CleanupOnError(self.close):
            while True:
                self._check()
                if b'\n' in self._buffer:
                    raw, self._buffer = self._buffer.split(b'\n', 1)
                    value = raw.decode('ascii')
                    _wire(value)
                    return value
                if len(self._buffer) > _MAX_LINE:
                    raise ValueError('Channel line exceeds bound')
                self._wait()
                try:
                    data, ancillary, flags, _ = self._socket.recvmsg(
                        _MAX_LINE + 1 - len(self._buffer),
                        socket.CMSG_SPACE(_CREDENTIALS.size) + socket.CMSG_SPACE(16 * 4),
                        socket.MSG_CMSG_CLOEXEC | socket.MSG_DONTWAIT)
                except BlockingIOError:
                    continue
                # Ancillary cleanup MUST precede process/deadline checks: even
                # a peer that exited after sendmsg may have installed FDs here.
                if data or ancillary or flags:
                    self._credentials(ancillary, flags, self._pin.identity)
                self._check()
                if not data:
                    raise EOFError('Process channel ended before complete line')
                self._buffer += data

    def send_line(self, value):
        """Send once; a partial/error outcome closes and never authorizes replay."""
        with CleanupOnError(self.close):
            pending = memoryview(_wire(value))
            while pending:
                self._wait(writing=True)
                try:
                    sent = self._socket.send(pending, socket.MSG_DONTWAIT | socket.MSG_NOSIGNAL)
                except BlockingIOError:
                    continue
                if sent <= 0:
                    raise EOFError('Process channel send failed')
                pending = pending[sent:]
            self._check()


@contextmanager
def process_channel(connection: socket.socket, pin: ProcessPin, *, timeout=5.0):
    """Take an already accepted exclusive socket; close on every outcome.

    Absolute timeout covers ALL reads/writes, not each frame separately. The
    listener must have enabled SO_PASSCRED; refuse rather than retroactively
    treating already queued bytes as authenticated. No blocking game callbacks.
    """
    channel = None
    try:
        if (not isinstance(connection, socket.socket) or connection.family != socket.AF_UNIX
                or connection.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_STREAM):
            raise ValueError('Connected Unix stream socket required')
        if not isinstance(pin, ProcessPin):
            raise ValueError('Independent native process pin required')
        if (type(timeout) not in (int, float) or not math.isfinite(timeout)
                or not 0 < timeout <= 10):
            raise ValueError('Channel timeout must be positive and at most ten seconds')
        channel = ProcessChannel(connection, pin, timeout)
        yield channel
    finally:
        if channel is not None:
            channel.close()
        elif isinstance(connection, socket.socket):
            connection.close()
