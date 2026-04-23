"""Producer/consumer queue for Lua STATS_READY webhook events.

Replaces the old fire-and-forget `asyncio.create_task(_process_...)`
pattern on every webhook. With the queue:

- Webhook receive side does parse + enqueue only (fast, <10 ms). Task
  spawned by `_safe_create_task` still returns quickly — no change to
  Discord gateway responsiveness — but we no longer fan out N parallel
  SSH fetches when webhooks burst.
- A single dedicated worker coroutine drains the queue and processes
  rounds sequentially: fetch stats → store Lua → delete webhook msg.
  Sequential ordering prevents SSH overload and makes intra-second
  STATS_READY bursts deterministic.
- Dedup on `(map, round_number, round_end_unix)` with a short TTL —
  a Lua retry after a Discord blip hits the dedup set and skips the
  redundant fetch instead of racing with the in-flight one.

Future: per-server workers once we scale past one game server, and a
Redis- or DB-backed queue once restart survivability matters. This
in-process asyncio.Queue is the minimal safe step for today's single
server.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from bot.logging_config import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("bot.webhook_queue")

# Dedup TTL is tight on purpose: Lua's realistic retry window after a
# Discord blip is seconds, not minutes. A long TTL widens the lockout if
# a round ever gets stuck in a "failed but not raised" state. Combined
# with handler-raises-on-soft-fail, 2 min is defense-in-depth.
DEDUP_TTL_SECONDS = 120
DEFAULT_QUEUE_SIZE = 50   # generous headroom; peak is ~1 webhook / 3 min today


@dataclass
class QueuedRound:
    """One pending STATS_READY round waiting for the worker."""

    metadata: dict
    message: Any  # discord.Message — kept as Any so tests don't need discord.py
    received_at: float = field(default_factory=time.time)


def _dedup_key(metadata: dict) -> str | None:
    """Key that uniquely identifies a Lua webhook event.

    Round-end unix timestamp is the ground truth — two webhooks with the
    same (map, round_number, round_end_unix) can only come from a Lua
    retry of the same real-world round, so they must collapse.

    Returns None when `round_end_unix` is missing or zero: that means
    we have no reliable third component, and collapsing every such
    payload to `map:round:0` would let a legitimate later round of the
    same map/number get rejected as a duplicate. The caller must treat
    None as "skip dedup for this one" and let it through.
    """
    end_unix = int(metadata.get('round_end_unix', 0) or 0)
    if end_unix <= 0:
        return None
    return (
        f"{metadata.get('map_name', 'unknown')}:"
        f"{metadata.get('round_number', 0)}:"
        f"{end_unix}"
    )


class WebhookEventQueue:
    """Bounded queue + single worker for STATS_READY webhook processing.

    Usage:
        queue = WebhookEventQueue(bot, handler=bot._process_stats_ready_round)
        queue.start()
        ...
        queue.enqueue(metadata, message)   # from webhook receive
        ...
        await queue.stop()                 # on bot shutdown
    """

    def __init__(
        self,
        bot,
        handler: Callable[[dict, Any], Awaitable[None]],
        maxsize: int = DEFAULT_QUEUE_SIZE,
        dedup_ttl_seconds: int = DEDUP_TTL_SECONDS,
    ):
        self._bot = bot
        self._handler = handler
        self._q: asyncio.Queue[QueuedRound] = asyncio.Queue(maxsize=maxsize)
        self._seen: dict[str, float] = {}
        self._dedup_ttl = dedup_ttl_seconds
        self._worker_task: asyncio.Task | None = None
        self._shutdown = asyncio.Event()
        self._stats = {
            "enqueued": 0,
            "deduped": 0,
            "dropped_full": 0,
            "processed": 0,
            "handler_failures": 0,
        }

    # ------------------------------------------------------------------
    # Producer side
    # ------------------------------------------------------------------

    def enqueue(self, metadata: dict, message) -> tuple[bool, str]:
        """Try to enqueue one round. Returns (accepted, reason).

        `reason` is "ok" / "duplicate" / "queue_full" / "shutting_down".
        Producer side logs appropriately and does NOT raise on overflow.

        A shutdown-in-progress refusal is important: without it, webhook
        handlers that are mid-flight when `stop()` fires can still
        `enqueue()` successfully AFTER the worker has exited, leaving
        the item stranded in memory and silently lost on bot close.
        """
        if self._shutdown.is_set():
            self._stats["dropped_shutdown"] = self._stats.get("dropped_shutdown", 0) + 1
            return (False, "shutting_down")
        self._prune_seen()
        key = _dedup_key(metadata)
        if key is not None and key in self._seen:
            self._stats["deduped"] += 1
            return (False, "duplicate")
        try:
            self._q.put_nowait(QueuedRound(metadata=metadata, message=message))
        except asyncio.QueueFull:
            self._stats["dropped_full"] += 1
            return (False, "queue_full")
        if key is not None:
            self._seen[key] = time.monotonic() + self._dedup_ttl
        self._stats["enqueued"] += 1
        return (True, "ok")

    def _prune_seen(self) -> None:
        now = time.monotonic()
        # Prune lazily on every enqueue. For dozens of entries / 10 min
        # this is cheap; if the cache ever grows it self-heals on the
        # next prune cycle.
        expired = [k for k, exp in self._seen.items() if exp <= now]
        for k in expired:
            self._seen.pop(k, None)

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._worker_task is not None and not self._worker_task.done():
            return
        self._shutdown.clear()
        self._worker_task = asyncio.create_task(
            self._worker_loop(), name="webhook_event_queue_worker"
        )
        logger.info("webhook event queue worker started (maxsize=%d)", self._q.maxsize)

    async def stop(self, timeout: float = 10.0) -> None:
        """Request shutdown and wait for the worker to drain + exit.

        The worker loop keeps consuming while the queue has items even
        after `_shutdown` is set, so pending STATS_READY events aren't
        lost on a graceful restart. If the timeout fires the worker is
        cancelled as a last resort.
        """
        self._shutdown.set()
        task = self._worker_task
        if task is None:
            return
        try:
            await asyncio.wait_for(task, timeout=timeout)
        except (asyncio.TimeoutError, TimeoutError):  # noqa: UP041 — Py 3.10 compat
            logger.warning(
                "webhook event queue worker did not drain within %ss (%d items left) — cancelling",
                timeout, self._q.qsize(),
            )
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                # Expected — we just cancelled it.
                pass
            except Exception:  # noqa: BLE001 — already logged inside worker loop
                logger.exception("webhook queue worker raised during cancel")
        finally:
            self._worker_task = None

    async def _worker_loop(self) -> None:
        # Drain-on-stop: keep consuming while the queue has items even
        # after shutdown is requested, so a graceful restart doesn't
        # drop STATS_READY events that already made it into the queue.
        while True:
            if self._shutdown.is_set() and self._q.empty():
                break
            try:
                item = await asyncio.wait_for(self._q.get(), timeout=1.0)
            except (asyncio.TimeoutError, TimeoutError):  # noqa: UP041 — Py 3.10 compat
                continue
            key = _dedup_key(item.metadata)
            try:
                await self._handler(item.metadata, item.message)
                self._stats["processed"] += 1
            except Exception:
                # Handler failure: drop the dedup entry so the next Lua
                # retry for this round is allowed through. Keeping the
                # entry would lock the round out of recovery until the
                # TTL expires.
                self._stats["handler_failures"] += 1
                if key is not None:
                    self._seen.pop(key, None)
                logger.exception(
                    "webhook queue handler raised for %s — dedup cleared, continuing",
                    key,
                )
            finally:
                self._q.task_done()

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, int]:
        """Snapshot of counters. Cheap, safe to call from diagnostics."""
        return {**self._stats, "queue_depth": self._q.qsize(), "seen_keys": len(self._seen)}
