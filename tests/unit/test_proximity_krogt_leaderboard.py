"""Unit tests for /api/proximity/leaderboards?category=krogt (per-life KROGT).

FakeDB dispatches on table name, per the test_proximity_player_heatmap.py
ASGITransport pattern. Algorithm mirrors scripts/backtest_krogt_perlife.py.
"""

import httpx
import pytest
from fastapi import FastAPI

from website.backend.dependencies import get_db
from website.backend.routers import proximity_scoring as ps_router

G1 = "AAAA1111"
G2 = "BBBB2222"


class FakeKrogtDB:
    """lives: (round_id, guid8, name, spawn_ms, death_ms); events: (round_id, guid8, t)."""

    def __init__(self, *, lives=None, kills=None, revives=None, objectives=None,
                 gibs=None, traded=None):
        self.lives = lives or []
        self.kills = kills or []
        self.revives = revives or []
        self.objectives = objectives or []
        self.gibs = gibs or []
        self.traded = traded or []
        self.lives_sql = ""
        self.lives_params = ()

    async def fetch_all(self, query: str, params=None):
        n = " ".join(query.strip().lower().split())
        if "from player_track" in n:
            self.lives_sql = n
            self.lives_params = tuple(params or ())
            return list(self.lives)
        if "from proximity_combat_position" in n:
            return list(self.kills)
        if "from proximity_revive" in n:
            return list(self.revives)
        if "from proximity_objective_run" in n:
            return list(self.objectives)
        if "from proximity_kill_outcome" in n:
            return list(self.gibs)
        if "from proximity_lua_trade_kill" in n:
            return list(self.traded)
        raise AssertionError(f"Unexpected fetch_all: {n}")


def _app(db) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db
    app.include_router(ps_router.router, prefix="/api")
    return app


async def _get(db, params):
    transport = httpx.ASGITransport(app=_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/api/proximity/leaderboards", params=params)


@pytest.mark.asyncio
async def test_krogt_counts_contributing_lives_only():
    db = FakeKrogtDB(
        lives=[
            # G1: 10 lives, a kill only inside the first window
            *[(7, G1, "PlayerOne", i * 1000, i * 1000 + 900) for i in range(10)],
            # G2: 10 lives, no events at all
            *[(7, G2, "PlayerTwo", i * 1000, i * 1000 + 900) for i in range(10)],
        ],
        kills=[(7, G1, 500)],
    )
    resp = await _get(db, {"category": "krogt", "session_date": "2026-06-30"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "krogt"
    by_guid = {e["guid"]: e for e in body["entries"]}
    assert by_guid[G1]["value"] == 10.0  # 1 of 10 lives contributed
    assert by_guid[G1]["lives"] == 10
    assert by_guid[G2]["value"] == 0.0
    assert body["entries"][0]["guid"] == G1  # sorted desc


@pytest.mark.asyncio
async def test_traded_death_credits_the_life_that_ended():
    # One life (0..5000); no direct events, but the ending death was traded at 5400 (+/-1s)
    db = FakeKrogtDB(
        lives=[(7, G1, "PlayerOne", i * 10000, i * 10000 + 5000) for i in range(10)],
        traded=[(7, G1, 5400)],
    )
    resp = await _get(db, {"category": "krogt", "session_date": "2026-06-30"})
    entry = resp.json()["entries"][0]
    assert entry["value"] == 10.0  # exactly the first life credited via trade


@pytest.mark.asyncio
async def test_min_lives_cutoff_scoped():
    db = FakeKrogtDB(lives=[(7, G1, "PlayerOne", 0, 900)])  # 1 life < 10 cutoff
    resp = await _get(db, {"category": "krogt", "session_date": "2026-06-30"})
    assert resp.json()["entries"] == []


@pytest.mark.asyncio
async def test_round_start_unix_scopes_the_queries():
    """Fully scoped round (same map+round_number twice in a session) must not
    aggregate both rounds (codex P2, PR #442)."""
    db = FakeKrogtDB()
    resp = await _get(db, {
        "category": "krogt", "session_date": "2026-06-30",
        "map_name": "supply", "round_number": 1, "round_start_unix": 1751300000,
    })
    assert resp.status_code == 200
    assert "pt.round_start_unix = $" in db.lives_sql
    assert 1751300000 in db.lives_params


@pytest.mark.asyncio
async def test_empty_lives_is_ok():
    resp = await _get(FakeKrogtDB(), {"category": "krogt"})
    assert resp.status_code == 200
    assert resp.json()["entries"] == []
