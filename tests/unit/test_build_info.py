"""Build/revision handshake (Codex PX-DEV-002).

website/backend/build_info.py answers "what code is this process actually
running" without touching the database — the fix for the mixed-revision
failure mode (old Python handlers + a StaticFiles-served newer frontend from
the same mutable checkout, or request-time lazy imports pulling in newer
service code mid-process).
"""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from website.backend import build_info


def test_git_revision_is_captured_at_import():
    """Real repo checkout — HEAD must resolve to a 40-char SHA."""
    revision = build_info._GIT_REVISION  # noqa: SLF001
    revision_short = build_info._GIT_REVISION_SHORT  # noqa: SLF001
    assert revision is not None
    assert len(revision) == 40
    assert revision_short == revision[:8]


def test_schema_ledger_max_file_matches_highest_numbered_migration():
    """Cross-check against a real directory listing rather than hardcoding
    a version — this must track the repo's actual migrations/ contents."""
    import re
    from pathlib import Path

    migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
    numbered = [
        (int(m.group(1)), p.stem)
        for p in migrations_dir.glob("*.sql")
        if (m := re.match(r"^(\d+)", p.name))
    ]
    expected = max(numbered, key=lambda t: t[0])[1]
    actual = build_info._SCHEMA_LEDGER_MAX_FILE  # noqa: SLF001
    assert actual == expected


def test_compute_api_contract_hash_is_stable_for_same_routes():
    app1 = FastAPI()
    app2 = FastAPI()

    @app1.get("/api/x")
    async def x1():
        return {}

    @app2.get("/api/x")
    async def x2():
        return {}

    assert build_info.compute_api_contract_hash(app1) == build_info.compute_api_contract_hash(app2)


def test_compute_api_contract_hash_differs_for_different_routes():
    app1 = FastAPI()
    app2 = FastAPI()

    @app1.get("/api/x")
    async def x():
        return {}

    @app2.get("/api/y")
    async def y():
        return {}

    assert build_info.compute_api_contract_hash(app1) != build_info.compute_api_contract_hash(app2)


def test_compute_api_contract_hash_is_method_sensitive():
    """The same path with a DIFFERENT method set must hash differently —
    a route-set mismatch that only adds/removes a verb is exactly the kind
    of silent drift PX-DEV-003 needs to catch."""
    app1 = FastAPI()
    app2 = FastAPI()

    @app1.get("/api/x")
    async def get_only():
        return {}

    @app2.get("/api/x")
    async def get_x():
        return {}

    @app2.post("/api/x")
    async def post_x():
        return {}

    assert build_info.compute_api_contract_hash(app1) != build_info.compute_api_contract_hash(app2)


def test_get_build_info_shape():
    app = FastAPI()
    info = build_info.get_build_info(app)
    assert set(info.keys()) == {
        "revision", "revision_short", "started_at", "api_contract", "schema_ledger_max_file",
    }
    expected_revision = build_info._GIT_REVISION  # noqa: SLF001
    expected_started_at = build_info._STARTED_AT.isoformat()  # noqa: SLF001
    assert info["revision"] == expected_revision
    assert info["started_at"] == expected_started_at


def test_build_header_value_format():
    value = build_info.build_header_value()
    rev, _, ts = value.partition("@")
    expected_rev = build_info._GIT_REVISION_SHORT or "unknown"  # noqa: SLF001
    assert rev == expected_rev
    assert ts  # non-empty timestamp component


@pytest.mark.asyncio
async def test_api_build_endpoint_returns_build_info():
    app = FastAPI()

    @app.get("/api/build", include_in_schema=False)
    async def get_build():
        return build_info.get_build_info(app)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        r = await client.get("/api/build")

    assert r.status_code == 200
    body = r.json()
    expected_revision = build_info._GIT_REVISION  # noqa: SLF001
    assert body["revision"] == expected_revision
    assert "api_contract" in body


@pytest.mark.asyncio
async def test_build_header_stamped_on_every_response():
    app = FastAPI()

    @app.get("/anything")
    async def anything():
        return {"ok": True}

    @app.middleware("http")
    async def add_build_header(request, call_next):
        response = await call_next(request)
        response.headers["X-Slomix-Build"] = build_info.build_header_value()
        return response

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        r = await client.get("/anything")

    assert r.status_code == 200
    assert r.headers.get("X-Slomix-Build") == build_info.build_header_value()
