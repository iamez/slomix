"""
Tests for /api/stats/quick-leaders endpoint.

Behaviour locked in:
- Empty data (no recent rounds) returns clean empty arrays without spurious errors
- Primary path returns formatted leaderboard rows
- When primary raises a schema error (SQLite legacy schema lacking round_date),
  the session_date fallback is tried before giving up
- Real DB errors that defeat both primary and fallback propagate to errors[]
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

    Configure return values by setting:
      - xp_rows / xp_session_rows: rows for primary XP query / SQLite session_date fallback
      - dpm_rows / dpm_fallback_rows / dpm_session_rows: rows for the three DPM cascade tiers

    Configure failures by assigning to:
      - fail_xp / fail_xp_fallback
      - fail_dpm / fail_dpm_fallback / fail_dpm_session
    Each is raised the next time the matching query executes.
    """

    def __init__(self):
        self.xp_rows: list[tuple] = []
        self.xp_session_rows: list[tuple] = []
        self.dpm_rows: list[tuple] = []
        self.dpm_fallback_rows: list[tuple] = []
        self.dpm_session_rows: list[tuple] = []
        self.fail_xp: Exception | None = None
        self.fail_xp_fallback: Exception | None = None
        self.fail_dpm: Exception | None = None
        self.fail_dpm_fallback: Exception | None = None
        self.fail_dpm_session: Exception | None = None

    async def fetch_all(self, query: str, params=None) -> list[tuple]:
        q = query.lower()
        # XP queries — both share sum(p.xp) but differ in date column
        if "from player_comprehensive_stats p" in q and "sum(p.xp)" in q:
            if "p.round_date" in q:
                if self.fail_xp:
                    raise self.fail_xp
                return self.xp_rows
            if "p.session_date" in q:
                if self.fail_xp_fallback:
                    raise self.fail_xp_fallback
                return self.xp_session_rows
        # DPM queries — three tiers distinguishable by JOIN / WHERE shape
        if "sum(p.damage_given)" in q:
            if "r.id = p.round_id" in q:  # primary
                if self.fail_dpm:
                    raise self.fail_dpm
                return self.dpm_rows
            if "r.round_date = p.round_date" in q:  # first fallback
                if self.fail_dpm_fallback:
                    raise self.fail_dpm_fallback
                return self.dpm_fallback_rows
            if "p.session_id is not null" in q:  # session-based fallback
                if self.fail_dpm_session:
                    raise self.fail_dpm_session
                return self.dpm_session_rows
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
    """Primary returns no rows -> clean empty payload, no errors."""
    db = FakeQuickLeadersDB()  # everything empty, nothing fails
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
async def test_xp_session_date_fallback_used_when_primary_raises():
    """SQLite-legacy schema: round_date missing -> primary raises, session_date fallback recovers."""
    db = FakeQuickLeadersDB()
    db.fail_xp = RuntimeError("no such column: p.round_date")
    db.xp_session_rows = [
        ("GUID-9", "Legacy", 5000, 2),
    ]
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/stats/quick-leaders")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["xp"]) == 1
        assert body["xp"][0]["guid"] == "GUID-9"
        assert "xp_query_failed" not in body["errors"]


@pytest.mark.asyncio
async def test_xp_errors_when_both_primary_and_fallback_fail():
    """Both XP queries raise -> errors[] flags it, xp[] empty."""
    db = FakeQuickLeadersDB()
    db.fail_xp = RuntimeError("primary down")
    db.fail_xp_fallback = RuntimeError("fallback down too")
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/stats/quick-leaders")
        assert resp.status_code == 200
        body = resp.json()
        assert "xp_query_failed" in body["errors"]
        assert body["xp"] == []


@pytest.mark.asyncio
async def test_dpm_session_fallback_used_when_other_tiers_raise():
    """SQLite legacy DPM path: primary + first fallback fail, session-based wins."""
    db = FakeQuickLeadersDB()
    db.fail_dpm = RuntimeError("no such column: p.round_id")
    db.fail_dpm_fallback = RuntimeError("no such column: p.round_date")
    db.dpm_session_rows = [
        ("GUID-7", "Legacy", 1234.5, 3),
    ]
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/stats/quick-leaders")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["dpm_sessions"]) == 1
        assert body["dpm_sessions"][0]["guid"] == "GUID-7"
        assert "dpm_query_failed" not in body["errors"]


@pytest.mark.asyncio
async def test_dpm_errors_when_all_three_tiers_fail():
    """All DPM tiers raise -> errors[] flags it, dpm_sessions empty."""
    db = FakeQuickLeadersDB()
    db.fail_dpm = RuntimeError("primary lost")
    db.fail_dpm_fallback = RuntimeError("fallback lost")
    db.fail_dpm_session = RuntimeError("session lost")
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/stats/quick-leaders")
        assert resp.status_code == 200
        body = resp.json()
        assert "dpm_query_failed" in body["errors"]
        assert body["dpm_sessions"] == []
