"""Default-off DEV supervisor entrypoint; no dotenv or service activation."""

import os
import time

from shared.runtime_cache_main import emit_status, serve  # noqa: F401 -- compatibility for lifecycle proofs.
from shared.runtime_proximity_config import ProximityProcessConfig
from shared.runtime_proximity_supervisor import supervise_with_signals
from shared.runtime_proximity_worker import ProximityWorkerState


def report(state):
    """Last selected batch only, not global spool/producer/DB health."""
    age = None if state.last_success_monotonic is None else max(0, time.monotonic() - state.last_success_monotonic)
    emit_status(dict(component='runtime_proximity', status=state.status,
                     last_batch_counts=None if state.last_batch_counts is None else dict(state.last_batch_counts),
                     last_batch_exhausted=state.last_batch_exhausted, last_success_age_seconds=age,
                     consecutive_failures=state.consecutive_failures,
                     next_delay_seconds=state.next_delay_seconds, error_type=state.error_type))


def run():
    if os.getenv('RUNTIME_PROXIMITY_WORKER_ENABLED') != 'true':
        report(ProximityWorkerState())
        return
    config = ProximityProcessConfig.from_environment()
    supervise_with_signals(config)


def main():
    try:
        run()
    except Exception as error:
        emit_status(dict(component='runtime_proximity', status='failed', error_type=type(error).__name__))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
