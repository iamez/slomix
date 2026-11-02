"""Serial isolated batches, interruptible pacing and explicit parent signal policy."""

import math
import signal
import threading

from shared.runtime_cache_main import emit_status
from shared.runtime_proximity_isolation import run_bounded_proximity_batch


def supervise(config, stop, *, runner=None, reporter=emit_status,
              timeout_seconds=60, shutdown_grace=1, poll_seconds=5,
              retry_seconds=5, max_retry_seconds=300):
    """Main-thread synchronous loop; at most one owned child, no parent DB pool.

    runner returns only AFTER child reaping. Exceptions (including inability to
    reap) abort the supervisor, never launch another child. Failed/timed-out child
    outcomes are unknown DB outcomes and use capped exponential backoff; completed
    means batch process completed, not all inputs imported. Child JSON carries
    last-batch counts separately. Always poll-wait, even on completed full batches.

    Stop interrupts idle/backoff. During a child, stop requests drain until the
    fixed batch deadline + up to two shutdown graces; no new batch follows. Parent
    must stay alive until reaping. Service stop timeout must exceed this budget
    with measured startup/scheduling margin; SIGKILL/kernel uninterruptible I/O
    cannot be made safe by Python. Backoff state is RAM-only: outer service restart
    rate limits still required. No service actions, inputs removed or DB rollback
    assumptions. Config must come from the guarded DEV reader at process entry.
    """
    for value, limit in ((timeout_seconds, 300), (shutdown_grace, 5), (poll_seconds, 3600),
                         (retry_seconds, 3600), (max_retry_seconds, 3600)):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= limit:
            raise ValueError('Supervisor intervals must be finite positive bounded numbers')
    if shutdown_grace < 0.01 or retry_seconds > max_retry_seconds:
        raise ValueError('Invalid supervisor grace or retry interval order')
    runner = runner or run_bounded_proximity_batch
    failures = 0
    reporter(dict(component='runtime_proximity_supervisor', status='starting'))
    while not stop.is_set():
        reporter(dict(component='runtime_proximity_supervisor', status='batch_running'))
        result = runner(config, timeout_seconds=timeout_seconds, shutdown_grace=shutdown_grace)
        if result.status == 'completed':
            failures = 0
            delay = poll_seconds
        elif result.status in ('failed', 'timed_out'):
            failures = min(failures + 1, 64)
            delay = min(retry_seconds * 2 ** (failures - 1), max_retry_seconds)
        else:
            raise RuntimeError('Unknown isolated batch process outcome')
        reporter(dict(component='runtime_proximity_supervisor', status=result.status,
                      consecutive_failures=failures, next_delay_seconds=None if stop.is_set() else delay))
        stop.wait(delay)
    reporter(dict(component='runtime_proximity_supervisor', status='stopped'))


def supervise_with_signals(config, **kwargs):
    """Own parent SIGTERM/SIGINT handlers only until all children are reaped."""
    stop = threading.Event()
    previous = {}

    def request_stop(_signum, _frame):
        stop.set()

    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, request_stop)
        supervise(config, stop, **kwargs)
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
