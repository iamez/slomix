"""Router-level tests for /api/storytelling/scopes and the gsid-aware
/api/storytelling/box-score (Codex §5/§8 PR-A).

Locks in the behaviour session_scope.py's resolver gives the BOX endpoint:
- gaming_session_id and an unambiguous session_date both resolve the same
  scope and score
- an ambiguous session_date (>1 gaming session that day) returns 409 with
  candidates instead of silently scoring the wrong session (the old
  `LIMIT 1` bug this PR replaces)
- unknown id/date -> 404, both/neither param -> 422
- every successful box-score response embeds a `scope` metadata block
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from website.backend.dependencies import get_db
from website.backend.routers import storytelling_router


class FakeBoxDB:
    """Routes by SQL fingerprint across session_scope.py + box_scoring_service.py."""

    def __init__(self):
        # date -> list of (gaming_session_id, start_date, end_date, round_count)
        self.gsids_for_date: dict[str, list[tuple]] = {}
        # gsid -> list of (round_start_unix, map_name, round_number, rdate)
        self.scope_rounds_by_gsid: dict[int, list[tuple]] = {}
        # gsid -> list of (id, map_name, round_number, winner_team, defender_team,
        #                   round_outcome, actual_duration_seconds, time_to_beat_seconds)
        self.box_rounds_by_gsid: dict[int, list[tuple]] = {}
        # gsid -> list of (team_name,) rows — BOXScoringService._get_team_names
        # does `r[0] for r in rows`, matching the real adapter's row shape
        # (a bare list[str] here would silently index into each STRING
        # instead, e.g. "Alpha"[0] == "A" — a stub/adapter divergence
        # Copilot review flagged on #524).
        self.team_names_by_gsid: dict[int, list[tuple[str]]] = {}
        # rows for list_recent_scopes
        self.recent_scope_rows: list[tuple] = []

    async def fetch_all(self, query: str, params=None) -> list[tuple]:
        q = " ".join(query.split())
        params = params or ()
        if "STRING_AGG(DISTINCT map_name" in q:
            return self.recent_scope_rows
        if "MIN(SUBSTR(CAST(round_date AS TEXT), 1, 10)) AS start_date" in q:
            return self.gsids_for_date.get(params[0], [])
        if "round_start_unix, map_name, round_number" in q:
            return self.scope_rounds_by_gsid.get(params[0], [])
        if "FROM session_teams" in q:
            return self.team_names_by_gsid.get(params[0], [])
        if "COALESCE(winner_team, 0)" in q:
            return self.box_rounds_by_gsid.get(params[0], [])
        raise AssertionError(f"unexpected query: {q[:100]}")

    async def fetch_one(self, query: str, params=None) -> Any:
        return None


def _build_app(db: FakeBoxDB) -> FastAPI:
    app = FastAPI()

    async def _db_override():
        yield db

    app.dependency_overrides[get_db] = _db_override
    app.include_router(storytelling_router.router, prefix="/api")
    return app


def _scope_rounds(*entries):
    """entries: (round_start_unix, map_name, round_number, rdate)"""
    return list(entries)


def _box_rounds(*entries):
    """entries: (id, map_name, round_number, winner_team, defender_team,
    round_outcome, actual_duration_seconds, time_to_beat_seconds)"""
    return list(entries)


@pytest.mark.asyncio
async def test_box_score_by_gaming_session_id_embeds_scope_metadata():
    db = FakeBoxDB()
    db.scope_rounds_by_gsid[137] = _scope_rounds(
        (1000, "supply", 1, "2026-07-18"),
        (1600, "supply", 2, "2026-07-18"),
    )
    db.box_rounds_by_gsid[137] = _box_rounds(
        (1, "supply", 1, 1, 2, "Fullhold", 300, 0),
        (2, "supply", 2, 2, 1, None, 250, 300),
    )
    db.team_names_by_gsid[137] = [("Alpha",), ("Beta",)]

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/storytelling/box-score", params={"gaming_session_id": 137})

    assert resp.status_code == 200
    body = resp.json()
    assert body["gaming_session_id"] == 137
    # Guards against the FakeBoxDB row-shape regression Copilot flagged: a
    # plain list[str] here would make _get_team_names' `r[0] for r in rows`
    # index into each STRING instead ("Alpha"[0] == "A").
    assert body["alpha_team"] == "Alpha"
    assert body["beta_team"] == "Beta"
    assert body["scope"] == {
        "kind": "gaming_session",
        "version": "gaming-session-v1",
        "gaming_session_id": 137,
        "dates": ["2026-07-18"],
        "accepted_round_count": 2,
        "distinct_map_names": ["supply"],
    }


@pytest.mark.asyncio
async def test_box_score_by_unambiguous_session_date_matches_gsid_result():
    db = FakeBoxDB()
    db.gsids_for_date["2026-07-18"] = [(137, "2026-07-18", "2026-07-18", 2)]
    db.scope_rounds_by_gsid[137] = _scope_rounds(
        (1000, "supply", 1, "2026-07-18"),
        (1600, "supply", 2, "2026-07-18"),
    )
    db.box_rounds_by_gsid[137] = _box_rounds(
        (1, "supply", 1, 1, 2, "Fullhold", 300, 0),
        (2, "supply", 2, 2, 1, None, 250, 300),
    )
    db.team_names_by_gsid[137] = [("Alpha",), ("Beta",)]

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        by_gsid = await client.get("/api/storytelling/box-score", params={"gaming_session_id": 137})
        by_date = await client.get("/api/storytelling/box-score", params={"session_date": "2026-07-18"})

    assert by_gsid.status_code == by_date.status_code == 200
    gsid_body = by_gsid.json()
    date_body = by_date.json()
    assert gsid_body["alpha_score"] == date_body["alpha_score"]
    assert gsid_body["beta_score"] == date_body["beta_score"]
    assert gsid_body["scope"] == date_body["scope"]


@pytest.mark.asyncio
async def test_box_score_ambiguous_date_returns_409_with_candidates():
    """The exact regression this PR fixes: a date with two gaming sessions
    must never silently score just one of them."""
    db = FakeBoxDB()
    db.gsids_for_date["2026-07-18"] = [
        (201, "2026-07-18", "2026-07-18", 12),
        (202, "2026-07-18", "2026-07-18", 8),
    ]

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/storytelling/box-score", params={"session_date": "2026-07-18"})

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["code"] == "AMBIGUOUS_SESSION_DATE"
    assert {c["gaming_session_id"] for c in detail["candidates"]} == {201, 202}


@pytest.mark.asyncio
async def test_box_score_unknown_gaming_session_id_is_404():
    db = FakeBoxDB()

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/storytelling/box-score", params={"gaming_session_id": 9999})

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_box_score_both_params_supplied_is_422():
    db = FakeBoxDB()

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(
            "/api/storytelling/box-score",
            params={"gaming_session_id": 137, "session_date": "2026-07-18"},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_box_score_neither_param_supplied_is_422():
    db = FakeBoxDB()

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/storytelling/box-score")

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_box_score_both_params_with_malformed_date_is_422_not_400():
    """Copilot review on #524: the 'exactly one of' check must run BEFORE
    date parsing, so a malformed date alongside gaming_session_id still
    surfaces as the real contract violation (422 - both provided), instead
    of a 400 from date-parsing that masks it."""
    db = FakeBoxDB()

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(
            "/api/storytelling/box-score",
            params={"gaming_session_id": 137, "session_date": "not-a-date"},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_box_score_invalid_date_format_is_400_before_scope_resolution():
    db = FakeBoxDB()

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/storytelling/box-score", params={"session_date": "18-07-2026"})

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_storytelling_scopes_returns_scope_version_and_sessions():
    db = FakeBoxDB()
    db.recent_scope_rows = [
        (137, "2026-07-18", "2026-07-19", 23, "radar, supply"),
        (136, "2026-07-11", "2026-07-11", 6, "goldrush"),
    ]

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/storytelling/scopes")

    assert resp.status_code == 200
    body = resp.json()
    assert body["scope_version"] == "gaming-session-v1"
    assert len(body["sessions"]) == 2
    first = body["sessions"][0]
    assert first["gaming_session_id"] == 137
    assert first["accepted_round_count"] == 23
    assert first["distinct_map_names"] == ["radar", "supply"]
    assert first["scope_version"] == "gaming-session-v1"


@pytest.mark.asyncio
async def test_storytelling_scopes_respects_limit_param():
    db = FakeBoxDB()
    db.recent_scope_rows = [(1, "2026-07-01", "2026-07-01", 4, "supply")]

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/storytelling/scopes", params={"limit": 5})

    assert resp.status_code == 200
    assert resp.json()["sessions"][0]["gaming_session_id"] == 1


@pytest.mark.asyncio
async def test_storytelling_scopes_rejects_out_of_range_limit():
    db = FakeBoxDB()

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/storytelling/scopes", params={"limit": 500})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_storytelling_scopes_returns_503_on_sqlite_backend():
    """Copilot review on #524: STRING_AGG is PostgreSQL-only. SQLite (the
    local dev fallback) must fail loudly with 503, never silently return an
    empty/wrong session list (D4 — degraded, never a silent fallback)."""
    db = FakeBoxDB()
    db.db_path = "/tmp/local-dev.sqlite3"  # duck-typed SQLite marker

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/storytelling/scopes")

    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "SCOPE_BACKEND_UNSUPPORTED"
