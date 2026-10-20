"""One process-pinned match: dispatch, bootstrap, authenticated capture, R1 -> R2.

Synchronous host-side orchestration, never a game callback, scheduler or listener.
Caller owns process pin/listener lifecycle and supplies independently approved
roots and match allocation. No service control, process launch, DB or retries.
"""

import os
from contextlib import contextmanager
from threading import Lock

from shared.runtime_captured_match import CapturedMatch
from shared.runtime_failure_cleanup import CleanupOnError
from shared.runtime_host_bootstrap import bootstrap_round
from shared.runtime_host_capture import capture_closed_stats
from shared.runtime_host_completion import receive_stats_completion
from shared.runtime_identity_allocation import inspect_round_pair
from shared.runtime_process_authority import verify_process_epoch
from shared.runtime_stats_dispatch import _root_key, prepare_stats_dispatch


class RuntimeMatchController:
    """Sequential one-shot match driver; ambiguous failures require reconciliation.

    prepare_half returns the sole dispatch so the external adapter can provision
    its producer directory. bootstrap owns an accepted InitGame socket; complete
    owns an accepted writer-close socket and publishes into the bound private
    capture root. R2 cannot be prepared until R1 capture succeeds. COMPLETE means
    captured halves, NOT canonical import or Discord delivery.

    This local driver must run under the approved producer UID: it reserves 0700
    source directories, so running as the Discord user's different UID would
    make the game unable to write. Caller must map producer_spool to the actual
    ET homepath/game-dir gamestats/runtime-snapshots, not guess from a repository.
    Four roots must be private, distinct, non-nested and stable. Roots/process are
    rechecked on each operation. No reconstruction of in-memory success after a
    crash: persisted claims stop replay, they do not authorize automatic recovery.
    Invalid-order/concurrent calls close their supplied socket without disrupting
    an already active operation. An admitted operation failing at any stage makes
    this controller terminal. File/syscall latency is not bounded by IPC timeout.
    A trusted source must still enforce actual InitGame/half lifecycle; this class
    does not infer physical continuity from planned identities or timestamps.
    """

    def __init__(self, *, authority, host_authority, producer_spool, capture_root,
                 match_id, source_id, map_name, pin, epoch):
        if pin.identity.uid != os.getuid():
            raise ValueError('Local match controller must run as the approved producer UID')
        self._authority, self._host = authority, host_authority
        self._spool, self._capture = producer_spool, capture_root
        self._match, self._source, self._map = match_id, source_id, map_name
        self._pin, self._epoch = pin, epoch
        self._roots = (authority, host_authority, producer_spool, capture_root)
        self._keys = tuple(_root_key(root, match_id) for root in self._roots)
        paths = [root.resolve(strict=True) for root in self._roots]
        if (len({tuple(key) for key in self._keys}) != 4
                or any(a.is_relative_to(b) or b.is_relative_to(a)
                       for i, a in enumerate(paths) for b in paths[i + 1:])):
            raise ValueError('Controller requires four separate non-nested roots')
        inspect_round_pair(authority, match_id, expected_source=source_id)
        if epoch.source_id != source_id:
            raise ValueError('Controller source disagrees with process epoch')
        verify_process_epoch(host_authority, pin, epoch)
        self._state, self._half = 'ready', 1
        self._dispatch = self._accepted = self._previous = None
        self._captures = ()
        self._lock = Lock()

    @property
    def state(self):
        return self._state

    def abort(self):
        """Fence an external adapter failure; retain all claims and captured bytes.

        The sole listener owner calls this after accept/deadline/path failure.
        Never interrupt an in-flight operation or turn failure into a retry.
        """
        if not self._lock.acquire(blocking=False):
            raise ValueError('Controller operation is concurrent or out of order')
        try:
            self._state = 'failed'
        finally:
            self._lock.release()

    def _verify_context(self):
        if tuple(_root_key(root, self._match) for root in self._roots) != self._keys:
            raise ValueError('Controller root identity changed')
        verify_process_epoch(self._host, self._pin, self._epoch)

    def _mark_failed(self):
        self._state = 'failed'

    def check_waiting(self):
        """Revalidate pending IPC without consuming a dispatch or changing order."""
        if not self._lock.acquire(blocking=False):
            raise ValueError('Controller operation is concurrent or out of order')
        try:
            if self._state not in ('awaiting_bootstrap', 'awaiting_completion'):
                raise ValueError('Controller is not awaiting a connection')
            with CleanupOnError(self._mark_failed):
                self._verify_context()
        finally:
            self._lock.release()

    def captured_match(self):
        """Export both successes with dispatch identities, even after source exit.

        No process reattachment or disk recovery: only this live controller's
        completed operations authorize export. The game need not stay running
        during database work. Root identity is rechecked here and by the importer;
        bytes/manifests remain subject to the existing sealed-input checks.
        """
        if not self._lock.acquire(blocking=False):
            raise ValueError('Controller operation is concurrent or out of order')
        try:
            if self._state != 'complete' or len(self._captures) != 2:
                raise ValueError('Both successful captures required before import handoff')
            (first, first_identity), (second, second_identity) = self._captures
            result = CapturedMatch(first, second, first_identity, second_identity,
                                   tuple(self._keys[3]))
            result.verify()
            return result
        finally:
            self._lock.release()

    @contextmanager
    def _operation(self, required, connection=None):
        acquired = self._lock.acquire(blocking=False)
        started = False

        def mark_started_failed():
            if started:
                self._mark_failed()

        try:
            if not acquired or self._state != required:
                raise ValueError('Controller operation is concurrent or out of order')
            started = True
            self._state = 'busy'
            with CleanupOnError(mark_started_failed):
                self._verify_context()
                yield
        finally:
            try:
                with CleanupOnError(mark_started_failed):
                    if connection is not None:
                        connection.close()
            finally:
                if acquired:
                    self._lock.release()

    def prepare_half(self):
        with self._operation('ready'):
            self._dispatch = prepare_stats_dispatch(
                self._authority, self._spool, self._match, expected_source=self._source,
                map_name=self._map, half=self._half, previous=self._previous,
                capture_root=self._capture,
            )
            self._state = 'awaiting_bootstrap'
            return self._dispatch

    def bootstrap(self, connection, *, timeout=5.0):
        with self._operation('awaiting_bootstrap', connection):
            self._accepted = bootstrap_round(
                connection, self._host, self._pin, self._epoch,
                dispatch=self._dispatch, timeout=timeout,
            )
            self._state = 'awaiting_completion'
            return self._accepted

    def complete(self, connection, *, timeout=5.0):
        with self._operation('awaiting_completion', connection):
            completed = receive_stats_completion(
                connection, self._host, self._pin, self._epoch,
                accepted=self._accepted, timeout=timeout,
            )
            captured = capture_closed_stats(
                self._host, self._pin, self._epoch, accepted=self._accepted,
                completed=completed, source_directory=self._spool / self._dispatch.generation,
                capture_root=self._capture,
            )
            self._previous = captured.reference
            self._captures += ((captured, self._dispatch.identity),)
            if self._half == 1:
                self._half, self._state = 2, 'ready'
            else:
                self._state = 'complete'
            return captured
