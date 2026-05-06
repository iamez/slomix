"""Tests for MemoryCacheBackend — in-process API response cache.

The cache backend powers the website's `/api/*` response caching. A
regression silently:

- Returns expired entries → users see stale data.
- get() doesn't clean up expired entries → memory leak.
- invalidate_all() doesn't bump namespace → old keys still served.
- Concurrent writes race → entries lost.

`MemoryCacheBackend` is testable without Redis. The Redis backend is
pure orchestration around the `Redis.from_url()` client and skipped
in unit tests.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from website.backend.services.http_cache_backend import MemoryCacheBackend


@pytest.fixture
def cache():
    return MemoryCacheBackend()


# ---------------------------------------------------------------------------
# get / set — basic round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_none_for_missing_key(cache):
    """Cold cache → None."""
    assert await cache.get("ns1", "missing-key") is None


@pytest.mark.asyncio
async def test_set_then_get_round_trip(cache):
    """Standard set+get returns the same value."""
    value = {"player": "alice", "kills": 10}
    await cache.set("ns1", "player_alice", value, ttl=60)
    out = await cache.get("ns1", "player_alice")
    assert out == value


@pytest.mark.asyncio
async def test_get_serialises_via_json(cache):
    """Stored payload is JSON-encoded — only JSON-serialisable values
    round-trip cleanly. Pin the contract so a regression that swaps
    to pickle doesn't change the security surface."""
    value = {"a": [1, 2, 3], "b": {"c": "d"}, "e": None, "f": True}
    await cache.set("ns1", "k", value, ttl=60)
    out = await cache.get("ns1", "k")
    assert out == value


@pytest.mark.asyncio
async def test_namespace_isolation(cache):
    """Different namespaces with same key → independent values.
    Pin so a global-namespace regression doesn't cross-pollute
    user-scoped vs public-scoped cache."""
    await cache.set("ns_a", "key", {"v": "A"}, ttl=60)
    await cache.set("ns_b", "key", {"v": "B"}, ttl=60)
    assert await cache.get("ns_a", "key") == {"v": "A"}
    assert await cache.get("ns_b", "key") == {"v": "B"}


# ---------------------------------------------------------------------------
# TTL expiry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_none_after_expiry(cache, monkeypatch):
    """Time advances past TTL → entry returns None.

    Pin so a regression that always returns the cached value would
    serve stale data forever."""
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    await cache.set("ns", "k", {"v": "x"}, ttl=60)
    # Advance past expiry
    monkeypatch.setattr(time, "time", lambda: 1100.0)
    assert await cache.get("ns", "k") is None


@pytest.mark.asyncio
async def test_get_within_ttl_returns_value(cache, monkeypatch):
    """Read within TTL window → value returned."""
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    await cache.set("ns", "k", {"v": "x"}, ttl=60)
    monkeypatch.setattr(time, "time", lambda: 1030.0)
    assert await cache.get("ns", "k") == {"v": "x"}


@pytest.mark.asyncio
async def test_get_at_exact_expiry_returns_none(cache, monkeypatch):
    """Read at exact expiry boundary → None (uses `<=` in production:
    expires_at <= now → expired). Pin the strict <= so a flapping
    clock at boundary doesn't oscillate."""
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    await cache.set("ns", "k", {"v": "x"}, ttl=60)
    # At t=1060, expires_at=1060 ≤ now=1060 → expired
    monkeypatch.setattr(time, "time", lambda: 1060.0)
    assert await cache.get("ns", "k") is None


@pytest.mark.asyncio
async def test_get_removes_expired_entry_from_storage(cache, monkeypatch):
    """Expired-on-get → entry is deleted (NOT just hidden). Pin so
    expired entries don't leak memory in long-running web servers."""
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    await cache.set("ns", "k", {"v": "x"}, ttl=60)
    monkeypatch.setattr(time, "time", lambda: 1100.0)
    await cache.get("ns", "k")  # triggers cleanup
    assert "ns:k" not in cache._entries


# ---------------------------------------------------------------------------
# invalidate_all — namespace bump
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initial_namespace_is_one(cache):
    """First call returns "1" (string)."""
    assert await cache.get_namespace() == "1"


@pytest.mark.asyncio
async def test_invalidate_all_bumps_namespace(cache):
    """invalidate_all → namespace counter +1. Pin so a single
    invalidate makes ALL old keys unreadable (atomic invalidation)."""
    assert await cache.get_namespace() == "1"
    await cache.invalidate_all()
    assert await cache.get_namespace() == "2"
    await cache.invalidate_all()
    assert await cache.get_namespace() == "3"


@pytest.mark.asyncio
async def test_invalidate_all_clears_entries(cache):
    """All in-memory entries dropped after invalidate."""
    await cache.set("old_ns", "k", {"v": "x"}, ttl=60)
    await cache.invalidate_all()
    assert cache._entries == {}


@pytest.mark.asyncio
async def test_invalidate_all_old_keys_unreadable(cache):
    """After invalidate, old-namespace lookups return None even with
    fresh `set` to a different namespace at the same key."""
    await cache.set("ns1", "k", {"v": "old"}, ttl=60)
    await cache.invalidate_all()
    assert await cache.get("ns1", "k") is None


# ---------------------------------------------------------------------------
# connect / close lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_is_noop(cache):
    """In-memory backend has nothing to connect to. Pin no-op so the
    interface contract is uniform with the Redis backend."""
    assert await cache.connect() is None


@pytest.mark.asyncio
async def test_close_clears_entries(cache):
    """close() drops all stored entries."""
    await cache.set("ns", "k", {"v": "x"}, ttl=60)
    await cache.close()
    assert cache._entries == {}


# ---------------------------------------------------------------------------
# Concurrency (lock contract)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_writes_do_not_lose_data(cache):
    """Race condition smoke test: 100 concurrent writes — final state
    has all 100 entries (lock serialises them). Pin so a regression
    that drops the lock can't silently lose entries."""
    async def _set(i):
        await cache.set("ns", f"k{i}", {"v": i}, ttl=60)

    await asyncio.gather(*[_set(i) for i in range(100)])
    # All 100 entries present
    for i in range(100):
        assert await cache.get("ns", f"k{i}") == {"v": i}


@pytest.mark.asyncio
async def test_overwrite_same_key_replaces_value(cache):
    """Setting same (ns,key) twice → second value wins."""
    await cache.set("ns", "k", {"v": "first"}, ttl=60)
    await cache.set("ns", "k", {"v": "second"}, ttl=60)
    assert await cache.get("ns", "k") == {"v": "second"}


# ---------------------------------------------------------------------------
# Edge cases: empty value / large value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_empty_dict_is_stored_and_returned(cache):
    """Empty dict {} is a valid cached value (NOT treated as None)."""
    await cache.set("ns", "k", {}, ttl=60)
    out = await cache.get("ns", "k")
    assert out == {}
    assert out is not None


@pytest.mark.asyncio
async def test_zero_ttl_immediately_expires(cache, monkeypatch):
    """ttl=0 → expires_at == now → expired on first read."""
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    await cache.set("ns", "k", {"v": "x"}, ttl=0)
    assert await cache.get("ns", "k") is None
