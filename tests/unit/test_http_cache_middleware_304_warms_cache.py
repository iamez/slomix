"""Regression test for the 304-on-miss cache-warming bug (Codex review on #574).

A cache MISS whose recomputed body happens to match the client's
If-None-Match (same underlying data, just an expired/evicted server-side
entry) used to return 304 and skip cache_backend.set() entirely. On an
expensive endpoint with a client that keeps sending the same ETag, that left
the cache permanently empty — every request recomputed from scratch,
forever, never warming a cache a later request could hit.
"""
from __future__ import annotations

import hashlib

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from website.backend.middleware.http_cache_middleware import HTTPCacheMiddleware
from website.backend.services.http_cache_backend import MemoryCacheBackend


def _app(cache_backend):
    app = FastAPI()

    @app.get("/api/proximity/whatever")
    async def whatever():
        return {"value": 42}

    app.add_middleware(HTTPCacheMiddleware, cache_backend=cache_backend)
    return app


@pytest.mark.asyncio
async def test_matching_etag_on_cache_miss_still_populates_cache():
    cache_backend = MemoryCacheBackend()
    transport = ASGITransport(app=_app(cache_backend))

    # The body-derived ETag is deterministic — sha256 of the JSON body,
    # truncated to 24 hex chars and quoted, matching _compute_etag exactly
    # (http_cache_middleware.py:336-338). This simulates a client that
    # already has a stale-but-still-accurate ETag from before the
    # server-side cache entry expired/was evicted.
    expected_body = b'{"value":42}'
    expected_etag = f'"{hashlib.sha256(expected_body).hexdigest()[:24]}"'

    async with AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get(
            "/api/proximity/whatever",
            headers={"If-None-Match": expected_etag},
        )

    assert response.status_code == 304

    # Cache key construction mirrors the middleware's _build_cache_key —
    # simplest robust check is just "the cache is no longer empty."
    assert cache_backend._entries, (  # noqa: SLF001 - inspecting internal state is the point of this test
        "a 304 on a cache MISS must still populate the cache; a client that "
        "keeps sending the same ETag would otherwise never let the cache warm"
    )
