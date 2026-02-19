from urllib.parse import parse_qs, urlsplit

import pytest
import httpx
from fastapi import FastAPI, Request

pytest.importorskip("itsdangerous")

from starlette.middleware.sessions import SessionMiddleware

from website.backend.dependencies import get_db
from website.backend.routers import auth as auth_router


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-session-secret")

    async def _db_override():
        yield None

    app.dependency_overrides[get_db] = _db_override
    app.include_router(auth_router.router, prefix="/auth")

    @app.post("/_test/login")
    async def _test_login(request: Request):
        payload = await request.json()
        request.session["user"] = payload
        return {"ok": True}

    return app


def _set_oauth_env(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("DISCORD_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("DISCORD_REDIRECT_URI", "https://stats.example.com/auth/callback")


@pytest.mark.asyncio
async def test_login_includes_csrf_state(monkeypatch):
    _set_oauth_env(monkeypatch)
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/auth/login", follow_redirects=False)
        assert response.status_code in {302, 307}

        location = response.headers["location"]
        parsed = urlsplit(location)
        query = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert parsed.netloc == "discord.com"
        assert query["state"][0]
        assert query["redirect_uri"][0] == "https://stats.example.com/auth/callback"


@pytest.mark.asyncio
async def test_callback_rejects_invalid_oauth_state(monkeypatch):
    _set_oauth_env(monkeypatch)
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        login_response = await client.get("/auth/login", follow_redirects=False)
        assert login_response.status_code in {302, 307}

        bad_callback = await client.get(
            "/auth/callback?code=test-code&state=wrong-state",
            follow_redirects=False,
        )
        assert bad_callback.status_code == 400
        assert bad_callback.json()["detail"] == "Invalid OAuth state"


@pytest.mark.asyncio
async def test_logout_uses_configured_origin_not_host_header(monkeypatch):
    _set_oauth_env(monkeypatch)
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://frontend.example.com")
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/auth/logout",
            headers={
                "host": "attacker.example.com",
                "x-requested-with": "XMLHttpRequest",
            },
        )
        assert response.status_code == 200
        assert response.json()["redirect_url"] == "https://frontend.example.com/"


@pytest.mark.asyncio
async def test_link_status_reports_guest_for_anonymous_user(monkeypatch):
    _set_oauth_env(monkeypatch)
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/auth/link/status")
        assert response.status_code == 200
        body = response.json()
        assert body["authenticated"] is False
        assert body["player_linked"] is False


@pytest.mark.asyncio
async def test_link_start_redirects_to_login_when_anonymous(monkeypatch):
    _set_oauth_env(monkeypatch)
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/auth/link/start", follow_redirects=False)
        assert response.status_code in {302, 307}
        assert response.headers["location"].endswith("/auth/login")
