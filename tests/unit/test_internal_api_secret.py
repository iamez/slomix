from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from website.backend.dependencies import get_db
from website.backend.routers import skill_router, storytelling_router

SECRET = "test-internal-secret"  # noqa: S105 - test-only shared secret


def _skill_app(db_calls: list[str]):
    app = FastAPI()

    async def _db_override():
        db_calls.append("db")
        return object()

    app.dependency_overrides[get_db] = _db_override
    app.include_router(skill_router.router, prefix="/api")
    return app


@pytest.mark.asyncio
async def test_s_effort_requires_internal_header_before_db(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_SECRET", SECRET)
    db_calls: list[str] = []
    transport = httpx.ASGITransport(app=_skill_app(db_calls))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/skill/s-effort?session_date=2026-07-07")

    assert resp.status_code == 401
    assert db_calls == []


@pytest.mark.asyncio
async def test_s_effort_accepts_valid_internal_header(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_SECRET", SECRET)
    calls: list[tuple] = []

    class _FakeSEffortService:
        def __init__(self, db):
            calls.append(("init", db))

        async def compute_session(self, session_date):
            calls.append(("compute", session_date))
            return [{
                "player_guid": "ABC12345",
                "name": "vid",
                "session_rating": 0.7,
                "s_performance": 1.2,
            }]

        async def persist_session(self, session_date, rows=None):
            calls.append(("persist", session_date, rows))
            return len(rows or [])

    monkeypatch.setattr(
        "website.backend.services.s_effort_service.SEffortService",
        _FakeSEffortService,
    )
    db_calls: list[str] = []
    transport = httpx.ASGITransport(app=_skill_app(db_calls))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/skill/s-effort?session_date=2026-07-07",
            headers={"X-Internal-Token": SECRET},
        )

    assert resp.status_code == 200
    assert resp.json()["available"] is True
    assert db_calls == ["db"]
    assert [c[0] for c in calls] == ["init", "compute", "persist"]


def _story_app(db_calls: list[str]):
    app = FastAPI()

    async def _db_override():
        db_calls.append("db")
        return object()

    app.dependency_overrides[get_db] = _db_override
    app.include_router(storytelling_router.router, prefix="/api")
    return app


@pytest.mark.asyncio
async def test_public_kill_impact_is_read_only(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_SECRET", SECRET)
    calls: list[tuple] = []

    class _FakeStorytellingService:
        def __init__(self, db):
            calls.append(("init", db))

        async def kis_compute_with_shadow(self, sd):
            calls.append(("compute", str(sd)))
            return {"status": "computed"}

        async def get_kis_leaderboard(self, sd, limit=20):
            calls.append(("leaderboard", str(sd), limit))
            return [{"guid": "ABC12345", "name": "vid", "kills": 2, "total_kis": 4.5}]

    monkeypatch.setattr(storytelling_router, "StorytellingService", _FakeStorytellingService)
    db_calls: list[str] = []
    transport = httpx.ASGITransport(app=_story_app(db_calls))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/storytelling/kill-impact?session_date=2026-07-07")

    assert resp.status_code == 200
    assert resp.json()["compute"] == {"status": "read_only"}
    assert [c[0] for c in calls] == ["init", "leaderboard"]
    assert db_calls == ["db"]


@pytest.mark.asyncio
async def test_internal_kill_impact_runs_compute(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_SECRET", SECRET)
    calls: list[tuple] = []

    class _FakeStorytellingService:
        def __init__(self, db):
            calls.append(("init", db))

        async def kis_compute_with_shadow(self, sd):
            calls.append(("compute", str(sd)))
            return {"status": "computed"}

        async def get_kis_leaderboard(self, sd, limit=20):
            calls.append(("leaderboard", str(sd), limit))
            return [{"guid": "ABC12345", "name": "vid", "kills": 2, "total_kis": 4.5}]

    monkeypatch.setattr(storytelling_router, "StorytellingService", _FakeStorytellingService)
    db_calls: list[str] = []
    transport = httpx.ASGITransport(app=_story_app(db_calls))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/storytelling/kill-impact?session_date=2026-07-07",
            headers={"X-Internal-Token": SECRET},
        )

    assert resp.status_code == 200
    assert resp.json()["compute"] == {"status": "computed"}
    assert [c[0] for c in calls] == ["init", "compute", "leaderboard"]


@pytest.mark.asyncio
async def test_wrong_internal_token_rejects_before_db(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_SECRET", SECRET)
    db_calls: list[str] = []
    transport = httpx.ASGITransport(app=_story_app(db_calls))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/storytelling/kill-impact?session_date=2026-07-07",
            headers={"X-Internal-Token": "wrong"},
        )

    assert resp.status_code == 401
    assert db_calls == []


@pytest.mark.asyncio
async def test_public_narrative_routes_do_not_ensure_kis(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_SECRET", SECRET)
    calls: list[tuple] = []

    class _FakeStorytellingService:
        def __init__(self, db):
            calls.append(("init", db))

        async def generate_narrative(self, sd, *, ensure_kis=True):
            calls.append(("narrative", str(sd), ensure_kis))
            return {"status": "ok", "narrative": "cached story"}

        async def generate_player_narratives(self, sd, *, ensure_kis=True):
            calls.append(("player_narratives", str(sd), ensure_kis))
            return {"status": "ok", "player_narratives": []}

    monkeypatch.setattr(storytelling_router, "StorytellingService", _FakeStorytellingService)
    db_calls: list[str] = []
    transport = httpx.ASGITransport(app=_story_app(db_calls))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        narrative = await client.get("/api/storytelling/narrative?session_date=2026-07-07")
        player_narratives = await client.get(
            "/api/storytelling/player-narratives?session_date=2026-07-07"
        )

    assert narrative.status_code == 200
    assert player_narratives.status_code == 200
    assert calls[1] == ("narrative", "2026-07-07", False)
    assert calls[3] == ("player_narratives", "2026-07-07", False)
