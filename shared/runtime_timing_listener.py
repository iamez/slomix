"""Bounded six-exchange capture for an explicitly provisioned timing producer.

Requires persistent timing output and ordered bootstrap/stats-close/timing-close
for each half. This does not provision ET Lua VMs or infer missing-close success.
"""
from types import SimpleNamespace

from shared.runtime_failure_cleanup import CleanupOnError
from shared.runtime_match_listener import _accept, _listener, _timeout
from shared.runtime_timing_controller import RuntimeTimingController


def serve_timing_match(controller, socket_path, *, initial_readiness_wait=1800.0,
                       bootstrap_wait=1800.0, completion_wait=3600.0,
                       timing_wait=30.0, exchange_timeout=5.0, on_ready=None):
    """Own one listener/controller; retain all captured prefixes on any failure.

    A missing timing close terminates this strict attempt, retains claims/bytes
    and requires reconciliation. It does not establish failed stats import or
    justify deleting a played round. No auto-retry, service startup or source ACK.
    """
    _timeout(initial_readiness_wait, 3600)
    _timeout(bootstrap_wait, 3600)
    _timeout(completion_wait, 7200)
    _timeout(timing_wait, 300)
    _timeout(exchange_timeout, 10)
    if not isinstance(controller, RuntimeTimingController) or controller.state != 'ready':
        raise ValueError('Exclusively owned ready timing controller required')
    if on_ready is not None and not callable(on_ready):
        raise ValueError('Readiness observer must be callable')
    with CleanupOnError(controller.abort):
        with _listener(socket_path) as (server, verify):
            for half in (1, 2):
                controller.prepare_half()
                if half == 1 and on_ready is not None:
                    controller.check_waiting()
                    verify()
                    on_ready()
                wait = initial_readiness_wait if half == 1 else bootstrap_wait
                controller.bootstrap(_accept(server, verify, controller, wait), timeout=exchange_timeout)
                controller.complete(_accept(server, verify, controller, completion_wait), timeout=exchange_timeout)
                waiting = SimpleNamespace(check_waiting=lambda h=half: controller.check_timing_waiting(h))
                controller.complete_timing(half, _accept(server, verify, waiting, timing_wait),
                                           timeout=exchange_timeout)
                verify()
        return controller.captured_timing_match()
