"""Caller-owned proximity polling lifecycle; disabled unless explicitly enabled."""

import asyncio
import logging
import math
import time
from dataclasses import dataclass, replace
from pathlib import Path

from shared.proximity_errors import TRANSIENT_PROXIMITY_ERRORS
from shared.runtime_proximity_admission import _scope
from shared.runtime_proximity_cursor import process_proximity_checkpointed_batch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProximityWorkerState:
    status: str = 'disabled'
    last_success_monotonic: float | None = None
    last_batch_counts: tuple[tuple[str, int], ...] | None = None
    last_batch_exhausted: int | None = None
    error_type: str | None = None
    consecutive_failures: int = 0
    next_delay_seconds: float | None = None


class RuntimeProximityWorker:
    """Await run() in a caller-owned task, like RuntimeCacheWorker.

    resources_factory() provides an async context manager yielding (adapter,
    observer), exclusively owned for this batch and released before another is
    acquired. The factory owns connecting to the same authoritative primary,
    cleanup/rollback and discarding damaged connections. No credentials, service,
    connections or task are created by this class. No implicit environment opt-in.

    Async timeout includes acquisition/work/release but is COOPERATIVE: synchronous
    filesystem/parser work, cancellation-suppressing code and blocked kernel I/O
    cannot be interrupted here. This is NOT the hard-deadline deployment gate.
    Stop interrupts idle/backoff; active work finishes or hits that cooperative
    timeout. Caller cancellation propagates after context-manager cleanup.

    Always wait between batches, even full/committed/deferred ones; these are
    circular inventories, not a consumable queue. Transient connection/OSError/
    timeout failures use capped exponential backoff. Programming/schema errors
    fail visibly rather than loop forever. No full-database health claim:
    last_batch_* describes ONLY the latest selected batch, not the entire spool.
    Persisted per-generation retries/cursor survive restart; global failure count
    is in-memory and resets on process restart. Legacy handover remains external.
    """

    def __init__(self, root: Path, *, source_id: str, gametimes_dir: Path,
                 enabled: bool = False, allow_declared_mapping: bool = False,
                 batch_size: int = 16, max_entries: int = 4096,
                 poll_seconds: float = 5, attempt_timeout: float = 60,
                 retry_seconds: float = 5, max_retry_seconds: float = 300):
        _scope(root / ('0' * 32), source_id, '0' * 32)
        if type(allow_declared_mapping) is not bool:
            raise ValueError('Explicit declared mapping policy required')
        if type(enabled) is not bool:
            raise ValueError('enabled must be an explicit boolean')
        if type(batch_size) is not int or not 1 <= batch_size <= 32:
            raise ValueError('batch_size must be 1..32')
        if type(max_entries) is not int or not 1 <= max_entries <= 4096:
            raise ValueError('max_entries must be 1..4096')
        for value in (poll_seconds, attempt_timeout, retry_seconds, max_retry_seconds):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 3600:
                raise ValueError('Worker intervals must be finite positive numbers <=3600')
        if retry_seconds > max_retry_seconds:
            raise ValueError('retry_seconds must not exceed max_retry_seconds')
        self.root, self.source_id, self.gametimes_dir = root, source_id, gametimes_dir
        self.enabled = enabled
        self.allow_declared_mapping = allow_declared_mapping
        self.batch_size, self.max_entries = batch_size, max_entries
        self.poll_seconds, self.attempt_timeout = poll_seconds, attempt_timeout
        self.retry_seconds, self.max_retry_seconds = retry_seconds, max_retry_seconds
        self.state = ProximityWorkerState()
        self._running = False

    async def run(self, resources_factory, stop: asyncio.Event):
        if self._running:
            raise RuntimeError('Proximity worker already running')
        if not self.enabled:
            self.state = replace(self.state, status='disabled', error_type=None, next_delay_seconds=None)
            return
        mapping_options = {'allow_declared_mapping': True} if self.allow_declared_mapping else {}
        self._running = True
        self.state = replace(self.state, status='starting', error_type=None,
                             consecutive_failures=0, next_delay_seconds=None)
        try:
            while not stop.is_set():
                try:
                    async with asyncio.timeout(self.attempt_timeout):
                        async with resources_factory() as (adapter, observer):
                            result = await process_proximity_checkpointed_batch(
                                self.root, source_id=self.source_id, now=int(time.time()),
                                adapter=adapter, observer=observer, gametimes_dir=self.gametimes_dir,
                                batch_size=self.batch_size, max_entries=self.max_entries,
                                **mapping_options,
                            )
                except TRANSIENT_PROXIMITY_ERRORS as error:
                    failures = min(self.state.consecutive_failures + 1, 64)
                    delay = min(self.retry_seconds * 2 ** (failures - 1), self.max_retry_seconds)
                    self.state = replace(self.state, status='unavailable', error_type=type(error).__name__,
                                         consecutive_failures=failures, next_delay_seconds=delay)
                    logger.warning('Proximity batch unavailable (%s)', type(error).__name__)
                    await self._wait(stop, delay)
                    continue
                counts = dict.fromkeys(('committed', 'deferred', 'retry', 'reconcile'), 0)
                for item in result.items:
                    counts[item.result.action] += 1  # Unknown actions fail, never count as success.
                exhausted = sum(item.result.reason == 'exhausted' for item in result.items)
                status = ('attention' if counts['reconcile'] else
                          'waiting' if counts['deferred'] or counts['retry'] else 'idle')
                self.state = ProximityWorkerState(
                    status, time.monotonic(), tuple(counts.items()), exhausted,
                    None, 0, self.poll_seconds,
                )
                await self._wait(stop, self.poll_seconds)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.state = replace(self.state, status='failed', error_type=type(error).__name__,
                                 next_delay_seconds=None)
            raise
        finally:
            self._running = False
            if self.state.status != 'failed':
                self.state = replace(self.state, status='stopped', error_type=None, next_delay_seconds=None)

    async def _wait(self, stop, delay):
        try:
            await asyncio.wait_for(stop.wait(), timeout=delay)
        except TimeoutError:
            # A normal poll deadline requests the next batch; stop remains interruptible.
            pass
