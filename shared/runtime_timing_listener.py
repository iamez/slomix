"""Independent stats and per-half timing channels; absent timing never blocks R2."""
from dataclasses import dataclass
from types import SimpleNamespace

from shared.runtime_captured_match import CapturedMatch
from shared.runtime_captured_timing_match import CapturedTimingMatch
from shared.runtime_failure_cleanup import CleanupOnError
from shared.runtime_match_listener import _accept, _listener, _timeout
from shared.runtime_timing_controller import RuntimeTimingController


@dataclass(frozen=True)
class TimingListenerResult:
    stats: CapturedMatch
    timing_match: CapturedTimingMatch | None
    timing_status: dict[int, str]


def serve_timing_match(controller, socket_path, *, timing_socket_paths,
                       initial_readiness_wait=1800.0, bootstrap_wait=1800.0,
                       completion_wait=3600.0, timing_wait=30.0,
                       exchange_timeout=5.0, on_ready=None):
    """Capture both stats halves before bounded independent timing admission.

    Provision all three paths before producer activation. Timing peers may send
    and close into their own bounded listener queues while stats are captured.
    The game process must remain live/pinned until timing authentication finishes.
    A missing timing connection stays pending and returns valid stats separately;
    no deletion, fabricated timing, source ACK or automatic retry occurs.
    """
    _timeout(initial_readiness_wait, 3600)
    _timeout(bootstrap_wait, 3600)
    _timeout(completion_wait, 7200)
    _timeout(timing_wait, 300)
    _timeout(exchange_timeout, 10)
    if not isinstance(controller, RuntimeTimingController) or controller.state != 'ready':
        raise ValueError('Exclusively owned ready timing controller required')
    if set(timing_socket_paths) != {1, 2} or len({socket_path, *timing_socket_paths.values()}) != 3:
        raise ValueError('Distinct stats and independently provisioned per-half timing sockets required')
    if on_ready is not None and not callable(on_ready):
        raise ValueError('Readiness observer must be callable')
    with CleanupOnError(controller.abort):
        with (_listener(socket_path) as (server, verify),
              _listener(timing_socket_paths[1]) as first_listener,
              _listener(timing_socket_paths[2]) as second_listener):
            for half in (1, 2):
                controller.prepare_half()
                if half == 1 and on_ready is not None:
                    controller.check_waiting()
                    verify()
                    on_ready()
                wait = initial_readiness_wait if half == 1 else bootstrap_wait
                controller.bootstrap(_accept(server, verify, controller, wait), timeout=exchange_timeout)
                controller.complete(_accept(server, verify, controller, completion_wait), timeout=exchange_timeout)
                verify()
            stats = controller.captured_match()
            for half, (timing_server, check) in enumerate((first_listener, second_listener), 1):
                waiting = SimpleNamespace(check_waiting=lambda h=half: controller.check_timing_waiting(h))
                try:
                    connection = _accept(timing_server, check, waiting, timing_wait)
                except TimeoutError:
                    continue  # No timing claim consumed; captured stats remain independently usable.
                try:
                    controller.complete_timing(half, connection, timeout=exchange_timeout)
                except (ValueError, OSError, EOFError):
                    # A consumed failed timing attempt cannot erase completed stats.
                    # Root/socket verification below still propagates integrity failures.
                    pass
                check()
            status = controller.timing_status()
            timed = controller.captured_timing_match() if all(v == 'captured' for v in status.values()) else None
        stats.verify()
        return TimingListenerResult(stats, timed, status)
