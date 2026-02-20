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

