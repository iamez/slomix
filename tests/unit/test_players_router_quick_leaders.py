"""
Tests for /api/stats/quick-leaders endpoint.

Regression coverage for the dead `session_date`/`session_id` fallback queries
removed in May 2026. Ensures:
- Empty data (no recent rounds) returns clean empty arrays without spurious errors
- Primary path returns formatted leaderboard rows
- Real DB errors propagate to errors[] (not silenced)
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from website.backend.dependencies import get_db
from website.backend.routers import players_router


class FakeQuickLeadersDB:
    """
    Minimal DB stub. Routes queries by substring match.

    Configure return values by setting xp_rows / dpm_rows attributes; configure
    failures by assigning to fail_xp / fail_dpm / fail_dpm_fallback (raised the
    next time the matching query is executed).
    """

    def __init__(self):
        self.xp_rows: list[tuple] = []
        self.dpm_rows: list[tuple] = []
        self.fail_xp: Exception | None = None
        self.fail_dpm: Exception | None = None
        self.fail_dpm_fallback: Exception | None = None

    async def fetch_all(self, query: str, params=None) -> list[tuple]:
        q = query.lower()
        if "from player_comprehensive_stats p" in q and "sum(p.xp)" in q:
            if self.fail_xp:
                raise self.fail_xp
            return self.xp_rows
        if "from player_comprehensive_stats p" in q and "sum(p.damage_given)" in q:
            # Distinguish primary (uses r.id = p.round_id) vs fallback
            # (uses r.round_date = p.round_date)
            if "r.id = p.round_id" in q:
                if self.fail_dpm:
                    raise self.fail_dpm
                return self.dpm_rows
            if "r.round_date = p.round_date" in q:
                if self.fail_dpm_fallback:
                    raise self.fail_dpm_fallback
                return []
        # batch_resolve_display_names
        if "from player_links" in q or "from player_aliases" in q:
            return []
        return []

    async def fetch_one(self, query: str, params=None) -> Any:
        return None


def _build_app(db: FakeQuickLeadersDB) -> FastAPI:
    app = FastAPI()

    async def _db_override():
        yield db

    app.dependency_overrides[get_db] = _db_override
    app.include_router(players_router.router, prefix="/api")
    return app


@pytest.mark.asyncio
async def test_returns_empty_arrays_when_no_recent_data():
    """Primary query returns no rows -> clean empty payload, no errors."""
    db = FakeQuickLeadersDB()  # all queues empty
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/stats/quick-leaders")
        assert resp.status_code == 200
        body = resp.json()
        assert body["xp"] == []
        assert body["dpm_sessions"] == []
        assert body["errors"] == []


@pytest.mark.asyncio
async def test_returns_xp_leaders_when_primary_succeeds():
    """Primary XP query returns rows -> formatted leaderboard, no errors."""
    db = FakeQuickLeadersDB()
    db.xp_rows = [
        ("GUID-1", "Alpha", 10000, 5),
        ("GUID-2", "Beta", 8000, 4),
        ("GUID-3", "Gamma", 6000, 3),
    ]
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/stats/quick-leaders")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["xp"]) == 3
        assert body["xp"][0]["rank"] == 1
        assert body["xp"][0]["guid"] == "GUID-1"
        assert body["xp"][0]["value"] == 10000
        assert body["xp"][0]["rounds"] == 5
        assert body["xp"][0]["label"] == "XP"
        assert body["errors"] == []


@pytest.mark.asyncio
async def test_real_db_error_propagates_to_errors_field():
    """When BOTH primary and fallback DPM queries raise, errors[] flags it."""
    db = FakeQuickLeadersDB()
    db.fail_dpm = RuntimeError("connection lost")
    db.fail_dpm_fallback = RuntimeError("still lost")
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/stats/quick-leaders")
        assert resp.status_code == 200
        body = resp.json()
        assert "dpm_query_failed" in body["errors"]
        assert body["dpm_sessions"] == []


@pytest.mark.asyncio
async def test_xp_query_failure_propagates_to_errors_field():
    """When primary XP query raises, errors[] flags it (no dead fallback)."""
    db = FakeQuickLeadersDB()
    db.fail_xp = RuntimeError("undefined column foo")
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/stats/quick-leaders")
        assert resp.status_code == 200
        body = resp.json()
        assert "xp_query_failed" in body["errors"]
        assert body["xp"] == []
