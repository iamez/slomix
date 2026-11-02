"""Exercise the actual router with host-only Secure cookies, no external login."""
# ruff: noqa: SLF001 -- test-only bucket reset and pure configuration guard probes

from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from website.backend.routers import auth


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("DISCORD_CLIENT_ID", "test-client")
    monkeypatch.setenv("DISCORD_CLIENT_SECRET", "fixture-only")
    monkeypatch.setenv("DISCORD_REDIRECT_URI", "https://dev.example/auth/callback")
    monkeypatch.delenv("DISCORD_REDIRECT_URI_ALLOWLIST", raising=False)
    monkeypatch.setenv("WEBSITE_UI_MODE", "app")
    auth._oauth_rate_buckets.clear()
    application = FastAPI()
    application.add_middleware(SessionMiddleware, secret_key="fixture-only", https_only=True)
    application.include_router(auth.router, prefix="/auth")
    return application


@pytest.mark.asyncio
@pytest.mark.parametrize("origin", ["http://192.0.2.10:8000", "http://100.64.0.1:8000", "http://dev.example", "https://dev.example:8443"])
async def test_alias_redirects_before_creating_oauth_state(app, origin):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url=origin) as client:
        response = await client.get("/auth/login", params={"next": "/app/session-detail/123"})
        assert response.status_code == 307
        assert response.headers["location"] == "https://dev.example/auth/login?next=%2Fapp%2Fsession-detail%2F123"
        assert "set-cookie" not in response.headers
        canonical = await client.get(response.headers["location"])
        query = parse_qs(urlsplit(canonical.headers["location"]).query)
        assert urlsplit(canonical.headers["location"]).hostname == "discord.com"
        assert query["state"] and query["code_challenge"]
        assert query["redirect_uri"] == ["https://dev.example/auth/callback"]
        assert "secure" in canonical.headers["set-cookie"].lower()
        assert {cookie.domain for cookie in client.cookies.jar} == {"dev.example"}


@pytest.mark.asyncio
@pytest.mark.parametrize("next_path", ["https://evil.example", "//evil.example", "/\\evil.example"])
async def test_alias_cannot_control_redirect_target(app, next_path):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://alias.example") as client:
        response = await client.get("/auth/login", params={"next": next_path}, headers={"X-Forwarded-Host": "evil.example"})
        assert response.headers["location"] == "https://dev.example/auth/login"
        assert "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_default_https_port_does_not_create_redirect_loop(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://dev.example:443") as client:
        response = await client.get("/auth/login")
        assert urlsplit(response.headers["location"]).hostname == "discord.com"


@pytest.mark.parametrize("uri", [
    "javascript://dev.example/auth/callback", "https://user:pass@dev.example/auth/callback",
    "https://dev.example:99999/auth/callback", "https://dev.example/auth/callback?next=evil",
    "https://dev.example/auth/callback#frag", "https://dev.example\\evil/auth/callback",
    "https://dev.example/auth/\ncallback",
])
def test_invalid_callback_configuration_refused(uri):
    with pytest.raises(auth.HTTPException) as error:
        auth._normalize_redirect_uri(uri)
    assert error.value.status_code == 500
    assert error.value.detail == "Invalid DISCORD_REDIRECT_URI configuration"


def test_explicit_redirect_allowlist_is_not_self_authorizing(app, monkeypatch):
    monkeypatch.setenv("DISCORD_REDIRECT_URI_ALLOWLIST", "https://other.example/auth/callback")
    with pytest.raises(auth.HTTPException, match="not allowlisted"):
        auth.get_discord_config()


def test_explicit_redirect_allowlist_accepts_configured_callback(app, monkeypatch):
    monkeypatch.setenv("DISCORD_REDIRECT_URI_ALLOWLIST", "https://dev.example/auth/callback")
    assert auth.get_discord_config()["redirect_uri"] == "https://dev.example/auth/callback"


@pytest.mark.asyncio
async def test_logout_returns_to_new_app_without_auth_network(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://dev.example") as client:
        response = await client.post("/auth/logout", headers={"X-Requested-With": "XMLHttpRequest"})
        assert response.status_code == 200
        assert response.json()["redirect_url"] == "https://dev.example/app"


@pytest.mark.parametrize("mode,profile,expected", [
    ("app", False, "/app"), ("app", True, "/app/profile"),
    ("legacy", False, "/"), ("legacy", True, "/#/profile"),
])
def test_default_login_destination_matches_frontend(monkeypatch, mode, profile, expected):
    monkeypatch.setenv("WEBSITE_UI_MODE", mode)
    assert auth._frontend_default_path(profile=profile) == expected
