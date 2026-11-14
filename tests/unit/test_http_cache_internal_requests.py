"""Internal requests must reach real authentication outside shared HTTP cache."""

from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from website.backend.dependencies import get_internal_request_mode
from website.backend.middleware.http_cache_middleware import HTTPCacheMiddleware
from website.backend.services.http_cache_backend import MemoryCacheBackend

PATH = "/api/storytelling/kill-impact"
SECRET = "dummy_internal_cache_fixture"  # noqa: S105 - synthetic authentication fixture
pytestmark = pytest.mark.asyncio


@pytest.fixture(params=[False, True], ids=["generation-off", "generation-on"])
def runtime_mode(request, monkeypatch):
    for flag in ("EVENT_STREAM_ENABLED", "RUNTIME_HTTP_CACHE_EVENTS_ENABLED",
                 "RUNTIME_HTTP_CACHE_NAMESPACE_ENABLED"):
        monkeypatch.setenv(flag, str(request.param).lower())
    monkeypatch.setenv("INTERNAL_API_SECRET", SECRET)
    return request.param


def client_for(cache, reader):
    app = FastAPI()
    calls = []

    @app.get(PATH)
    async def endpoint(internal: bool = Depends(get_internal_request_mode),
                       gaming_session_id: int = 184, error: str = ""):
        if error == "handled":
            raise HTTPException(503, "Fixture unavailable")
        if error == "exception":
            raise RuntimeError("Fixture handler failure")
        calls.append((gaming_session_id, internal))
        return {"status": "ok",
                "scope": {"gaming_session_id": gaming_session_id, "dates": ["2026-11-12"]},
                "compute": {"status": "computed" if internal else "read_only", "kills_scored": 92}}

    app.add_middleware(HTTPCacheMiddleware, cache_backend=cache, generation_reader=reader)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://fixture"), calls


@pytest.mark.parametrize("token", [SECRET, "invalid-fixture", ""], ids=["valid", "invalid", "empty"])
@pytest.mark.parametrize("warm", [False, True], ids=["cold", "public-warm"])
async def test_internal_header_presence_bypasses_shared_cache(runtime_mode, token, warm):
    cache = AsyncMock(wraps=MemoryCacheBackend())
    reader = AsyncMock(return_value=1)
    client, calls = client_for(cache, reader)
    async with client:
        if warm:
            public = await client.get(PATH)
            assert public.headers["X-Cache"] == "MISS"
            assert (await client.get(PATH)).headers["X-Cache"] == "HIT"
        before = (cache.get_namespace.await_count, cache.get.await_count,
                  cache.set.await_count, reader.await_count)
        response = await client.get(PATH, headers={"X-Internal-Token": token})
        assert response.status_code == (200 if token == SECRET else 401)
        assert response.headers["Cache-Control"] == "private, no-store"
        assert "X-Cache" not in response.headers
        assert (cache.get_namespace.await_count, cache.get.await_count,
                cache.set.await_count, reader.await_count) == before
        if token == SECRET:
            assert response.json()["compute"]["status"] == "computed"
            assert calls[-1] == (184, True)
        else:
            assert calls == ([(184, False)] if warm else [])


async def test_internal_first_never_populates_public_response_or_etag(runtime_mode):
    cache = MemoryCacheBackend()
    reader = AsyncMock(return_value=1)
    client, calls = client_for(cache, reader)
    async with client:
        internal = await client.get(PATH, headers={"X-Internal-Token": SECRET})
        assert internal.json()["compute"]["status"] == "computed"
        assert not cache._entries  # noqa: SLF001 - no internal envelope may be retained
        public = await client.get(PATH)
        assert public.headers["X-Cache"] == "MISS"
        assert public.json()["compute"]["status"] == "read_only"
        etag = public.headers["ETag"]
        conditional = await client.get(PATH, headers={"If-None-Match": etag})
        assert conditional.status_code == 304
        again = await client.get(PATH, headers={"X-Internal-Token": SECRET, "If-None-Match": etag})
        assert again.status_code == 200
        assert again.json()["compute"]["status"] == "computed"
        assert "ETag" not in again.headers
        other = await client.get(PATH, params={"gaming_session_id": 185})
        assert other.headers["X-Cache"] == "MISS"
        assert other.json()["scope"]["gaming_session_id"] == 185
        assert (await client.get(PATH)).headers["X-Cache"] == "HIT"
        assert calls == [(184, True), (184, False), (184, True), (185, False)]


@pytest.mark.parametrize("headers", [{"Authorization": "Bearer fixture"}, {"Cookie": "fixture=1"}])
async def test_existing_sensitive_request_bypass_is_preserved(runtime_mode, headers):
    cache = AsyncMock(wraps=MemoryCacheBackend())
    reader = AsyncMock(return_value=1)
    client, _ = client_for(cache, reader)
    async with client:
        response = await client.get(PATH, headers=headers)
    assert response.headers["Cache-Control"] == "private, no-store"
    cache.get.assert_not_awaited()
    cache.set.assert_not_awaited()
    reader.assert_not_awaited()


async def test_internal_auth_precedes_generation_failure(runtime_mode):
    reader = AsyncMock(side_effect=RuntimeError("Fixture generation unavailable"))
    cache = AsyncMock(wraps=MemoryCacheBackend())
    client, _ = client_for(cache, reader)
    async with client:
        for token, status in [(SECRET, 200), ("invalid-fixture", 401), ("", 401)]:
            response = await client.get(PATH, headers={"X-Internal-Token": token})
            assert response.status_code == status
            assert response.headers["Cache-Control"] == "private, no-store"
    reader.assert_not_awaited()
    cache.get.assert_not_awaited()
    cache.set.assert_not_awaited()


@pytest.mark.parametrize("error", ["handled", "exception"])
async def test_internal_errors_never_touch_shared_cache(runtime_mode, error):
    cache = AsyncMock(wraps=MemoryCacheBackend())
    reader = AsyncMock(return_value=1)
    client, _ = client_for(cache, reader)
    async with client:
        if error == "exception":
            with pytest.raises(RuntimeError, match="Fixture handler failure"):
                await client.get(PATH, params={"error": error}, headers={"X-Internal-Token": SECRET})
        else:
            response = await client.get(PATH, params={"error": error}, headers={"X-Internal-Token": SECRET})
            assert response.status_code == 503
            assert response.headers["Cache-Control"] == "private, no-store"
    reader.assert_not_awaited()
    cache.get.assert_not_awaited()
    cache.set.assert_not_awaited()
