"""Regression test for the client-error DoS gap (Codex P2 review on #578).

FastAPI validates the request body (and, on a validation error, echoes an
oversized field straight back in the 422 response) BEFORE a route's own
@limiter.limit(...) decorator ever runs. On the public, unauthenticated
/api/client-error endpoint, that meant an attacker sending repeated
malformed/oversized bodies was never rate-limited at all. RateLimitMiddleware
runs at the ASGI level, outside FastAPI's routing/body-parsing entirely, so a
dedicated bucket there applies before a single byte of the body is read.
"""
import json

import httpx
import pytest
from fastapi import FastAPI

from website.backend.middleware.rate_limit_middleware import RateLimitMiddleware
from website.backend.routers import client_error_router


@pytest.mark.asyncio
async def test_client_error_bucket_limits_before_body_is_read(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("RATE_LIMIT_CLIENT_ERROR_REQUESTS_PER_WINDOW", "2")

    app = FastAPI()

    @app.post("/api/client-error")
    async def client_error():
        # Never reached once the middleware bucket is exhausted - if this
        # runs on the 3rd request, the fix regressed.
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.post("/api/client-error", json={"message": "x"})
        assert first.status_code == 200

        second = await client.post("/api/client-error", json={"message": "x"})
        assert second.status_code == 200

        third = await client.post("/api/client-error", json={"message": "x"})
        assert third.status_code == 429
        assert third.json()["bucket"] == "client_error"


@pytest.mark.asyncio
async def test_client_error_oversized_body_rejected_before_parsing(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_CLIENT_ERROR_MAX_BODY_BYTES", "1024")

    app = FastAPI()
    reached_handler = {"value": False}

    @app.post("/api/client-error")
    async def client_error():
        reached_handler["value"] = True
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/client-error",
            content=b"x" * 2048,
            headers={"content-length": "2048"},
        )

    assert response.status_code == 413
    assert reached_handler["value"] is False, "oversized body must be rejected before the route handler runs"


@pytest.mark.asyncio
async def test_client_error_chunked_body_without_content_length_is_refused(monkeypatch):
    """Codex P2 review on #578 (second round): the size cap was a Content-Length
    check that only ran `if content_length is not None`, so a client using
    Transfer-Encoding: chunked (or just omitting the header) skipped it entirely
    and reached the handler with an arbitrarily large body. Reading the body in
    ASGI middleware to measure it isn't an option — that consumes the stream
    before FastAPI can parse it — so the header is required on this endpoint.
    """
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_CLIENT_ERROR_MAX_BODY_BYTES", "1024")

    app = FastAPI()
    reached_handler = {"value": False}

    @app.post("/api/client-error")
    async def client_error():
        reached_handler["value"] = True
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware)

    # An async iterator body makes httpx send Transfer-Encoding: chunked with
    # no Content-Length — the same shape a hand-rolled attacker request uses.
    async def chunked_body():
        yield b"x" * 2048

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/client-error", content=chunked_body())

    assert response.status_code == 411, (
        "a body with no declared length can't be size-checked, so it must be "
        f"refused rather than passed through (got {response.status_code})"
    )
    assert reached_handler["value"] is False, "unbounded body must not reach the route handler"


@pytest.mark.asyncio
async def test_body_cap_applies_even_when_rate_limiting_disabled(monkeypatch):
    """Codex review on #578: the cap sat AFTER dispatch()'s `if not self.enabled`
    early return, so RATE_LIMIT_ENABLED=false left the public endpoint parsing
    arbitrarily large or chunked bodies — recreating the pre-validation DoS the
    middleware was added to close. It's a payload-validity gate, not a rate
    limit, so it has to run regardless.
    """
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("RATE_LIMIT_CLIENT_ERROR_MAX_BODY_BYTES", "1024")

    app = FastAPI()
    reached_handler = {"value": False}

    @app.post("/api/client-error")
    async def client_error():
        reached_handler["value"] = True
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        oversized = await client.post(
            "/api/client-error", content=b"x" * 2048, headers={"content-length": "2048"}
        )

        async def chunked_body():
            yield b"x" * 2048

        chunked = await client.post("/api/client-error", content=chunked_body())

    assert oversized.status_code == 413, "size cap must not depend on RATE_LIMIT_ENABLED"
    assert chunked.status_code == 411, "length requirement must not depend on RATE_LIMIT_ENABLED"
    assert reached_handler["value"] is False


@pytest.mark.asyncio
async def test_schema_valid_unicode_report_is_not_rejected(monkeypatch):
    """Codex review on #578: the Pydantic field limits are in CHARACTERS while
    this cap is in BYTES, so a report satisfying every schema limit could still
    be 413'd before validation — 2000 CJK chars in message + stack alone exceed
    the old 10240 default (they serialize to ~14.7 KB).
    """
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.delenv("RATE_LIMIT_CLIENT_ERROR_MAX_BODY_BYTES", raising=False)

    app = FastAPI()
    app.state.limiter = client_error_router.limiter
    app.include_router(client_error_router.router, prefix="/api")
    app.add_middleware(RateLimitMiddleware)

    payload = {
        "message": "漢" * 2000,
        "stack": "漢" * 2000,
        "page_url": "漢" * 500,
        "user_agent": "漢" * 300,
        "timestamp": "漢" * 64,
    }
    body = json.dumps(payload, ensure_ascii=False).encode()
    assert len(body) > 10240, "fixture must exceed the old default to be meaningful"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/client-error",
            content=body,
            headers={"content-type": "application/json", "content-length": str(len(body))},
        )

    assert response.status_code == 204, (
        f"a report inside every schema limit must not be rejected on size "
        f"(got {response.status_code}, body was {len(body)} bytes)"
    )


@pytest.mark.asyncio
async def test_client_error_malformed_content_length_is_refused(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")

    app = FastAPI()
    reached_handler = {"value": False}

    @app.post("/api/client-error")
    async def client_error():
        reached_handler["value"] = True
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/client-error",
            content=b"{}",
            headers={"content-length": "not-a-number"},
        )

    assert response.status_code == 400
    assert reached_handler["value"] is False
