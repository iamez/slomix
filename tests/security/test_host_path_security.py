"""Host/path security hardening tests (AUD-005).

The pinned Starlette line has a published advisory where a malformed Host
header distorts `request.url`-derived values. The mitigation is two-layered:

1. TrustedHostMiddleware is the OUTERMOST middleware → unexpected/malformed
   Host gets 400 before anything else observes the request;
2. security decisions (CSRF prefix matching, sensitive-file blocking) read
   `request.scope["path"]` via `routed_path()`, which Host cannot influence.

These tests build a minimal app from the same building blocks main.py wires
(security_utils is import-light by design), so they run without booting the
full application.
"""
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from website.backend.security_utils import (  # noqa: E402
    CSRFMiddleware,
    resolve_trusted_hosts,
    routed_path,
)

TRUSTED = ["www.slomix.fyi", "slomix.fyi", "localhost", "127.0.0.1", "testserver"]


def _build_app() -> FastAPI:
    """Replicate main.py's security-relevant middleware order."""
    app = FastAPI()

    @app.get("/api/echo-path")
    async def echo_path(request: Request):
        return {"routed": routed_path(request), "url_path": request.url.path}

    @app.post("/api/mutate")
    async def mutate():
        return {"ok": True}

    @app.post("/plain/mutate")
    async def plain_mutate():
        return {"ok": True}

    @app.get("/login")
    async def login(request: Request):
        request.session["user"] = {"id": "1"}
        return {"ok": True}

    # Same add_middleware order as main.py: CSRF, then session, then the
    # trusted-host gate LAST so it ends up outermost.
    app.add_middleware(CSRFMiddleware, enabled=True, allowed_origins={"https://www.slomix.fyi"})
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=TRUSTED)
    return app


@pytest.fixture
def client():
    return TestClient(_build_app(), base_url="https://www.slomix.fyi")


# ── TrustedHost gate ─────────────────────────────────────────────────


@pytest.mark.parametrize("bad_host", [
    "evil.example",
    "www.slomix.fyi/",
    "www.slomix.fyi/../admin",
    "www.slomix.fyi?x=1",
    "www.slomix.fyi#frag",
    "www.slomix.fyi evil.example",
])
def test_malformed_or_unknown_host_gets_400(client, bad_host):
    resp = client.get("/api/echo-path", headers={"host": bad_host})
    assert resp.status_code == 400, (
        f"host {bad_host!r} must be rejected by the outermost TrustedHostMiddleware"
    )


def test_correct_hosts_pass(client):
    for good in ["www.slomix.fyi", "slomix.fyi", "localhost", "127.0.0.1"]:
        resp = client.get("/api/echo-path", headers={"host": good})
        assert resp.status_code == 200, f"host {good!r} must be allowed"


def test_host_with_port_passes():
    """Starlette compares the hostname part, so ports need no listing."""
    client = TestClient(_build_app(), base_url="http://localhost")
    assert client.get("/api/echo-path", headers={"host": "localhost:7000"}).status_code == 200


def test_trusted_host_runs_before_csrf(client):
    """Middleware order: a bad Host on a CSRF-protected mutation must yield
    400 (TrustedHost, outermost), never 403 (CSRF, inner)."""
    client.get("/login")
    resp = client.post("/api/mutate", headers={"host": "evil.example"})
    assert resp.status_code == 400


# ── routed_path ──────────────────────────────────────────────────────


def test_routed_path_matches_scope(client):
    resp = client.get("/api/echo-path")
    body = resp.json()
    assert body["routed"] == "/api/echo-path"
    assert body["routed"] == body["url_path"]


# ── CSRF uses the routed path ────────────────────────────────────────


def test_csrf_blocks_session_mutation_with_bad_origin(client):
    client.get("/login")
    resp = client.post("/api/mutate", headers={"origin": "https://evil.example"})
    assert resp.status_code == 403


def test_csrf_allows_good_origin(client):
    client.get("/login")
    resp = client.post("/api/mutate", headers={"origin": "https://www.slomix.fyi"})
    assert resp.status_code == 200


def test_csrf_ignores_non_api_paths(client):
    client.get("/login")
    resp = client.post("/plain/mutate", headers={"origin": "https://evil.example"})
    assert resp.status_code == 200


def test_csrf_skips_anonymous_requests(client):
    resp = client.post("/api/mutate", headers={"origin": "https://evil.example"})
    assert resp.status_code == 200


# ── resolve_trusted_hosts fail-fast ──────────────────────────────────


def test_production_posture_requires_trusted_hosts(monkeypatch):
    monkeypatch.delenv("TRUSTED_HOSTS", raising=False)
    with pytest.raises(ValueError, match="TRUSTED_HOSTS"):
        resolve_trusted_hosts(https_only=True)


def test_dev_posture_defaults_to_wildcard(monkeypatch):
    monkeypatch.delenv("TRUSTED_HOSTS", raising=False)
    assert resolve_trusted_hosts(https_only=False) == ["*"]


def test_configured_hosts_are_parsed_and_lowercased(monkeypatch):
    monkeypatch.setenv("TRUSTED_HOSTS", " WWW.Slomix.fyi , slomix.fyi ,localhost")
    assert resolve_trusted_hosts(https_only=True) == [
        "www.slomix.fyi", "slomix.fyi", "localhost",
    ]


def test_whitespace_only_setting_still_fails_fast(monkeypatch):
    monkeypatch.setenv("TRUSTED_HOSTS", "  ,  ")
    with pytest.raises(ValueError, match="TRUSTED_HOSTS"):
        resolve_trusted_hosts(https_only=True)
