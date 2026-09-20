from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
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


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("/app/sessions/159", "/app/sessions/159"),
        ("/app", "/app"),
        ("/app?tab=players", "/app?tab=players"),
        ("", None),
        (None, None),
        ("/", None),
        ("/#/profile", None),
        ("//evil.example.com/app", None),
        ("/\\evil.example.com", None),
        ("https://evil.example.com/app", None),
        ("/app/x\r\nSet-Cookie: a=b", None),
        ("/apple", None),
        ("/app/" + "a" * 600, None),
    ],
)
def test_safe_next_path_accepts_only_same_origin_app_paths(value, expected):
    assert auth_router._safe_next_path(value) == expected  # noqa: SLF001


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = ""
        self.headers: dict[str, str] = {}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        return None


# The router reaches Discord through the same httpx module this file uses, so
# the fake below is swapped in globally; keep the real client for the test
# transport.
_RealAsyncClient = httpx.AsyncClient


class _FakeDiscord:
    """Stands in for httpx.AsyncClient: the token exchange and the identity
    lookup both succeed, so the callback reaches its redirect."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, *args, **kwargs):
        return _FakeResponse({"access_token": "tok", "token_type": "Bearer"})

    async def get(self, *args, **kwargs):
        return _FakeResponse({"id": "123456789012345678", "username": "tester", "global_name": "Tester", "avatar": None})


async def _run_login_then_callback(monkeypatch, next_value: str | None) -> str:
    _set_oauth_env(monkeypatch)
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://stats.example.com")
    monkeypatch.setattr(auth_router.httpx, "AsyncClient", _FakeDiscord)

    async def _identity(db, **kwargs):
        return {"user_id": 1, "linked_player_guid": None, "linked_player_name": None}

    monkeypatch.setattr(auth_router, "_sync_website_identity", _identity)
    # The limiter counts logins per client across the whole process; three
    # round-trips in this file would trip it (429, no Location).
    auth_router._oauth_rate_buckets.clear()  # noqa: SLF001
    app = _build_app()
    transport = httpx.ASGITransport(app=app)
    async with _RealAsyncClient(transport=transport, base_url="http://testserver") as client:
        params = {} if next_value is None else {"next": next_value}
        login_response = await client.get("/auth/login", params=params, follow_redirects=False)
        state = parse_qs(urlsplit(login_response.headers["location"]).query)["state"][0]
        callback = await client.get(f"/auth/callback?code=test-code&state={state}", follow_redirects=False)
        assert callback.status_code in (302, 307), (callback.status_code, callback.text[:300])
        return callback.headers["location"]


@pytest.mark.asyncio
async def test_callback_returns_to_the_app_page_the_login_started_from(monkeypatch):
    assert await _run_login_then_callback(monkeypatch, "/app/sessions/159") == "https://stats.example.com/app/sessions/159"


@pytest.mark.asyncio
async def test_callback_ignores_a_foreign_next_and_keeps_the_old_default(monkeypatch):
    assert await _run_login_then_callback(monkeypatch, "https://evil.example.com/") == "https://stats.example.com/#/profile"
    assert await _run_login_then_callback(monkeypatch, None) == "https://stats.example.com/#/profile"
