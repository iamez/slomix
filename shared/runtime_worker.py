"""Deadline supervision for a single disposable, capture-only child process."""

import math
import multiprocessing
import signal
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class WorkerResult:
    """Process outcome, never a capture durability or database acknowledgement."""

    status: Literal['completed', 'failed', 'timed_out']
    pid: int
    exit_code: int


def _execute(task: Callable[[], None]) -> None:
    """Do not expose task exception text, credentials or payload through IPC."""
    try:
        task()
    except BaseException:
        raise SystemExit(1) from None


def _reap(process, grace: float) -> BaseException | None:
    """Reap our child before returning a deferred cleanup exception."""
    interrupted = None
    for stop in (process.terminate, process.kill):
        deadline = time.monotonic() + grace
        while True:
            try:
                if not process.is_alive():
                    return interrupted
                # Even an expired phase must attempt its stopping signal once.
                # Its deadline limits waits/retries, not the initial escalation.
                stop()
                process.join(max(0.0, deadline - time.monotonic()))
                if not process.is_alive():
                    return interrupted
                if time.monotonic() >= deadline:
                    break
            except BaseException as exc:
                if interrupted is None:
                    interrupted = exc
                if time.monotonic() >= deadline:
                    break
    raise RuntimeError(f'Owned runtime worker {process.pid} could not be reaped') from interrupted


@contextmanager
def _defer_sigint():
    """Own main-thread SIGINT for the complete child lifetime.

    No signal mask is changed or inherited by the child. Python dispatches signal
    handlers only in the main thread; other threads need no handler replacement.
    This protects OS SIGINT, not arbitrary exceptions injected into CPython internals.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = signal.getsignal(signal.SIGINT)
    if not callable(previous):
        yield  # Preserve SIG_IGN/SIG_DFL semantics without inventing errors.
        return
    pending = []

    def defer(signum, frame):
        if not pending:
            pending.append((signum, frame))

    error = None
    signal.signal(signal.SIGINT, defer)
    try:
        yield
    except BaseException as exc:
        error = exc
        raise
    finally:
        signal.signal(signal.SIGINT, previous)
        if pending:
            try:
                previous(*pending[0])
            except BaseException:
                # The handler must run even when the operation failed. Preserve
                # its side effects, but do not replace that original exception.
                if error is None:
                    raise


def run_bounded_capture_task(
    task: Callable[[], None], *, timeout_seconds: float, shutdown_grace: float = 1.0,
) -> WorkerResult:
    """Spawn a trusted picklable capture task and reap before returning a result.

    Synchronous supervisor, not an event-loop API or a service manager. Task must
    own its resources: no inherited DB pools, shared queues/locks or descendant
    processes. No task return value is transported. Normal return means completed;
    exceptions/SystemExit become failed without transmitting exception text.
    Startup counts against the deadline; shutdown may add two grace periods.
    shutdown_grace must be at least 0.01 seconds; even then OS scheduling can
    prevent timely reaping, which remains an explicit RuntimeError.
    Timeout means the child is still alive after the bounded join. A late parent
    observation cannot establish the exact exit time of an already finished child.
    OS process startup and uninterruptible kernel waits cannot be hard-bounded.
    Failure to reap raises, never reports successful cleanup. Cleanup defers
    escalation interruptions until reaping finishes; the original parent error
    takes precedence over a cleanup interruption after successful reaping.
    Main-thread callable SIGINT handlers are deferred across the entire child
    lifetime through handle close, then restored and invoked even after an error.
    Cancellation latency can therefore reach the task timeout plus shutdown;
    there is no immediate SIGINT cancellation promise. Signals coalesce to one
    callback. No blocked signal mask is inherited. SIGKILL/default SIGTERM cannot
    be recovered; non-callable SIG_DFL/SIG_IGN policies remain unchanged. The
    caller must not replace SIGINT policy during supervision.
    Forced termination skips child finally blocks: retain sources and reconcile
    .part/final files.
    Launch from an import-safe main guarded by if __name__ == '__main__'.
    """
    for value, maximum in ((timeout_seconds, 300), (shutdown_grace, 5)):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError('Worker deadlines must be finite positive numbers within limits')
    if shutdown_grace < 0.01:
        raise ValueError('Worker shutdown grace must be at least 0.01 seconds')
    # Install once, before a child can exist; no unprotected cleanup transition.
    with _defer_sigint():
        process = multiprocessing.get_context('spawn').Process(target=_execute, args=(task,), daemon=True)
        deadline = time.monotonic() + timeout_seconds
        original_error = None
        try:
            process.start()
            pid = process.pid
            process.join(max(0.0, deadline - time.monotonic()))
            timed_out = process.is_alive()
        except BaseException as exc:
            original_error = exc
            raise
        finally:
            cleanup_error = None
            if process.pid is not None:
                cleanup_error = _reap(process, shutdown_grace)
            exit_code = process.exitcode
            process.close()
            if cleanup_error is not None and original_error is None:
                raise cleanup_error
        status = 'timed_out' if timed_out else ('completed' if exit_code == 0 else 'failed')
        return WorkerResult(status, pid, exit_code)
