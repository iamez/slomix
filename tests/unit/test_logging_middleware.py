from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from starlette.responses import JSONResponse

from website.backend.middleware import logging_middleware


class StubAccessLogger:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def info(self, message: str, extra=None) -> None:  # noqa: ANN001
        self.calls.append(("info", message))

    def warning(self, message: str, extra=None) -> None:  # noqa: ANN001
        self.calls.append(("warning", message))


@pytest.mark.asyncio
async def test_promotions_campaign_401_logs_as_info(monkeypatch):
    logger = StubAccessLogger()
    monkeypatch.setattr(logging_middleware, "access_logger", logger)

    app = FastAPI()

    @app.get("/api/availability/promotions/campaign")
    async def promotions_campaign():
        return JSONResponse({"detail": "Authentication required"}, status_code=401)

    app.add_middleware(logging_middleware.RequestLoggingMiddleware)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/availability/promotions/campaign")

    assert response.status_code == 401
    assert ("info", "→ GET /api/availability/promotions/campaign") in logger.calls
    assert any(
        level == "info" and "← GET /api/availability/promotions/campaign → 401" in message
        for level, message in logger.calls
    )
    assert not any(
        level == "warning" and "← GET /api/availability/promotions/campaign → 401" in message
        for level, message in logger.calls
    )


@pytest.mark.asyncio
async def test_other_401_still_logs_warning(monkeypatch):
    logger = StubAccessLogger()
    monkeypatch.setattr(logging_middleware, "access_logger", logger)

    app = FastAPI()

    @app.get("/api/private/resource")
    async def private_resource():
        return JSONResponse({"detail": "Authentication required"}, status_code=401)

    app.add_middleware(logging_middleware.RequestLoggingMiddleware)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/private/resource")

    assert response.status_code == 401
    assert any(
        level == "warning" and "← GET /api/private/resource → 401" in message
        for level, message in logger.calls
    )


def test_no_host_derived_paths_in_source():
    """Guard (IMP-006): every path classification and every logged path value
    must come from routed_path() (the raw ASGI scope path), never from
    request.url.path — Starlette reconstructs request.url with the
    client-controlled Host header, so a crafted Host could otherwise move a
    request into a QUIET path, out of a SECURITY path, or past the
    suspicious-pattern classifier."""
    src = Path(logging_middleware.__file__).read_text(encoding="utf-8")
    assert "request.url.path" not in src, "logging must not read Host-derived request.url.path"
    assert "routed_path" in src


class StubSecurityLogger:
    def __init__(self) -> None:
        self.records: list[tuple[str, dict]] = []

    def info(self, message: str, extra=None) -> None:  # noqa: ANN001
        self.records.append((message, extra or {}))

    def warning(self, message: str, extra=None) -> None:  # noqa: ANN001
        self.records.append((message, extra or {}))

    def log(self, level, message: str, extra=None) -> None:  # noqa: ANN001
        self.records.append((message, extra or {}))


@pytest.mark.asyncio
async def test_security_classification_uses_routed_path(monkeypatch):
    """Auth-path security events must carry the routed ASGI path."""
    sec = StubSecurityLogger()
    monkeypatch.setattr(logging_middleware, "security_logger", sec)

    app = FastAPI()

    @app.get("/auth/me")
    async def auth_me():
        return JSONResponse({"detail": "Authentication required"}, status_code=401)

    app.add_middleware(logging_middleware.RequestLoggingMiddleware)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/auth/me")

    assert response.status_code == 401
    paths = [extra.get("path") for _, extra in sec.records if "path" in extra]
    assert "/auth/me" in paths, "security event must record the routed path"



@pytest.mark.asyncio
async def test_control_characters_in_path_cannot_forge_log_lines(monkeypatch):
    """ASGI decodes %0A/%0D into scope['path'] — logged copies must escape
    control characters so a request can't inject fake log entries; the raw
    path still drives classification (Codex on #520)."""
    logger = StubAccessLogger()
    monkeypatch.setattr(logging_middleware, "access_logger", logger)

    app = FastAPI()
    app.add_middleware(logging_middleware.RequestLoggingMiddleware)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.get("/api/a%0Ainjected%0D")

    assert logger.calls, "request must be logged"
    for _, message in logger.calls:
        assert "\n" not in message and "\r" not in message, (
            f"log message contains raw control chars: {message!r}"
        )
    assert any("\\n" in m for _, m in logger.calls), "newline must be escaped, not dropped"
