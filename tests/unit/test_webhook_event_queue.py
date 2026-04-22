"""Tests for WebhookEventQueue (dedup + producer/consumer).

Pins the 2026-04-22 restructure that moves STATS_READY processing from
fire-and-forget `asyncio.create_task()` into a bounded queue with a
single dedicated worker. Goals:

- Dedup on `(map, round_number, round_end_unix)` — Lua retries after a
  Discord blip collapse to one fetch.
- Queue-full drops record a reason and drop the overflow (was:
  `_stats_ready_rate_limit` dropped silently).
- Worker exceptions do not kill the loop.
- Graceful shutdown drains cleanly.
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
