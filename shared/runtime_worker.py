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


def _reap(process, grace: float) -> None:
    """Stop only our child, escalate if needed, and observe its exit."""
    if process.is_alive():
        process.terminate()
        process.join(grace)
    if process.is_alive():
        process.kill()
        process.join(grace)
    if process.is_alive():
        raise RuntimeError(f'Owned runtime worker {process.pid} could not be reaped')


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
    Failure to reap raises, never reports successful cleanup. Forced termination
    skips child finally blocks: retain sources and reconcile .part/final files.
    Launch from an import-safe main guarded by if __name__ == '__main__'.
    """
    for value, maximum in ((timeout_seconds, 300), (shutdown_grace, 5)):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError('Worker deadlines must be finite positive numbers within limits')
    process = multiprocessing.get_context('spawn').Process(target=_execute, args=(task,), daemon=True)
    deadline = time.monotonic() + timeout_seconds
    try:
        process.start()
        pid = process.pid
        process.join(max(0.0, deadline - time.monotonic()))
        timed_out = process.is_alive()
    finally:
        if process.pid is not None:
            _reap(process, shutdown_grace)
        exit_code = process.exitcode
        process.close()
    status = 'timed_out' if timed_out else ('completed' if exit_code == 0 else 'failed')
    return WorkerResult(status, pid, exit_code)
