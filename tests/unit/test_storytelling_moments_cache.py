"""Regression tests for detect_moments module-level cache.

The 11 moment detectors fire 11 parallel DB queries + an objective-event
loader on every request. Story page typically triggers both /moments
and /narrative (which internally calls detect_moments(limit=1)) on the
same session — without caching we recompute the whole batch twice.

Cache is keyed by (session_date, limit) with TTL that adapts:
- today → 5 min (new rounds may still arrive)
- historical → 1 h (stable, bounded for retro-corrections)
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services.storytelling import moments as moments_module
from website.backend.services.storytelling.service import StorytellingService


@pytest.fixture(autouse=True)
def _clear_moments_cache():
    """Each test starts with an empty cache so cross-test state doesn't leak."""
    moments_module._MOMENTS_CACHE.clear()
    yield
    moments_module._MOMENTS_CACHE.clear()


def _service_with_stub_detectors():
    """Service whose detectors all return trivial fixture moments.

    We patch `_detect_moments_uncached` directly so we don't have to mock
    11 separate detectors + the objective-event loader. The cache wraps
    this method, so replacing it is the right seam for cache testing.
    """
    db = AsyncMock()
    svc = StorytellingService(db)
    call_count = {"n": 0}

    async def fake_uncached(sd, limit):
        call_count["n"] += 1
        return [
            {"type": "kill_streak", "impact_stars": 5, "time_ms": 1000},
            {"type": "multikill", "impact_stars": 4, "time_ms": 2000},
            {"type": "team_wipe", "impact_stars": 3, "time_ms": 3000},
        ][:limit]

    svc._detect_moments_uncached = fake_uncached
    return svc, call_count


@pytest.mark.asyncio
async def test_second_call_hits_cache():
    svc, calls = _service_with_stub_detectors()
    sd = date(2026, 4, 21) - timedelta(days=30)  # historical → long TTL

    first = await svc.detect_moments(sd, limit=10)
    second = await svc.detect_moments(sd, limit=10)

    assert calls["n"] == 1
    assert first == second


@pytest.mark.asyncio
async def test_different_limit_recomputes():
    """Cache key includes limit — limit=1 vs limit=10 are distinct entries."""
    svc, calls = _service_with_stub_detectors()
    sd = date(2026, 4, 21) - timedelta(days=30)

    await svc.detect_moments(sd, limit=10)
    await svc.detect_moments(sd, limit=1)
    await svc.detect_moments(sd, limit=10)  # cached
    await svc.detect_moments(sd, limit=1)   # cached

    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_ttl_expiry_recomputes():
    """After TTL passes, the next call re-runs the detectors."""
    svc, calls = _service_with_stub_detectors()
    sd = date(2026, 4, 21) - timedelta(days=30)

    await svc.detect_moments(sd, limit=10)
    # Force the cached entry to look stale (>1h for historical TTL).
    cached_list, _ = moments_module._MOMENTS_CACHE[(sd, 10)]
    moments_module._MOMENTS_CACHE[(sd, 10)] = (cached_list, time.time() - 4000)

    await svc.detect_moments(sd, limit=10)

    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_concurrent_callers_collapse_to_one_compute():
    """N coroutines all awaiting the same (sd, limit) should trigger
    exactly one underlying compute — the lock in _compute_locks guards
    the double-check pattern."""
    db = AsyncMock()
    svc = StorytellingService(db)
    call_count = {"n": 0}

    async def slow_uncached(sd, limit):
        call_count["n"] += 1
        await asyncio.sleep(0.01)
        return [{"type": "kill_streak", "impact_stars": 5, "time_ms": 1000}]

    svc._detect_moments_uncached = slow_uncached
    sd = date(2026, 4, 21) - timedelta(days=30)

    results = await asyncio.gather(
        *(svc.detect_moments(sd, limit=10) for _ in range(8))
    )

    assert call_count["n"] == 1
    # All callers get the same payload
    first = results[0]
    for r in results[1:]:
        assert r == first


@pytest.mark.asyncio
async def test_today_ttl_is_shorter_than_historical():
    today = date.today()
    yesterday = today - timedelta(days=1)
    assert moments_module._moments_cache_ttl(today) < moments_module._moments_cache_ttl(yesterday)


@pytest.mark.asyncio
async def test_lru_eviction_when_cache_full():
    """Oldest entry is evicted when cache exceeds max size."""
    svc, _ = _service_with_stub_detectors()
    original_max = moments_module._MOMENTS_CACHE_MAX
    moments_module._MOMENTS_CACHE_MAX = 3
    try:
        base = date(2026, 1, 1)
        await svc.detect_moments(base + timedelta(days=0), limit=10)
        await svc.detect_moments(base + timedelta(days=1), limit=10)
        await svc.detect_moments(base + timedelta(days=2), limit=10)
        assert len(moments_module._MOMENTS_CACHE) == 3
        # Adding a 4th evicts the oldest (day 0)
        await svc.detect_moments(base + timedelta(days=3), limit=10)
        assert len(moments_module._MOMENTS_CACHE) == 3
        assert (base + timedelta(days=0), 10) not in moments_module._MOMENTS_CACHE
    finally:
        moments_module._MOMENTS_CACHE_MAX = original_max
