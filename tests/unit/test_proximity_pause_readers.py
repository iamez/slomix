"""Pause boundaries through actual ASGI handlers; synthetic DB, no live services."""

import copy
import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from proximity.parser.parser import ProximityParserV4
from shared.proximity_paths import capture_segments, in_capture_gap
from website.backend.dependencies import get_db
from website.backend.routers import proximity_objectives, replay_router
from website.backend.services import objective_pressure_service as pressure
from website.backend.services.replay_service import _find_position_at_time, get_player_paths
from website.backend.services.round_web_service import find_position_floor

ROOT = Path(__file__).resolve().parents[2]


def point(time, event="sample"):
    return {"time": time, "x": 10, "y": 0, "z": 0, "health": 100, "event": event}


@pytest.mark.parametrize("duplicate", [False, True])
@pytest.mark.parametrize("target,missing", [(-1, False), (0, False), (1, True),
                                          (100, True), (199, True), (200, False), (400, False)])
def test_offline_replay_refuses_only_explicit_open_gap(duplicate, target, missing):
    path = [point(0), point(200, "capture_resume"), point(400)]
    if duplicate:
        path.insert(1, {**point(200), "x": 900})  # plausible duplicate cannot hide jump
    original = copy.deepcopy(path)
    assert in_capture_gap(path, target) is missing
    assert (_find_position_at_time(path, target) is None) is missing
    segments = capture_segments(path)
    assert [p["time"] for p in segments[0]] == [0]
    assert segments[1][0]["time"] == 200
    assert len(segments) == (3 if duplicate else 2)
    assert sum(abs(b["x"] - a["x"]) for s in segments for a, b in zip(s, s[1:])) == 0
    assert [p for s in segments for p in s] == path == original


def test_initial_repeated_boundary_and_causal_history_are_distinct():
    path = [point(200, "capture_resume"), point(400), point(600, "capture_resume")]
    assert in_capture_gap(path, 0)
    assert in_capture_gap(path, 500)
    assert not in_capture_gap(path, 400)
    assert len(capture_segments(path)) == 2
    # Offline replay can use hindsight; causal Spiderweb must not learn from a
    # future marker. Its answer remains the last observed state plus staleness.
    assert find_position_floor(path, 500) == (path[1], 100, 1)
    assert find_position_floor(path[:2], 500) == find_position_floor(path, 500)


@pytest.mark.parametrize("timestamp", [None, True, "200", 200.5])
def test_malformed_marker_does_not_become_an_ordinary_point(timestamp):
    path = [point(0), point(timestamp, "capture_resume")]
    for helper, args in [(capture_segments, (path,)), (in_capture_gap, (path, 100))]:
        with pytest.raises(ValueError, match="integer timestamp"):
            helper(*args)


class ReaderDb:
    def __init__(self, path):
        self.path = path
        self.calls = []

    async def fetch_all(self, sql, params=()):
        self.calls.append((sql, params))
        if "SELECT pt.player_guid" in sql:
            return [("G1", "Player", "ALLIES", "MEDIC", 0, 2000, self.path, "supply")]
        if "FROM player_track" in sql:
            return [dict(round_start_unix=1000, round_number=1, map_name="supply",
                         player_guid=guid, player_name=guid, team=team, path=json.dumps(self.path))
                    for guid, team in [("ALLY0001", "ALLIES"), ("ALLY0002", "ALLIES"), ("AXIS0001", "AXIS")]]
        if "FROM proximity_combat_position" in sql:
            return []
        raise AssertionError(f"unexpected query: {sql}")


@pytest.fixture
def pressure_isolation(monkeypatch):
    monkeypatch.setattr(pressure, "_CACHE", {})
    monkeypatch.setattr(pressure, "_load_zones", lambda: {"supply": [(0, 0, 0, 10000)]})


@pytest.mark.asyncio
@pytest.mark.parametrize("duplicate", [False, True])
@pytest.mark.parametrize("marker_coordinates", [False, True])
async def test_pressure_keeps_boundaries_even_when_coordinates_are_missing(
    pressure_isolation, duplicate, marker_coordinates
):
    marker = point(800, "capture_resume") if marker_coordinates else {"time": 800, "event": "capture_resume"}
    path = [point(0), point(200), marker, point(1000), point(1200)]
    if duplicate:
        path.insert(2, point(800))
    out = await pressure.compute_objective_pressure(ReaderDb(path), "2099-01-01")
    assert [p["pressure_seconds"] for p in out["players"]] == [0.4, 0.4]
    assert out["capture_quality"]["status"] == "partial"
    assert out["capture_quality"]["boundary_markers"] == 3
    assert out["capture_quality"]["excluded_boundary_points"] == (6 if duplicate else 3)
    cached = await pressure.compute_objective_pressure(ReaderDb(path), "2099-01-01", limit=1)
    assert len(cached["players"]) == 1
    assert cached["capture_quality"] == out["capture_quality"]


@pytest.mark.asyncio
async def test_marker_alone_is_not_enemy_presence(pressure_isolation):
    class Db(ReaderDb):
        async def fetch_all(self, sql, params=()):
            rows = await super().fetch_all(sql, params)
            if "FROM player_track" in sql:
                rows[2]["path"] = json.dumps([point(0, "capture_resume")])
            return rows
    out = await pressure.compute_objective_pressure(Db([point(0), point(200)]), "2099-01-02")
    assert out["players"] == []
    assert out["capture_quality"]["status"] == "partial"


@pytest.mark.asyncio
async def test_trail_window_cannot_reconnect_separate_segments():
    path = [point(0), point(200), point(800, "capture_resume"), point(1000)]
    result = await get_player_paths(ReaderDb(path), 1, 100, 900)
    assert [[p["time"] for p in s["samples"]] for s in result["paths"]] == [[200], [800]]
    assert result["player_count"] == 1
    assert result["segment_count"] == 2


@pytest.mark.asyncio
async def test_whole_lua_file_to_real_asgi_replay_and_pressure(tmp_path, pressure_isolation):
    lua = shutil.which("lua5.4")
    assert lua, "lua5.4 required for connected proof"
    result = subprocess.run(
        [lua, "tests/lua/engine_clock_contract_harness.lua", str(tmp_path), "resume"],
        cwd=ROOT, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    files = list(tmp_path.glob("*_engagements.txt"))
    assert len(files) == 1
    parser = ProximityParserV4()
    assert parser.parse_file(str(files[0]))
    path = [asdict(p) for p in parser.player_tracks[0].path]
    boundary = next(p["time"] for p in path if p["event"] == "capture_resume")
    db = ReaderDb(path)
    app = FastAPI()
    app.include_router(replay_router.router, prefix="/api")
    app.include_router(proximity_objectives.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        positions = await client.get("/api/replay/round/1/positions", params={"t": boundary - 1})
        trails = await client.get("/api/replay/round/1/paths", params={"from": 0, "to": 2000})
        objective = await client.get("/api/proximity/objective-pressure", params={"session_date": "2099-01-03"})
    assert [r.status_code for r in (positions, trails, objective)] == [200, 200, 200]
    assert positions.json()["players"] == []
    assert positions.json()["gaps"] == {"G1": "capture_discontinuity"}
    assert trails.json()["segment_count"] == 2
    trail_distance = sum(abs(b["x"] - a["x"]) for s in trails.json()["paths"]
                         for a, b in zip(s["samples"], s["samples"][1:]))
    assert trail_distance == parser.player_tracks[0].total_distance == 20
    assert all(not (min(p["time"] for p in s["samples"]) < boundary <=
                    max(p["time"] for p in s["samples"])) for s in trails.json()["paths"])
    assert [p["pressure_seconds"] for p in objective.json()["players"]] == [0.4, 0.4]
    assert objective.json()["capture_quality"]["boundary_markers"] == 3
    # Independent interval accounting: the pre-gap pair and the final post-gap
    # pair each contribute 200ms. Neither gap nor boundary supplies a credit.
    assert sum(path[b]["time"] - path[a]["time"] for a, b in [(0, 1), (3, 4)]) / 1000 == 0.4
    print("ASGI PROOF: positions=gap; trails=2; pressure=0.4s; ET/DB synthetic")
