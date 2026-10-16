"""Caller-owned team polling lifecycle; no service, pool or task startup."""

import asyncio
import logging
import math
import os
import time
from dataclasses import dataclass, replace

import asyncpg

from shared.runtime_team_batch import consume_team_page
from shared.runtime_team_consumer import team_consumer_enabled
from shared.runtime_team_discovery import TeamScanHint
from shared.team_write_guard import TeamWriteBusy

logger = logging.getLogger(__name__)
_RETRYABLE = (OSError, TimeoutError, TeamWriteBusy, asyncpg.PostgresConnectionError,
              asyncpg.CannotConnectNowError, asyncpg.SerializationError, asyncpg.DeadlockDetectedError)


def team_worker_enabled() -> bool:
    return (team_consumer_enabled()
            and os.getenv('RUNTIME_TEAM_WORKER_ENABLED', 'false').strip().lower() == 'true')


@dataclass(frozen=True)
class TeamWorkerState:
    """Last completed page counts, never totals or proof of current DB health.

    error_type records the latest failed attempt until a page succeeds. Stopping
    preserves it alongside any earlier successful page; it is not current health.
    """

    status: str = 'disabled'
    next_hint: TeamScanHint | None = None
    inspected: int = 0
    processed: int = 0
    pending: int = 0
    already_processed: int = 0
    last_success_monotonic: float | None = None
    error_type: str | None = None


class RuntimeTeamWorker:
    """Caller awaits run(factory, stop); each page owns one borrowed connection.

    Factory must return an async context manager with an exclusive native
    connection, no enclosing transaction, and cancellation-safe release. The
    attempt timeout includes acquire, page and release, but is cooperative;
    cancellation-resistant drivers/cleanup cannot be hard-bounded here.
    Stop interrupts idle/retry waits; active work finishes or times out. Caller
    may cancel run for earlier interruption. No tasks, pools or services started.
    Receipt-filtered discovery, not in-memory scheduling, establishes progress.
    Sweep fairness requires completed pages: persistent timeouts on the same
    pending page retain the hint and require batch-size/deadline tuning.
    """

    def __init__(self, *, batch_size=100, poll_seconds=5.0, attempt_timeout=10.0):
        if type(batch_size) is not int or not 1 <= batch_size <= 1000:
            raise ValueError('batch_size must be an integer from 1 to 1000')
        for value in (poll_seconds, attempt_timeout):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError('Worker intervals must be finite positive numbers')
        self.batch_size = batch_size
        self.poll_seconds = poll_seconds
        self.attempt_timeout = attempt_timeout
        self.state = TeamWorkerState()
        self._running = False

    async def run(self, connection_factory, stop: asyncio.Event):
        if self._running:
            raise RuntimeError('Team worker already running')
        if not team_worker_enabled():
            self.state = TeamWorkerState()
            return
        self._running = True
        # A new run starts a fresh sweep; a previous RAM hint is not durable.
        self.state = TeamWorkerState(status='starting')
        hint = None
        try:
            while not stop.is_set():
                if not team_worker_enabled():
                    self.state = replace(self.state, status='disabled', error_type=None)
                    return
                try:
                    async with asyncio.timeout(self.attempt_timeout):
                        async with connection_factory() as conn:
                            try:
                                result = await consume_team_page(conn, batch_size=self.batch_size, hint=hint)
                            except asyncpg.InterfaceError:
                                try:
                                    closed = conn.is_closed()
                                except asyncpg.InterfaceError:
                                    # Closing a pooled connection detaches its proxy;
                                    # even is_closed() then rejects access. Within
                                    # this owned acquisition it is unusable, so retry
                                    # from receipts with a fresh pool connection.
                                    if not isinstance(conn, asyncpg.pool.PoolConnectionProxy):
                                        raise
                                    closed = True
                                if closed:
                                    raise ConnectionError('Team connection closed') from None
                                raise
                except _RETRYABLE as error:
                    # Release can fail after commits; keep original hint too.
                    self.state = replace(self.state, status='unavailable', error_type=type(error).__name__)
                    logger.warning('Runtime team consumer unavailable (%s)', type(error).__name__)
                    await self._wait(stop)
                    continue
                # Publish scheduling progress only after successful release.
                hint = result.next_hint
                outcomes = [item.outcome.status for item in result.items]
                status = ('disabled' if result.status == 'disabled' else
                          'catching_up' if hint is not None else
                          'pending' if 'pending' in outcomes else 'idle')
                self.state = TeamWorkerState(
                    status=status, next_hint=hint, inspected=len(outcomes),
                    processed=outcomes.count('processed'), pending=outcomes.count('pending'),
                    already_processed=outcomes.count('already_processed'),
                    last_success_monotonic=time.monotonic(),
                )
                if result.status == 'disabled':
                    return
                if hint is not None:
                    await asyncio.sleep(0)  # Yield between pages, even with a full backlog.
                else:
                    # Pending rows recur forever; throttle at EVERY sweep wrap.
                    await self._wait(stop)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.state = replace(self.state, status='failed', error_type=type(error).__name__)
            raise
        finally:
            self._running = False
            if self.state.status not in ('disabled', 'failed'):
                self.state = replace(self.state, status='stopped')

    async def _wait(self, stop):
        try:
            await asyncio.wait_for(stop.wait(), timeout=self.poll_seconds)
        except TimeoutError:
            pass  # The polling interval elapsed; the next sweep may proceed.
