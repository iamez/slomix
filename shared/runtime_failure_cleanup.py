"""Failure-only resource cleanup without catching or suppressing control flow."""

from contextlib import AbstractContextManager


class CleanupOnError(AbstractContextManager):
    """Run the owned cleanup on exceptional exit, including cancellation/exit.

    Successful exit does nothing. A cleanup failure propagates normally with
    the original exception as its context; no retry or acknowledgement occurs.
    """

    def __init__(self, cleanup):
        self._cleanup = cleanup

    def __exit__(self, exception_type, exception, traceback):
        if exception_type is not None:
            self._cleanup()
        return False
