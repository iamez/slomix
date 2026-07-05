"""Unit tests for GET /api/proximity/push-deaths/heatmap ("where pushes die",
proximity productization slice 2). FakeDB pattern per test_proximity_player_heatmap.py.
"""

import httpx
import pytest
from fastapi import FastAPI

from website.backend.dependencies import get_db
from website.backend.routers import proximity_positions as pp_router


class FakePushDeathsDB:
    def __init__(self, *, push_rows=None, carrier_rows=None):
        self.push_rows = push_rows if push_rows is not None else []
        self.carrier_rows = carrier_rows if carrier_rows is not None else []
        self.push_sql = ""
        self.carrier_sql = ""

    @staticmethod
    def _norm(q: str) -> str:
        return " ".join(q.strip().lower().split())

    async def fetch_all(self, query: str, params=None):
        n = self._norm(query)
        if "proximity_team_push" in n:
            self.push_sql = n
            return list(self.push_rows)
        if "proximity_carrier_kill" in n:
            self.carrier_sql = n
            return list(self.carrier_rows)
        raise AssertionError(f"Unexpected fetch_all: {n}")


def _build_app(db) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db
    app.include_router(pp_router.router, prefix="/api")
    return app


async def _get(db, params):
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/api/proximity/push-deaths/heatmap", params=params)


@pytest.mark.asyncio
async def test_map_name_required():
    resp = await _get(FakePushDeathsDB(), {})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_merges_push_and_carrier_sources_per_cell():
    db = FakePushDeathsDB(
        push_rows=[(1, 2, 10), (0, 0, 3)],
        carrier_rows=[(1, 2, 4), (5, 5, 1)],  # (1,2) overlaps a push cell
    )
    resp = await _get(db, {"map_name": "sw_goldrush_te"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["grid_size"] == 512
    assert body["perspective"] == "pushes"
    zones = {(z["x"], z["y"]): z["count"] for z in body["hotzones"]}
    assert zones[(1, 2)] == 14  # 10 push + 4 carrier summed in one cell
    assert zones[(0, 0)] == 3
    assert zones[(5, 5)] == 1
    # sorted by count desc
    counts = [z["count"] for z in body["hotzones"]]
    assert counts == sorted(counts, reverse=True)
    assert body["push_death_cells"] == 2
    assert body["carrier_death_cells"] == 2


@pytest.mark.asyncio
async def test_push_query_excludes_non_objective_pushes_and_scopes_map():
    db = FakePushDeathsDB()
    resp = await _get(db, {"map_name": "supply", "session_date": "2026-06-30"})
    assert resp.status_code == 200
    assert "not in ('no', 'n/a', '')" in db.push_sql
    assert "tp.map_name" in db.push_sql
    assert "tp.session_date" in db.push_sql
    # carrier source scoped the same way
    assert "ck.map_name" in db.carrier_sql
    assert "abs(cp.event_time - ck.kill_time) <= 1500" in db.carrier_sql


@pytest.mark.asyncio
async def test_empty_sources_return_ok_with_no_zones():
    resp = await _get(FakePushDeathsDB(), {"map_name": "supply"})
    assert resp.status_code == 200
    assert resp.json()["hotzones"] == []
