"""Unit tests for GET /api/proximity/player-aim (Full Aim Analytics, Phase 1).

The headline coverage is the wrap-safe circular statistics — an arithmetic
mean of yaw is silently wrong (170 and -170 average to 0, true mean ~180), so
those helpers are tested directly without a DB. Endpoint tests fake the DB
following the test_proximity_player_heatmap.py ASGITransport pattern.
"""

import math

import httpx
import pytest
from fastapi import FastAPI

from website.backend.dependencies import get_db
from website.backend.routers import proximity_positions as pp

CANON = "652EB4A6311DBD8BD18E14CE9840EB1E"
SHORT = "652EB4A6"


# ============================================================
# Pure helpers — circular statistics correctness (no DB)
# ============================================================

def test_circular_mean_handles_wraparound_not_arithmetic():
    # 170 and -170: arithmetic mean = 0 (WRONG); circular mean ~ +/-180.
    s = math.sin(math.radians(170)) + math.sin(math.radians(-170))
    c = math.cos(math.radians(170)) + math.cos(math.radians(-170))
    st = pp._circular_yaw_stats(s / 2.0, c / 2.0, 2)
    assert abs(abs(st["mean_yaw_deg"]) - 180.0) < 1.0
    assert st["resultant_length"] > 0.9  # tightly clustered (both near 180)


def test_circular_mean_near_zero_is_zero():
    s = (math.sin(math.radians(10)) + math.sin(math.radians(-10))) / 2.0
    c = (math.cos(math.radians(10)) + math.cos(math.radians(-10))) / 2.0
    st = pp._circular_yaw_stats(s, c, 2)
    assert abs(st["mean_yaw_deg"]) < 1.0
    assert st["resultant_length"] > 0.9


def test_circular_uniform_low_R_capped_std_and_high_p():
    # 16 evenly spread directions -> resultant ~ 0, std capped, Rayleigh ~1.
    n = 16
    s = sum(math.sin(math.radians(i * 22.5)) for i in range(n)) / n
    c = sum(math.cos(math.radians(i * 22.5)) for i in range(n)) / n
    st = pp._circular_yaw_stats(s, c, n)
    assert st["resultant_length"] < 0.05
    assert st["circular_std_deg"] == 180.0
    assert st["rayleigh_p"] > 0.5  # not directional


def test_circular_identical_angles_R_one_std_zero_significant():
    th = math.radians(42.0)
    st = pp._circular_yaw_stats(math.sin(th), math.cos(th), 500)
    assert st["resultant_length"] >= 0.999
    assert st["circular_std_deg"] == 0.0
    assert abs(st["mean_yaw_deg"] - 42.0) < 0.5
    assert st["rayleigh_p"] < 0.05  # strongly directional


def test_circular_zero_n_safe_defaults():
    st = pp._circular_yaw_stats(0.0, 0.0, 0)
    assert st == {
        "n": 0, "mean_yaw_deg": 0.0, "resultant_length": 0.0,
        "circular_std_deg": 180.0, "rayleigh_p": 1.0,
    }


def test_yaw_bucket_centers_in_range_and_ordered():
    centers = [pp._aim_yaw_bucket_center_deg(i) for i in range(pp._AIM_YAW_BUCKETS)]
    assert len(centers) == 16
    assert all(-180.0 < x <= 180.0 for x in centers)
    # bucket 0 covers shifted [0,22.5) -> yaw ~ -168.75
    assert abs(centers[0] - (-168.75)) < 1e-6
    # bucket 8 covers shifted [180,202.5) -> yaw ~ +11.25
    assert abs(centers[8] - 11.25) < 1e-6


def test_rose_circular_concentrated_and_opposite():
    rose = [0] * 16
    rose[8] = 50  # ~ +11.25 deg
    mean_yaw, r = pp._rose_circular(rose)
    assert abs(mean_yaw - pp._aim_yaw_bucket_center_deg(8)) < 1e-6
    assert r >= 0.999
    opp = [0] * 16
    opp[0] = 25
    opp[8] = 25  # ~180 deg apart -> cancels
    _, r2 = pp._rose_circular(opp)
    assert r2 < 0.05
    assert pp._rose_circular([0] * 16) == (0.0, 0.0)


def test_dominant_sector_picks_strongest():
    rose = [0] * 16
    rose[8] = 30  # ~ +11.25 -> "E" sector (centred on 0)
    rose[9] = 10
    sector, frac = pp._aim_dominant_sector(rose)
    assert sector == "E"
    assert 0.0 < frac <= 1.0
    assert pp._aim_dominant_sector([0] * 16) == ("", 0.0)


def test_narrative_rules():
    assert pp._build_aim_narrative({"n": 0}, 0.0, [0] * 16) == ["0 shots tracked"]

    low = pp._build_aim_narrative(
        {"n": 10, "rayleigh_p": 0.01, "circular_std_deg": 10.0}, 0.0, [1] * 16,
    )
    assert low[0] == "10 shots tracked"
    assert "Low sample" in low[1]

    rose = [0] * 16
    rose[8] = 100  # strong "E"
    directional = pp._build_aim_narrative(
        {"n": 200, "rayleigh_p": 0.001, "circular_std_deg": 12.0}, 15.0, rose,
    )
    joined = " ".join(directional)
    assert "200 shots tracked" in joined
    assert "aimed E" in joined
    assert "tight" in joined.lower()
    assert "aim up" in joined.lower()

    uniform = pp._build_aim_narrative(
        {"n": 200, "rayleigh_p": 0.9, "circular_std_deg": 80.0}, -20.0, [12] * 16,
    )
    j2 = " ".join(uniform).lower()
    assert "no dominant" in j2
    assert "wide" in j2
    assert "aim down" in j2

    moderate = pp._build_aim_narrative(
        {"n": 200, "rayleigh_p": 0.001, "circular_std_deg": 40.0}, 2.0, rose,
    )
    j3 = " ".join(moderate).lower()
    assert "moderate" in j3
    assert "level aim" in j3


# ============================================================
# Endpoint integration (faked DB)
# ============================================================

class FakeAimDB:
    def __init__(self, *, rose_rows=None, pitch_rows=None, circ_row=None):
        self.rose_rows = rose_rows if rose_rows is not None else [
            (1, 2, 9, 30), (1, 2, 10, 10), (-3, 4, 1, 4),
        ]
        self.pitch_rows = pitch_rows if pitch_rows is not None else [
            (4, 25), (5, 15),
        ]
        self.circ_row = circ_row if circ_row is not None else (
            44,
            math.sin(math.radians(11.25)),
            math.cos(math.radians(11.25)),
            6.0,
            12.0,
        )
        self.resolver_called = False

    @staticmethod
    def _n(q: str) -> str:
        return " ".join(q.strip().lower().split())

    async def fetch_val(self, query: str, params=None):
        n = self._n(query)
        if "left(" in n and "limit 1" in n:
            self.resolver_called = True
            return CANON
        raise AssertionError(f"Unexpected fetch_val: {n}")

    async def fetch_all(self, query: str, params=None):
        n = self._n(query)
        if "max(player_name)" in n and "group by player_guid" in n:
            return [(CANON, "TestPlayer")]
        if "group by gx, gy, yb" in n:
            return list(self.rose_rows)
        if "group by pb" in n:
            return list(self.pitch_rows)
        if "avg(sin(radians" in n:
            return [self.circ_row]
        raise AssertionError(f"Unexpected fetch_all: {n}")


def _build_app(db) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db
    app.include_router(pp.router, prefix="/api")
    return app


async def _get(db, params):
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        return await c.get("/api/proximity/player-aim", params=params)


@pytest.mark.asyncio
async def test_missing_map_name_400():
    r = await _get(FakeAimDB(), {"player_guid": SHORT})
    assert r.status_code == 400
    assert "map_name" in r.json()["detail"]


@pytest.mark.asyncio
async def test_missing_player_guid_400():
    r = await _get(FakeAimDB(), {"map_name": "sw_goldrush_te"})
    assert r.status_code == 400
    assert "player_guid" in r.json()["detail"]


@pytest.mark.asyncio
async def test_short_guid_resolves_to_canonical():
    db = FakeAimDB()
    r = await _get(db, {"map_name": "sw_goldrush_te", "player_guid": SHORT})
    assert r.status_code == 200
    assert db.resolver_called is True
    assert r.json()["player_guid"] == CANON


@pytest.mark.asyncio
async def test_canonical_guid_skips_resolver():
    db = FakeAimDB()
    r = await _get(db, {"map_name": "sw_goldrush_te", "player_guid": CANON})
    assert r.status_code == 200
    assert db.resolver_called is False


@pytest.mark.asyncio
async def test_response_shape_and_rose_folding():
    db = FakeAimDB(
        rose_rows=[(1, 2, 9, 30), (1, 2, 10, 10), (5, 5, 3, 2)],  # cell(5,5)=2 < min_cell
        pitch_rows=[(1, 3), (4, 20), (6, 7)],
        circ_row=(40, math.sin(math.radians(11.25)), math.cos(math.radians(11.25)), 5.0, 9.0),
    )
    r = await _get(db, {"map_name": "sw_goldrush_te", "player_guid": CANON})
    assert r.status_code == 200
    j = r.json()
    for k in ("status", "map_name", "player_guid", "player_name", "grid_size",
              "total", "sampled", "scope", "hotzones", "yaw_buckets",
              "yaw_bucket_width_deg", "pitch_hist", "circular", "narrative"):
        assert k in j, f"missing {k}"
    assert j["yaw_buckets"] == 16
    assert j["total"] == j["circular"]["n"] == 40
    # cell (1,2) has 30+10=40 >= min_cell -> kept; (5,5)=2 -> filtered
    assert len(j["hotzones"]) == 1
    hz = j["hotzones"][0]
    assert hz["x"] == 1 and hz["y"] == 2 and hz["count"] == 40
    assert len(hz["rose"]) == 16
    assert hz["rose"][8] == 30 and hz["rose"][9] == 10  # yb 9->idx8, yb 10->idx9
    assert 0.0 <= hz["r"] <= 1.0
    assert len(j["pitch_hist"]["counts"]) == 6
    assert j["pitch_hist"]["counts"][0] == 3 and j["pitch_hist"]["counts"][3] == 20
    assert j["pitch_hist"]["counts"][5] == 7
    assert isinstance(j["narrative"], list) and j["narrative"]
    assert j["narrative"][0] == "40 shots tracked"


@pytest.mark.asyncio
async def test_min_cell_param_and_empty_data():
    db = FakeAimDB(rose_rows=[], pitch_rows=[], circ_row=(0, None, None, None, None))
    r = await _get(db, {"map_name": "m", "player_guid": CANON})
    assert r.status_code == 200
    j = r.json()
    assert j["hotzones"] == []
    assert j["total"] == 0
    assert j["circular"]["n"] == 0
    assert j["narrative"] == ["0 shots tracked"]


@pytest.mark.asyncio
async def test_cell_cap_sets_sampled():
    rows = []
    for i in range(150):  # 150 distinct cells, each >= min_cell
        rows.append((i, 0, 9, 20))
    db = FakeAimDB(rose_rows=rows,
                   circ_row=(3000, math.sin(0.2), math.cos(0.2), 1.0, 5.0))
    r = await _get(db, {"map_name": "m", "player_guid": CANON})
    j = r.json()
    assert j["sampled"] is True
    assert len(j["hotzones"]) == 120
