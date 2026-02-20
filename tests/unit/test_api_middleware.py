import pytest

import time
from collections import deque
from fastapi import FastAPI
import httpx
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from website.backend.middleware.http_cache_middleware import HTTPCacheMiddleware
from website.backend.middleware.rate_limit_middleware import RateLimitMiddleware
from website.backend.services.http_cache_backend import MemoryCacheBackend


@pytest.mark.asyncio
async def test_http_cache_middleware_etag_and_hit_cycle():
    app = FastAPI()
    cache_backend = MemoryCacheBackend()

    state = {"value": 0}

    @app.get("/api/stats/leaderboard")
    async def leaderboard():
        state["value"] += 1
        return {"value": state["value"]}

    app.add_middleware(HTTPCacheMiddleware, cache_backend=cache_backend)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.get("/api/stats/leaderboard")
        assert first.status_code == 200
        assert first.headers.get("X-Cache") == "MISS"
        assert first.json() == {"value": 1}

        etag = first.headers.get("ETag")
        assert etag

        second = await client.get("/api/stats/leaderboard")
        assert second.status_code == 200
        assert second.headers.get("X-Cache") == "HIT"
        assert second.json() == {"value": 1}

        third = await client.get("/api/stats/leaderboard", headers={"If-None-Match": etag})
        assert third.status_code == 304
        assert third.headers.get("ETag") == etag


@pytest.mark.asyncio
async def test_rate_limit_middleware_rejects_when_limit_exceeded(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_WINDOW", "2")
    monkeypatch.setenv("RATE_LIMIT_HEAVY_REQUESTS_PER_WINDOW", "1")

    app = FastAPI()

    @app.get("/api/stats/leaderboard")
    async def leaderboard():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.get("/api/stats/leaderboard")
        assert first.status_code == 200

        second = await client.get("/api/stats/leaderboard")
        assert second.status_code == 429
        body = second.json()
        assert body["detail"] == "Rate limit exceeded"
        assert body["bucket"] == "heavy"
        assert int(second.headers["X-RateLimit-Limit"]) == 1
        assert int(second.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_rate_limit_middleware_capacity_guard(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_WINDOW", "5")
    monkeypatch.setenv("RATE_LIMIT_HEAVY_REQUESTS_PER_WINDOW", "5")
    monkeypatch.setenv("RATE_LIMIT_MAX_TRACKED_KEYS", "1")

    app = FastAPI()

    @app.get("/api/stats/overview")
    async def overview():
        return {"ok": True}

    middleware = RateLimitMiddleware(app)
    middleware.max_tracked_keys = 1
    middleware._requests = {"existing:standard": deque([time.time()])}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/stats/overview",
        "raw_path": b"/api/stats/overview",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    request = Request(scope)

    async def call_next(_: Request) -> Response:
        return Response(content=b'{"ok":true}', media_type="application/json")

    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 429
    assert b"Rate limiter capacity reached" in response.body


def test_rate_limit_cleanup_evicts_empty_buckets():
    app = FastAPI()
    middleware = RateLimitMiddleware(app)
    middleware.window_seconds = 60

    now = 1_000.0
    middleware._requests = {
        "stale:standard": deque([now - 120]),
        "active:standard": deque([now - 5]),
    }

    middleware._cleanup_inactive_buckets(now)

    assert "stale:standard" not in middleware._requests
    assert "active:standard" in middleware._requests


def test_http_cache_extract_body_for_materialized_response():
    response = Response(content=b'{"ok":true}', media_type="application/json")
    payload = HTTPCacheMiddleware._extract_response_body(response)
    assert payload == b'{"ok":true}'


def test_http_cache_extract_body_returns_none_for_streaming_response():
    response = StreamingResponse(iter([b'{"ok":true}']), media_type="application/json")
    payload = HTTPCacheMiddleware._extract_response_body(response)
    assert payload is None


def test_http_cache_parse_content_length():
    assert HTTPCacheMiddleware._parse_content_length("128") == 128
    assert HTTPCacheMiddleware._parse_content_length("-1") is None
    assert HTTPCacheMiddleware._parse_content_length("not-a-number") is None
    assert HTTPCacheMiddleware._parse_content_length(None) is None
