"""Tests for WebhookEventQueue (dedup + producer/consumer).

Pins the 2026-04-22 restructure that moves STATS_READY processing from
fire-and-forget `asyncio.create_task()` into a bounded queue with a
single dedicated worker. Goals:

- Dedup on `(map, round_number, round_end_unix)` — Lua retries after a
  Discord blip collapse to one fetch.
- Queue-full drops record a reason and drop the overflow (was:
  `_stats_ready_rate_limit` dropped silently).
- Worker exceptions do not kill the loop and clear dedup for retry.
- Graceful shutdown drains the queue before exiting.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from bot.services.webhook_event_queue import WebhookEventQueue, _dedup_key


def _meta(map_name="te_escape2", rn=1, end=1772746382) -> dict:
    return {
        "map_name": map_name,
        "round_number": rn,
        "round_end_unix": end,
    }


def test_dedup_key_is_deterministic():
    k1 = _dedup_key(_meta())
    k2 = _dedup_key(_meta())
    assert k1 == k2
    k3 = _dedup_key(_meta(end=1772746999))
    assert k1 != k3


@pytest.mark.asyncio
async def test_enqueue_accepts_new_key():
    q = WebhookEventQueue(bot=None, handler=AsyncMock())
    accepted, reason = q.enqueue(_meta(), message=object())
    assert accepted is True
    assert reason == "ok"
    assert q.stats()["enqueued"] == 1


@pytest.mark.asyncio
async def test_enqueue_rejects_duplicate():
    q = WebhookEventQueue(bot=None, handler=AsyncMock())
    msg = object()
    first, _ = q.enqueue(_meta(), msg)
    second, reason = q.enqueue(_meta(), msg)
    assert first is True
    assert second is False
    assert reason == "duplicate"
    assert q.stats()["deduped"] == 1


@pytest.mark.asyncio
async def test_enqueue_rejects_when_full():
    q = WebhookEventQueue(bot=None, handler=AsyncMock(), maxsize=2)
    q.enqueue(_meta(end=1), object())
    q.enqueue(_meta(end=2), object())
    accepted, reason = q.enqueue(_meta(end=3), object())
    assert accepted is False
    assert reason == "queue_full"
    assert q.stats()["dropped_full"] == 1


@pytest.mark.asyncio
async def test_worker_consumes_enqueued_item():
    handler = AsyncMock()
    q = WebhookEventQueue(bot=None, handler=handler)
    msg = object()
    q.enqueue(_meta(), msg)
    q.start()
    # Give the worker time to drain
    await asyncio.sleep(0.1)
    await q.stop(timeout=2.0)
    handler.assert_awaited()
    call_args = handler.await_args
    assert call_args.args[0]["map_name"] == "te_escape2"
    assert call_args.args[1] is msg
    assert q.stats()["processed"] >= 1


@pytest.mark.asyncio
async def test_worker_isolates_handler_failure():
    """Handler raising must not kill the worker loop."""
    handler = AsyncMock(side_effect=[RuntimeError("boom"), None])
    q = WebhookEventQueue(bot=None, handler=handler)
    q.enqueue(_meta(end=1), object())
    q.enqueue(_meta(end=2), object())
    q.start()
    await asyncio.sleep(0.15)
    await q.stop(timeout=2.0)
    assert q.stats()["handler_failures"] == 1
    assert q.stats()["processed"] == 1
    assert handler.await_count == 2


@pytest.mark.asyncio
async def test_dedup_ttl_expires():
    """After the TTL passes, the same key can be enqueued again."""
    q = WebhookEventQueue(bot=None, handler=AsyncMock(), dedup_ttl_seconds=0)
    q.enqueue(_meta(), object())
    # TTL=0 means every subsequent call prunes its own entry first.
    await asyncio.sleep(0.001)
    accepted, reason = q.enqueue(_meta(), object())
    assert accepted is True
    assert reason == "ok"


@pytest.mark.asyncio
async def test_stop_without_start_is_safe():
    q = WebhookEventQueue(bot=None, handler=AsyncMock())
    await q.stop(timeout=1.0)  # should not raise


@pytest.mark.asyncio
async def test_start_is_idempotent():
    handler = AsyncMock()
    q = WebhookEventQueue(bot=None, handler=handler)
    q.start()
    q.start()  # second call should be a no-op
    await q.stop(timeout=2.0)


@pytest.mark.asyncio
async def test_stop_drains_pending_items():
    """Graceful shutdown must finish the in-memory queue before exiting."""
    processed: list[str] = []

    async def slow_handler(metadata, _message):
        await asyncio.sleep(0.02)
        processed.append(metadata["map_name"])

    q = WebhookEventQueue(bot=None, handler=slow_handler)
    q.start()
    # Fill with 5 items, then request stop while the worker is mid-drain.
    for i in range(5):
        q.enqueue(_meta(map_name=f"map{i}"), object())
    await asyncio.sleep(0.005)  # let worker grab the first one
    await q.stop(timeout=5.0)
    assert len(processed) == 5


@pytest.mark.asyncio
async def test_enqueue_rejects_after_shutdown():
    """Once `stop()` has set the shutdown flag, further enqueues must
    be refused — otherwise a webhook handler racing with bot.close()
    would park an item in the queue AFTER the worker has exited, and
    the item would be silently lost on DB shutdown."""
    q = WebhookEventQueue(bot=None, handler=AsyncMock())
    q.start()
    await q.stop(timeout=2.0)
    accepted, reason = q.enqueue(_meta(), object())
    assert accepted is False
    assert reason == "shutting_down"
    assert q.stats().get("dropped_shutdown", 0) == 1


@pytest.mark.asyncio
async def test_handler_failure_clears_dedup_for_retry():
    """A handler exception must NOT lock the round out of a retry — the
    dedup key is cleared so the next Lua retry within the TTL can go
    through instead of being silently rejected."""
    calls: list[int] = []

    async def flaky_handler(_metadata, _message):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        # 2nd call succeeds

    q = WebhookEventQueue(bot=None, handler=flaky_handler)
    q.start()
    accepted_first, _ = q.enqueue(_meta(), object())
    assert accepted_first is True
    await asyncio.sleep(0.05)  # let the failure process
    # Same key should NOT be dedup-rejected — failure cleared the entry.
    accepted_retry, reason = q.enqueue(_meta(), object())
    assert accepted_retry is True, f"expected retry accepted after failure, got {reason}"
    await asyncio.sleep(0.05)
    await q.stop(timeout=2.0)
    assert q.stats()["handler_failures"] == 1
    assert q.stats()["processed"] == 1
    assert len(calls) == 2
