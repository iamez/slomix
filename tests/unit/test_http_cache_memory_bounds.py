"""Bound abandoned epochs and late old-epoch writes without a server process."""

# ruff: noqa: SLF001 -- retained storage, not just lookup results, is the contract.

import asyncio
import sys

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from website.backend.middleware.http_cache_middleware import HTTPCacheMiddleware
from website.backend.services.http_cache_backend import MemoryCacheBackend


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "10", None])
@pytest.mark.parametrize("name", ["max_entries", "max_bytes"])
def test_invalid_limits(limit, name):
    with pytest.raises(ValueError, match="positive integers"):
        MemoryCacheBackend(**{name: limit})


@pytest.mark.asyncio
async def test_many_epochs_and_late_old_write_remain_bounded():
    cache = MemoryCacheBackend(max_entries=3)
    for epoch in range(100):
        await cache.set(str(epoch), "key", {"epoch": epoch}, ttl=60)
        assert len(cache._entries) <= 3
    await cache.set("0", "key", {"epoch": 0}, ttl=60)
    assert len(cache._entries) == 3
    assert await cache.get("99", "key") == {"epoch": 99}
    assert await cache.get("0", "key") == {"epoch": 0}
    assert await cache.get("97", "key") is None
    reachable = [await cache.get(str(epoch), "key") for epoch in range(100)]
    assert sum(value is not None for value in reachable) == len(cache._entries) == 3


@pytest.mark.asyncio
async def test_replacement_at_capacity_refreshes_fifo_without_extra_eviction():
    cache = MemoryCacheBackend(max_entries=2)
    await cache.set("ns", "first", {"version": 1}, ttl=60)
    await cache.set("ns", "second", {}, ttl=60)
    await cache.set("ns", "first", {"version": 2}, ttl=60)
    assert await cache.get("ns", "second") == {}
    assert await cache.get("ns", "first") == {"version": 2}
    await cache.set("ns", "third", {}, ttl=60)
    assert await cache.get("ns", "second") is None
    assert await cache.get("ns", "first") == {"version": 2}


@pytest.mark.asyncio
async def test_byte_budget_includes_keys_and_unicode():
    cache = MemoryCacheBackend(max_entries=100, max_bytes=1024)
    for index in range(40):
        await cache.set("epoch", f"{index}" + "č" * 60, {"body": "ž" * 20}, ttl=60)
        measured = sum(sys.getsizeof(key) + sys.getsizeof(value[1])
                       for key, value in cache._entries.items())
        assert measured <= 1024
    assert len(cache._entries) < 40
    assert await cache.get("epoch", "39" + "č" * 60) == {"body": "ž" * 20}


@pytest.mark.asyncio
async def test_expired_abandoned_namespace_pruned_on_other_write(monkeypatch):
    monkeypatch.setattr("website.backend.services.http_cache_backend.time.time", lambda: 1000)
    cache = MemoryCacheBackend()
    await cache.set("old", "key", {}, ttl=1)
    monkeypatch.setattr("website.backend.services.http_cache_backend.time.time", lambda: 1002)
    await cache.set("new", "other", {}, ttl=60)
    assert list(cache._entries) == ["new:other"]


@pytest.mark.asyncio
@pytest.mark.parametrize("ttl,body", [(0, {}), (60, {"body": "x" * 1024})])
async def test_uncacheable_replacement_removes_old_value(ttl, body):
    cache = MemoryCacheBackend(max_bytes=512)
    await cache.set("ns", "key", {"old": True}, ttl=60)
    await cache.set("ns", "key", body, ttl=ttl)
    assert await cache.get("ns", "key") is None


@pytest.mark.asyncio
async def test_concurrent_writes_respect_capacity_and_cleanup():
    cache = MemoryCacheBackend(max_entries=5, max_bytes=1024)
    await asyncio.gather(*(cache.set(str(i), "k", {"value": i}, ttl=60) for i in range(100)))
    assert len(cache._entries) == 5
    assert sum(sys.getsizeof(k) + sys.getsizeof(v[1]) for k, v in cache._entries.items()) <= 1024
    await cache.invalidate_all()
    assert not cache._entries
    await cache.set("new", "k", {}, ttl=60)
    await cache.close()
    assert not cache._entries


@pytest.mark.asyncio
async def test_http_eviction_recomputes_without_wrong_response():
    cache = MemoryCacheBackend(max_entries=1)
    app = FastAPI()
    calls = []

    @app.get("/api/stats/overview")
    async def overview(value: int):
        calls.append(value)
        return {"value": value}

    app.add_middleware(HTTPCacheMiddleware, cache_backend=cache)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for value, expected in [(1, "MISS"), (1, "HIT"), (2, "MISS"), (1, "MISS")]:
            response = await client.get("/api/stats/overview", params={"value": value})
            assert response.status_code == 200
            assert response.json() == {"value": value}
            assert response.headers["X-Cache"] == expected
    assert calls == [1, 2, 1]
    assert len(cache._entries) == 1
