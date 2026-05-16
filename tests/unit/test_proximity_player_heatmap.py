"""Unit tests for GET /api/proximity/player-heatmap (Phase 2 of the proximity
redesign). Covers param validation, mode->column routing, GUID short->canonical
resolution, presence stride downsampling, grid_size clamp, and response shape.

DB is faked (no PostgreSQL) following the tests/unit/test_availability_router.py
ASGITransport + dependency_overrides[get_db] pattern.
"""

import httpx
import pytest
from fastapi import FastAPI

from website.backend.dependencies import get_db
from website.backend.routers import proximity_positions as pp_router

CANON = "652EB4A6311DBD8BD18E14CE9840EB1E"  # 32-char canonical
SHORT = "652EB4A6"  # 8-char prefix


class FakeHeatmapDB:
    """Pattern-matches the few queries the endpoint issues."""

    def __init__(self, *, total_samples: int = 0, grid_rows=None):
        self.total_samples = total_samples
        self.grid_rows = grid_rows if grid_rows is not None else [(1, 2, 10), (-3, 4, 5)]
        self.last_grid_sql = ""
        self.last_grid_params = ()
        self.resolver_called = False

    @staticmethod
    def _norm(q: str) -> str:
        return " ".join(q.strip().lower().split())

    async def fetch_val(self, query: str, params=None):
        n = self._norm(query)
        # GUID short->canonical resolution
        if "left(" in n and "limit 1" in n:
            self.resolver_called = True
            return CANON
        # presence: COALESCE(SUM(sample_count),0)
        if "sum(sample_count)" in n:
            return self.total_samples
        raise AssertionError(f"Unexpected fetch_val: {n}")

    async def fetch_all(self, query: str, params=None):
        n = self._norm(query)
        # _load_scoped_guid_name_map
        if "max(player_name)" in n and "group by player_guid" in n:
            return [(CANON, "TestPlayer")]
        # the grid query (combat or presence)
        if "floor(" in n and "count(*) as cnt" in n:
            self.last_grid_sql = n
            self.last_grid_params = tuple(params or ())
            return list(self.grid_rows)
        raise AssertionError(f"Unexpected fetch_all: {n}")


def _build_app(db) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db
    app.include_router(pp_router.router, prefix="/api")
    return app


async def _get(db, params):
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/api/proximity/player-heatmap", params=params)


# ---- param validation ------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_map_name_returns_400():
    r = await _get(FakeHeatmapDB(), {"mode": "kills_from", "player_guid": SHORT})
    assert r.status_code == 400
    assert "map_name" in r.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_mode_returns_400():
    r = await _get(FakeHeatmapDB(), {"map_name": "supply", "mode": "bogus", "player_guid": SHORT})
    assert r.status_code == 400
    assert "mode must be one of" in r.json()["detail"]


@pytest.mark.asyncio
async def test_missing_player_guid_returns_400():
    r = await _get(FakeHeatmapDB(), {"map_name": "supply", "mode": "kills_from"})
    assert r.status_code == 400
    assert "player_guid" in r.json()["detail"]


# ---- mode -> column routing -----------------------------------------------

@pytest.mark.asyncio
async def test_kills_from_uses_attacker_coords_and_filter():
    db = FakeHeatmapDB()
    r = await _get(db, {"map_name": "supply", "mode": "kills_from", "player_guid": SHORT})
    assert r.status_code == 200
    sql = db.last_grid_sql
    assert "floor(attacker_x" in sql and "floor(attacker_y" in sql
    assert "from proximity_combat_position" in sql
    assert "attacker_guid = $" in sql


@pytest.mark.asyncio
async def test_victims_die_uses_victim_coords_attacker_filter():
    db = FakeHeatmapDB()
    r = await _get(db, {"map_name": "supply", "mode": "victims_die", "player_guid": SHORT})
    assert r.status_code == 200
    sql = db.last_grid_sql
    assert "floor(victim_x" in sql and "floor(victim_y" in sql
    assert "attacker_guid = $" in sql
    assert "coverage" not in r.json()


@pytest.mark.asyncio
async def test_player_dies_filters_victim_guid_and_sets_coverage():
    db = FakeHeatmapDB()
    r = await _get(db, {"map_name": "supply", "mode": "player_dies", "player_guid": SHORT})
    assert r.status_code == 200
    body = r.json()
    sql = db.last_grid_sql
    assert "floor(victim_x" in sql
    assert "victim_guid = $" in sql
    assert body["coverage"] == "kills_only"


@pytest.mark.asyncio
async def test_aim_mode_routes_to_proximity_shot_fired():
    """v9 true-aim mode=aim -> proximity_shot_fired origin_x/origin_y,
    filtered by guid. (Empty in prod until Lua feature deployed.)"""
    db = FakeHeatmapDB()
    r = await _get(db, {"map_name": "supply", "mode": "aim", "player_guid": SHORT})
    assert r.status_code == 200
    sql = db.last_grid_sql
    assert "floor(origin_x" in sql and "floor(origin_y" in sql
    assert "from proximity_shot_fired" in sql
    assert "guid = $" in sql
    assert r.json()["mode"] == "aim"


@pytest.mark.asyncio
async def test_presence_uses_player_track_lateral():
    db = FakeHeatmapDB(total_samples=500)
    r = await _get(db, {"map_name": "supply", "mode": "presence", "player_guid": SHORT})
    assert r.status_code == 200
    sql = db.last_grid_sql
    assert "jsonb_array_elements" in sql and "with ordinality" in sql
    assert "player_guid = $" in sql
    assert r.json()["sampled"] is False  # 500 samples -> stride 1


# ---- presence stride math --------------------------------------------------

@pytest.mark.asyncio
async def test_presence_stride_downsamples_when_large():
    db = FakeHeatmapDB(total_samples=24000)  # ceil(24000/8000) = 3
    r = await _get(db, {"map_name": "supply", "mode": "presence", "player_guid": SHORT})
    assert r.status_code == 200
    assert "% 3) = 0" in db.last_grid_sql
    assert r.json()["sampled"] is True


@pytest.mark.asyncio
async def test_presence_stride_one_when_small():
    db = FakeHeatmapDB(total_samples=8000)  # ceil(8000/8000) = 1
    r = await _get(db, {"map_name": "supply", "mode": "presence", "player_guid": SHORT})
    assert r.status_code == 200
    assert "% 1) = 0" in db.last_grid_sql
    assert r.json()["sampled"] is False


# ---- GUID resolution -------------------------------------------------------

@pytest.mark.asyncio
async def test_short_guid_resolved_to_canonical():
    db = FakeHeatmapDB()
    r = await _get(db, {"map_name": "supply", "mode": "kills_from", "player_guid": SHORT})
    assert r.status_code == 200
    assert db.resolver_called is True
    assert r.json()["player_guid"] == CANON


@pytest.mark.asyncio
async def test_canonical_guid_skips_resolver():
    db = FakeHeatmapDB()
    r = await _get(db, {"map_name": "supply", "mode": "kills_from", "player_guid": CANON})
    assert r.status_code == 200
    assert db.resolver_called is False
    assert r.json()["player_guid"] == CANON


# ---- response shape + grid clamp ------------------------------------------

@pytest.mark.asyncio
async def test_response_shape_and_total():
    db = FakeHeatmapDB(grid_rows=[(1, 2, 10), (-3, 4, 5)])
    r = await _get(db, {"map_name": "supply", "mode": "kills_from", "player_guid": SHORT})
    body = r.json()
    assert body["status"] == "ok"
    assert body["mode"] == "kills_from"
    assert body["map_name"] == "supply"
    assert body["player_name"] == "TestPlayer"
    assert body["hotzones"] == [
        {"x": 1, "y": 2, "count": 10},
        {"x": -3, "y": 4, "count": 5},
    ]
    assert body["total"] == 15
    assert body["sampled"] is False


@pytest.mark.asyncio
async def test_grid_size_clamped_low_and_high():
    db = FakeHeatmapDB()
    r_lo = await _get(db, {"map_name": "supply", "mode": "kills_from", "player_guid": SHORT, "grid_size": 16})
    assert r_lo.json()["grid_size"] == 128
    r_hi = await _get(db, {"map_name": "supply", "mode": "kills_from", "player_guid": SHORT, "grid_size": 99999})
    assert r_hi.json()["grid_size"] == 1024
