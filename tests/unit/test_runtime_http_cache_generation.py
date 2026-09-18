"""HTTP runtime-generation behavior without starting a server or live DB."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from website.backend.middleware.http_cache_middleware import HTTPCacheMiddleware
from website.backend.services import runtime_cache_generation as generation_service
from website.backend.services.http_cache_backend import MemoryCacheBackend, ResilientCacheBackend

FLAGS = ("EVENT_STREAM_ENABLED", "RUNTIME_HTTP_CACHE_EVENTS_ENABLED", "RUNTIME_HTTP_CACHE_NAMESPACE_ENABLED")
PATH = "/api/stats/overview"


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    for flag in FLAGS:
        monkeypatch.setenv(flag, "true")


def client_for(cache, reader, endpoint):
    app = FastAPI()
    app.get(PATH)(endpoint)
    app.add_middleware(HTTPCacheMiddleware, cache_backend=cache, generation_reader=reader)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.parametrize("flag", FLAGS)
@pytest.mark.parametrize("value", [None, "false"])
async def test_off_never_reads_generation(monkeypatch, flag, value):
    if value is None:
        monkeypatch.delenv(flag, raising=False)
    else:
        monkeypatch.setenv(flag, value)
    reader = AsyncMock(side_effect=AssertionError("must not read"))

    async def endpoint():
        return {"value": 1}

    async with client_for(MemoryCacheBackend(), reader, endpoint) as client:
        assert (await client.get(PATH)).headers["X-Cache"] == "MISS"
        assert (await client.get(PATH)).headers["X-Cache"] == "HIT"
    reader.assert_not_awaited()


@pytest.mark.parametrize("bad", [None, -1, True, "1", TimeoutError(), RuntimeError("private diagnostic")])
async def test_unverified_generation_bypasses_get_and_set(bad, caplog):
    reader = AsyncMock(side_effect=bad) if isinstance(bad, Exception) else AsyncMock(return_value=bad)
    cache = AsyncMock()

    async def endpoint():
        return {"value": "fresh"}

    async with client_for(cache, reader, endpoint) as client:
        response = await client.get(PATH)
    assert response.json() == {"value": "fresh"}
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Cache"] == "BYPASS-GENERATION"
    cache.get_namespace.assert_not_awaited()
    cache.get.assert_not_awaited()
    cache.set.assert_not_awaited()
    assert "private diagnostic" not in caplog.text


async def test_two_workers_and_redis_startup_fallback_observe_shared_epoch():
    state = {"generation": 0, "value": "old"}

    async def reader():
        return state["generation"]

    async def endpoint():
        return {"value": state["value"]}

    primary = AsyncMock()
    primary.connect.side_effect = ConnectionError("unavailable")
    fallback = ResilientCacheBackend(primary, MemoryCacheBackend())
    await fallback.connect()
    async with client_for(MemoryCacheBackend(), reader, endpoint) as one, client_for(fallback, reader, endpoint) as two:
        for client in (one, two):
            assert (await client.get(PATH)).headers["X-Cache"] == "MISS"
            assert (await client.get(PATH)).headers["X-Cache"] == "HIT"
        state.update(generation=1, value="new")
        for client in (one, two):
            response = await client.get(PATH)
            assert response.headers["X-Cache"] == "MISS"
            assert response.json() == {"value": "new"}
    await fallback.close()


async def test_old_inflight_response_cannot_populate_new_epoch():
    started, finish = asyncio.Event(), asyncio.Event()
    state = {"generation": 0, "calls": 0}

    async def reader():
        return state["generation"]

    async def endpoint():
        state["calls"] += 1
        if state["calls"] == 1:
            started.set()
            await finish.wait()
            return {"value": "old"}
        return {"value": "new"}

    async with client_for(MemoryCacheBackend(), reader, endpoint) as client:
        task = asyncio.create_task(client.get(PATH))
        try:
            await asyncio.wait_for(started.wait(), timeout=2)
            state["generation"] = 1
            assert (await client.get(PATH)).json() == {"value": "new"}
            finish.set()
            assert (await task).json() == {"value": "old"}
            latest = await client.get(PATH)
            assert latest.headers["X-Cache"] == "HIT"
            assert latest.json() == {"value": "new"}
        finally:
            finish.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("value", [None, -1, True, 1.5, "0"])
async def test_reader_rejects_invalid_database_value(monkeypatch, value):
    adapter = SimpleNamespace(fetch_val=AsyncMock(return_value=value))
    monkeypatch.setattr(generation_service, "get_db_pool", lambda: adapter)
    with pytest.raises(ValueError):
        await generation_service.read_http_cache_generation()


async def test_reader_uses_current_pool_and_parameterized_query(monkeypatch):
    state = {"pool": None}
    monkeypatch.setattr(generation_service, "get_db_pool", lambda: state["pool"])
    with pytest.raises(RuntimeError, match="unavailable"):
        await generation_service.read_http_cache_generation()
    state["pool"] = SimpleNamespace(fetch_val=AsyncMock(return_value=7))
    assert await generation_service.read_http_cache_generation() == 7
    state["pool"].fetch_val.assert_awaited_once_with(
        "SELECT generation FROM runtime_cache_generations WHERE cache_name = ?", ("http_api",),
    )


async def test_reader_timeout_cancels_query(monkeypatch):
    cancelled = asyncio.Event()

    async def query(*args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(generation_service, "GENERATION_READ_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(generation_service, "get_db_pool", lambda: SimpleNamespace(fetch_val=query))
    with pytest.raises(TimeoutError):
        await generation_service.read_http_cache_generation()
    assert cancelled.is_set()


async def test_cancellation_is_not_hidden_as_bypass():
    reader = AsyncMock(side_effect=asyncio.CancelledError())
    cache, call_next = AsyncMock(), AsyncMock()
    middleware = HTTPCacheMiddleware(FastAPI(), cache, generation_reader=reader)
    request = Request({"type": "http", "method": "GET", "path": PATH, "query_string": b"", "headers": []})
    with pytest.raises(asyncio.CancelledError):
        await middleware.dispatch(request, call_next)
    call_next.assert_not_awaited()
    cache.get.assert_not_awaited()
