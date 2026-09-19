"""Caller-owned durable polling driver, independent of Discord and HTTP startup."""

import asyncio
import logging
import math
import os
import time
from dataclasses import dataclass, replace

import asyncpg

from shared.runtime_cache_consumer import consume_http_cache_events
from shared.runtime_events import event_stream_enabled

logger = logging.getLogger(__name__)


def cache_worker_enabled():
    return event_stream_enabled() and all(
        os.getenv(flag, "false").strip().lower() == "true"
        for flag in ("RUNTIME_HTTP_CACHE_EVENTS_ENABLED", "RUNTIME_HTTP_CACHE_WORKER_ENABLED")
    )


@dataclass(frozen=True)
class CacheWorkerState:
    status: str = "disabled"
    generation: int | None = None
    unsupported_pending: int | None = None
    last_success_monotonic: float | None = None
    error_type: str | None = None


class RuntimeCacheWorker:
    """Await run() in a caller-owned task; this class never starts a task itself.

    connection_factory returns an async context manager for a native PostgreSQL
    connection. Every batch reacquires/releases; receipts, not RAM, resume work.
    stop interrupts idle/backoff waits; active work has a timeout and can also be
    cancelled by the caller. No NOTIFY required. Health is this consumer only.
    """

    def __init__(self, *, batch_size=100, poll_seconds=5.0, attempt_timeout=10.0):
        if type(batch_size) is not int or not 1 <= batch_size <= 1000:
            raise ValueError("batch_size must be an integer from 1 to 1000")
        for value in (poll_seconds, attempt_timeout):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError("Worker intervals must be finite positive numbers")
        self.batch_size = batch_size
        self.poll_seconds = poll_seconds
        self.attempt_timeout = attempt_timeout
        self.state = CacheWorkerState()
        self._running = False

    async def run(self, connection_factory, stop: asyncio.Event):
        if self._running:
            raise RuntimeError("Cache worker already running")
        if not cache_worker_enabled():
            self.state = replace(self.state, status="disabled", error_type=None)
            return
        self._running = True
        self.state = replace(self.state, status="starting", error_type=None)
        try:
            while not stop.is_set():
                if not cache_worker_enabled():
                    self.state = replace(self.state, status="disabled")
                    return
                try:
                    async with asyncio.timeout(self.attempt_timeout):
                        async with connection_factory() as conn:
                            try:
                                result = await consume_http_cache_events(conn, batch_size=self.batch_size)
                            except asyncpg.InterfaceError:
                                # Only a closed native connection is retryable;
                                # other interface errors indicate misuse.
                                if conn.is_closed():
                                    raise ConnectionError("Runtime cache connection closed") from None
                                raise
                except (asyncpg.PostgresError, OSError, TimeoutError) as error:
                    self.state = replace(self.state, status="unavailable", error_type=type(error).__name__)
                    logger.warning("Runtime cache consumer unavailable (%s)", type(error).__name__)
                    await self._wait(stop)
                    continue
                if result.status == "disabled":
                    self.state = replace(self.state, status="disabled")
                    return
                status = "unsupported" if result.unsupported_pending else (
                    "catching_up" if result.processed == self.batch_size else "idle"
                )
                self.state = CacheWorkerState(
                    status, result.generation, result.unsupported_pending, time.monotonic(), None,
                )
                if result.processed == self.batch_size:
                    await asyncio.sleep(0)  # Yield even on a continuously full backlog.
                else:
                    await self._wait(stop)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.state = replace(self.state, status="failed", error_type=type(error).__name__)
            raise
        finally:
            self._running = False
            if self.state.status not in ("disabled", "failed"):
                self.state = replace(self.state, status="stopped")

    async def _wait(self, stop):
        try:
            await asyncio.wait_for(stop.wait(), timeout=self.poll_seconds)
        except TimeoutError:
            pass  # Periodic durable scan, including without any notification.
