"""Deadline supervision for a single disposable, capture-only child process."""

import math
import multiprocessing
import time
from collections.abc import Callable
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
    try:
        if process.is_alive():
            process.terminate()
            process.join(grace)
    except BaseException as exc:
        interrupted = exc
    if process.is_alive():
        process.kill()
        deadline = time.monotonic() + grace
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                process.join(remaining)
            except BaseException as exc:
                if interrupted is None:
                    interrupted = exc
            if not process.is_alive():
                break
    if process.is_alive():
        raise RuntimeError(f'Owned runtime worker {process.pid} could not be reaped') from interrupted
    return interrupted


def run_bounded_capture_task(
    task: Callable[[], None], *, timeout_seconds: float, shutdown_grace: float = 1.0,
) -> WorkerResult:
    """Spawn a trusted picklable capture task and reap before returning a result.

    Synchronous supervisor, not an event-loop API or a service manager. Task must
    own its resources: no inherited DB pools, shared queues/locks or descendant
    processes. No task return value is transported. Normal return means completed;
    exceptions/SystemExit become failed without transmitting exception text.
    Startup counts against the deadline; shutdown may add two grace periods.
    Timeout means the child is still alive after the bounded join. A late parent
    observation cannot establish the exact exit time of an already finished child.
    OS process startup and uninterruptible kernel waits cannot be hard-bounded.
    Failure to reap raises, never reports successful cleanup. Cleanup defers
    join interruptions until reaping finishes; the original parent error
    takes precedence over a cleanup interruption after successful reaping.
    Forced termination skips child finally blocks: retain sources and reconcile
    .part/final files.
    Launch from an import-safe main guarded by if __name__ == '__main__'.
    """
    for value, maximum in ((timeout_seconds, 300), (shutdown_grace, 5)):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError('Worker deadlines must be finite positive numbers within limits')
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
