"""One synchronous supervised SSH attempt with separate observed spool state."""

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from shared.runtime_spool import inspect_published_stats_file
from shared.runtime_ssh_capture import SSHCaptureTask
from shared.runtime_worker import WorkerResult, run_bounded_capture_task


@dataclass(frozen=True)
class SupervisedCaptureResult:
    """Content observation and optional child outcome, neither an import receipt."""

    content: Literal['missing', 'match', 'conflict']
    worker: WorkerResult | None


def capture_ssh_once(
    task: SSHCaptureTask, *, timeout_seconds: float, shutdown_grace: float = 1.0,
) -> SupervisedCaptureResult:
    """Skip existing content; otherwise reap capture child, then inspect again.

    Requires a stable private immutable spool and trusted source size/digest.
    Matching content is not fsync durability or database acknowledgement. Conflict
    never overwrites; missing after failure is retryable by caller policy. A match
    after worker failure/timeout preserves both facts, not a successful worker.
    Partial files are ignored and retained, not cleaned. No loops or source ack.

    Local inspection is byte-bounded but NOT within the child timeout. Run on a
    dedicated synchronous supervisor, not an event loop; underlying filesystem
    waits can block. Inspection, spawn and parent interruption errors propagate.
    """
    def inspect():
        return inspect_published_stats_file(
            task.directory, PurePosixPath(task.remote_path).name,
            expected_size=task.expected_size, expected_sha256=task.expected_sha256,
            max_bytes=task.max_bytes,
        )

    content = inspect()
    if content != 'missing':
        return SupervisedCaptureResult(content, None)
    worker = run_bounded_capture_task(
        task, timeout_seconds=timeout_seconds, shutdown_grace=shutdown_grace,
    )
    return SupervisedCaptureResult(inspect(), worker)
