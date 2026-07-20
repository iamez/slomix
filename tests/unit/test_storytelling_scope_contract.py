"""Contract test: every session_date-scoped storytelling panel accepts
gaming_session_id (Codex §5/§8 SS-C) and embeds a `scope` metadata block.

All 15 panels below were converted from a bare, required `session_date`
Query param to the shared `resolve_story_scope` dependency (SS-A's
GamingSessionScope resolver). This enumerates every one of them so a
future endpoint added to storytelling_router.py without the shared
dependency — or an accidental regression back to session_date-only —
fails a test instead of silently reintroducing the ambiguous-date bug
this whole program exists to close.

Deliberately NOT covered here: the underlying per-panel SQL still queries
a SINGLE representative date (scope.dates[0]), not the full multi-date
scope compute_session_kis_for_gsid (SS-B) uses — see resolve_story_scope's
docstring. This test only proves the ROUTE CONTRACT (gsid-addressable,
ambiguous-date-safe, scope metadata present), not per-panel multi-date
data completeness.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from website.backend.dependencies import get_db, get_internal_request_mode
from website.backend.routers import storytelling_router


class _ContractFakeDB:
    """Resolves gaming_session_id=137 OR session_date=2026-07-18 to the
    exact same single-round scope; returns [] for every other query
    (best-lives / kill-impact-details' raw SQL, any service-internal
    query the monkeypatched StorytellingService below doesn't need)."""

    def __init__(self):
        self._requested_date: str | None = None

    async def fetch_all(self, query, params=None):
        q = " ".join(str(query).split())
        if "MIN(SUBSTR(CAST(round_date AS TEXT), 1, 10)) AS start_date" in q:
            self._requested_date = params[0]
            return [(137, params[0], params[0], 1)]
        if "round_start_unix, map_name, round_number" in q and "FROM rounds" in q:
            rdate = self._requested_date or "2026-07-18"
            return [(1_700_000_000, "supply", 1, rdate)]
        return []

    async def fetch_one(self, query, params=None):
        return None


class _FakeStorytellingService:
    """Every service method the 15 contract-tested panels call, returning
    the minimal shape each router endpoint needs (some add "scope" onto
    the dict afterward, so the dict must be mutable — not frozen)."""

    def __init__(self, db):
        self.db = db

    async def detect_moments(self, sd, limit=10):
        return []

    async def kis_compute_with_shadow(self, sd):
        return {"status": "read_only"}

    async def get_kis_leaderboard(self, sd, limit=20):
        return []

    async def compute_team_synergy(self, sd):
        return {"status": "ok", "session_date": str(sd)}

    async def compute_win_contribution(self, session_date):
        return {"session_date": str(session_date), "mvp": None, "players": []}

    async def compute_momentum(self, sd):
        return {"status": "ok", "session_date": str(sd), "rounds": []}

    async def compute_momentum_session(self, sd):
        return {"status": "ok", "session_date": str(sd), "points": []}

    async def generate_narrative(self, sd, *, ensure_kis=True):
        return {"status": "ok", "session_date": str(sd), "narrative": "story"}

    async def compute_gravity(self, sd):
        return {"status": "ok", "session_date": str(sd), "players": []}

    async def compute_space_created(self, sd):
        return {"status": "ok", "session_date": str(sd), "players": []}

    async def compute_enabler(self, sd):
        return {"status": "ok", "session_date": str(sd), "players": []}

    async def compute_lurker_profile(self, sd):
        return {"status": "ok", "session_date": str(sd), "players": []}

    async def compute_useless_defense_deaths(self, sd, *, min_killer_health=80, min_reinf_seconds=25):
        return {"status": "ok", "session_date": str(sd), "players": []}

    async def generate_player_narratives(self, sd, *, ensure_kis=True):
        return {"status": "ok", "session_date": str(sd), "player_narratives": []}


# (path, extra required query params beyond session_date/gaming_session_id)
_CONTRACT_ENDPOINTS: list[tuple[str, dict]] = [
    ("/api/storytelling/moments", {}),
    ("/api/storytelling/best-lives", {}),
    ("/api/storytelling/kill-impact", {}),
    ("/api/storytelling/kill-impact/details", {"player_guid": "ABC12345"}),
    ("/api/storytelling/synergy", {}),
    ("/api/storytelling/win-contribution", {}),
    ("/api/storytelling/momentum", {}),
    ("/api/storytelling/momentum-session", {}),
    ("/api/storytelling/narrative", {}),
    ("/api/storytelling/gravity", {}),
    ("/api/storytelling/space-created", {}),
    ("/api/storytelling/enabler", {}),
    ("/api/storytelling/lurker-profile", {}),
    ("/api/storytelling/useless-defense-deaths", {}),
    ("/api/storytelling/player-narratives", {}),
]


def _build_app(db):
    app = FastAPI()

    async def _db_override():
        return db

    async def _internal_mode_override():
        return False

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_internal_request_mode] = _internal_mode_override
    app.include_router(storytelling_router.router, prefix="/api")
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize("path,extra_params", _CONTRACT_ENDPOINTS)
async def test_panel_accepts_gaming_session_id_and_embeds_scope(monkeypatch, path, extra_params):
    monkeypatch.setattr(storytelling_router, "StorytellingService", _FakeStorytellingService)
    db = _ContractFakeDB()
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(path, params={"gaming_session_id": 137, **extra_params})

    assert resp.status_code == 200, f"{path} -> {resp.status_code}: {resp.text[:300]}"
    body = resp.json()
    assert "scope" in body, f"{path} response missing 'scope' metadata block"
    assert body["scope"]["gaming_session_id"] == 137
    assert body["scope"]["version"] == "gaming-session-v1"


@pytest.mark.asyncio
@pytest.mark.parametrize("path,extra_params", _CONTRACT_ENDPOINTS)
async def test_panel_accepts_legacy_session_date(monkeypatch, path, extra_params):
    """The legacy session_date query param must keep working unchanged for
    existing callers that haven't migrated to gaming_session_id yet."""
    monkeypatch.setattr(storytelling_router, "StorytellingService", _FakeStorytellingService)
    db = _ContractFakeDB()
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(path, params={"session_date": "2026-07-18", **extra_params})

    assert resp.status_code == 200, f"{path} -> {resp.status_code}: {resp.text[:300]}"
    assert "scope" in resp.json()


@pytest.mark.asyncio
async def test_panel_both_params_is_422():
    db = _ContractFakeDB()
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(
            "/api/storytelling/momentum",
            params={"session_date": "2026-07-18", "gaming_session_id": 137},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_panel_both_params_with_malformed_date_is_422_not_400():
    """The 'exactly one of' check must run BEFORE date parsing, so a
    malformed date alongside gaming_session_id still surfaces as the real
    contract violation (422), not a 400 that masks it (Copilot review)."""
    db = _ContractFakeDB()
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(
            "/api/storytelling/momentum",
            params={"session_date": "not-a-date", "gaming_session_id": 137},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_panel_neither_param_is_422():
    db = _ContractFakeDB()
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/storytelling/momentum")
    assert resp.status_code == 422


class _AmbiguousDateFakeDB:
    """A date matching TWO gaming sessions — every panel must 409, never
    silently pick one (the same regression class SS-A's BOX score fixed)."""

    async def fetch_all(self, query, params=None):
        q = " ".join(str(query).split())
        if "MIN(SUBSTR(CAST(round_date AS TEXT), 1, 10)) AS start_date" in q:
            return [
                (201, params[0], params[0], 5),
                (202, params[0], params[0], 3),
            ]
        return []

    async def fetch_one(self, query, params=None):
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize("path,extra_params", _CONTRACT_ENDPOINTS)
async def test_panel_ambiguous_date_is_409_with_candidates(monkeypatch, path, extra_params):
    monkeypatch.setattr(storytelling_router, "StorytellingService", _FakeStorytellingService)
    db = _AmbiguousDateFakeDB()
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(path, params={"session_date": "2026-07-18", **extra_params})

    assert resp.status_code == 409, f"{path} -> {resp.status_code}: {resp.text[:300]}"
    detail = resp.json()["detail"]
    assert detail["code"] == "AMBIGUOUS_SESSION_DATE"
    assert {c["gaming_session_id"] for c in detail["candidates"]} == {201, 202}
