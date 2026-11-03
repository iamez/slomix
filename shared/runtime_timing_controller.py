"""Opt-in timing extension to the existing sequential stats controller."""
from shared.runtime_host_timing_completion import receive_timing_completion
from shared.runtime_match_controller import RuntimeMatchController
from shared.runtime_stats_dispatch import _root_key
from shared.runtime_timing_capture import capture_closed_timing
from shared.runtime_timing_completion import TimingCompletion


class RuntimeTimingController(RuntimeMatchController):
    """Provision all timing expectations before accepting any peer message.

    Timing failure consumes only that timing attempt. Stats capture stays valid;
    missing timing prevents export of a full handoff, not stats-only import.
    """

    def __init__(self, *, timing_capture_root, timing_filenames, **kwargs):
        super().__init__(**kwargs)
        if set(timing_filenames) != {1, 2}:
            raise ValueError('Both independently expected timing basenames required')
        self._timing_names = dict(timing_filenames)
        for name in self._timing_names.values():
            TimingCompletion('a' * 32, name, 1).encode()
        path = timing_capture_root.resolve(strict=True)
        if any(path.is_relative_to(root.resolve(strict=True))
               or root.resolve(strict=True).is_relative_to(path) for root in self._roots):
            raise ValueError('Timing capture root must be separate from all existing roots')
        self._roots += (timing_capture_root,)
        self._keys += (_root_key(timing_capture_root, self._match),)
        self._timing_root = timing_capture_root
        self._timing_accepted = {}
        self._timing_attempted = set()
        self._timings = {}

    def _record_bootstrap(self, accepted):
        # Invoked under the base controller lock, before publishing ready state.
        half = accepted.delivery.dispatch.identity.round_number
        self._timing_accepted[half] = accepted

    def complete_timing(self, half, connection, *, timeout=5.0):
        acquired = self._lock.acquire(blocking=False)
        close_attempted = False
        try:
            if (not acquired or self._state in ('busy', 'failed')
                    or type(half) is not int or half not in self._timing_accepted
                    or half in self._timing_attempted):
                raise ValueError('Timing operation is concurrent, unavailable or already attempted')
            self._verify_context()
            accepted = self._timing_accepted[half]
            self._timing_attempted.add(half)
            completed = receive_timing_completion(connection, self._host, self._pin, self._epoch,
                accepted=accepted, expected_filename=self._timing_names[half], timeout=timeout)
            result = capture_closed_timing(self._host, self._pin, self._epoch,
                accepted=accepted, completed=completed, expected_filename=self._timing_names[half],
                source_directory=self._spool / accepted.delivery.dispatch.generation,
                capture_root=self._timing_root)
            self._verify_context()
            close_attempted = True
            connection.close()
            self._timings[half] = result
            return result
        finally:
            try:
                if not close_attempted:
                    connection.close()
            finally:
                if acquired:
                    self._lock.release()

    def timing_status(self):
        """Bounded diagnostic state; no file discovery or recovery adoption."""
        return {half: ('captured' if half in self._timings else
                       'failed' if half in self._timing_attempted else 'pending') for half in (1, 2)}

    def captured_timing_match(self):
        """Export successful captures only; missing timing stays explicit/pending."""
        from shared.runtime_captured_timing_match import CapturedTimingMatch

        stats = self.captured_match()
        if not self._lock.acquire(blocking=False):
            raise ValueError('Controller operation is concurrent')
        try:
            if set(self._timings) != {1, 2}:
                raise ValueError('Both successful timing captures required')
            result = CapturedTimingMatch(stats, (self._timings[1], self._timings[2]),
                                        tuple(self._keys[4]))
            result.verify()
            return result
        finally:
            self._lock.release()
