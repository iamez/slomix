from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI

pytest.importorskip("httpx")
pytest.importorskip("itsdangerous")

from fastapi.testclient import TestClient
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
    return app


def _set_oauth_env(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("DISCORD_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("DISCORD_REDIRECT_URI", "https://stats.example.com/auth/callback")


def test_login_includes_csrf_state(monkeypatch):
    _set_oauth_env(monkeypatch)
    client = TestClient(_build_app())

    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code in {302, 307}

    location = response.headers["location"]
    parsed = urlsplit(location)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "discord.com"
    assert query["state"][0]
    assert query["redirect_uri"][0] == "https://stats.example.com/auth/callback"


def test_callback_rejects_invalid_oauth_state(monkeypatch):
    _set_oauth_env(monkeypatch)
    client = TestClient(_build_app())

    login_response = client.get("/auth/login", follow_redirects=False)
    assert login_response.status_code in {302, 307}

    bad_callback = client.get(
        "/auth/callback?code=test-code&state=wrong-state",
        follow_redirects=False,
    )
    assert bad_callback.status_code == 400
    assert bad_callback.json()["detail"] == "Invalid OAuth state"


def test_logout_uses_configured_origin_not_host_header(monkeypatch):
    _set_oauth_env(monkeypatch)
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://frontend.example.com")
    client = TestClient(_build_app())

    response = client.get(
        "/auth/logout",
        headers={"host": "attacker.example.com"},
        follow_redirects=False,
    )
    assert response.status_code in {302, 307}
    assert response.headers["location"] == "https://frontend.example.com/"
