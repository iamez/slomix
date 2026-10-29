"""Actual legacy canvas commands vs independent offline gap contract, no browser."""

import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from proximity.parser.parser import ProximityParserV4
from shared.proximity_paths import in_capture_gap

ROOT = Path(__file__).resolve().parents[2]


def point(t, x, event="sample"):
    return dict(time=t, x=x, y=0, health=100, event=event)


def draw(path, time):
    node = shutil.which("node")
    assert node, "Node is required for whole-module canvas proof"
    result = subprocess.run(
        [node, "--experimental-vm-modules", "tests/js/replay_capture_harness.mjs"],
        input=json.dumps(dict(path=path, time=time)), text=True, capture_output=True,
        cwd=ROOT, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("time", [200, 201, 399, 400, 401, 600])
def test_canvas_and_event_lookup_respect_same_gap_as_backend(time):
    path = [point(0, 0), point(200, 10), point(400, 1000, "capture_resume"), point(600, 1010)]
    result = draw(path, time)
    missing = in_capture_gap(path, time)
    assert (result["dots"] == []) is missing
    assert (result["position"] is None) is missing
    if missing:
        assert result["strokes"] == []
    else:
        distance = sum(abs(b[0] - a[0]) for stroke in result["strokes"]
                       for a, b in zip(stroke, stroke[1:]))
        assert distance <= 10  # only last contiguous trail, never the 990-unit jump


@pytest.mark.parametrize("marker_index", [0, 1, 2])
def test_canvas_resets_whole_coincident_boundary_group(marker_index):
    path = [point(0, 0), point(200, 10)]
    boundary = [point(400, 990), point(400, 995), point(400, 1000)]
    boundary[marker_index]["event"] = "capture_resume"
    result = draw(path + boundary + [point(600, 1010)], 600)
    assert len(result["strokes"]) == 1
    assert [p[0] for p in result["strokes"][0]] == [1000, 1010]


def test_unmarked_legacy_path_keeps_existing_nearest_position_behaviour():
    result = draw([point(200, 10), point(400, 20)], 300)
    assert result["position"] == {"x": 10, "y": 0}
    assert result["dots"]


@pytest.mark.parametrize("time", [None, True, "400", 400.5])
def test_malformed_boundary_cannot_become_a_drawn_position(time):
    result = draw([point(200, 10), point(time, 1000, "capture_resume"), point(600, 1010)], 600)
    assert result == {"strokes": [], "dots": [], "position": None}


def test_initial_boundary_withholds_pre_capture_position():
    result = draw([point(400, 1000, "capture_resume"), point(600, 1010)], 200)
    assert result == {"strokes": [], "dots": [], "position": None}


def test_marker_without_coordinates_still_breaks_trail_and_gap():
    path = [point(0, 0), point(200, 10), {"time": 400, "event": "capture_resume"},
            point(600, 1010), point(800, 1020)]
    assert draw(path, 300) == {"strokes": [], "dots": [], "position": None}
    result = draw(path, 800)
    assert [p[0] for p in result["strokes"][0]] == [1010, 1020]


def test_legacy_tuple_boundary_is_not_ignored():
    path = [[t, x, 0, 0, 100, 0, 8, 0, 0, event]
            for t, x, event in [(200, 10, "sample"), (400, 1000, "capture_resume"), (600, 1010, "sample")]]
    assert draw(path, 300) == {"strokes": [], "dots": [], "position": None}
    assert [p[0] for p in draw(path, 600)["strokes"][0]] == [1000, 1010]


def test_actual_lua_file_reaches_canvas_without_inventing_gap_motion(tmp_path):
    lua = shutil.which("lua5.4")
    assert lua, "Lua5.4 required for writer-to-canvas proof"
    written = subprocess.run(
        [lua, "tests/lua/engine_clock_contract_harness.lua", str(tmp_path), "resume"],
        cwd=ROOT, capture_output=True, text=True, timeout=15,
    )
    assert written.returncode == 0, written.stdout + written.stderr
    files = list(tmp_path.glob("*_engagements.txt"))
    assert len(files) == 1
    parser = ProximityParserV4()
    assert parser.parse_file(str(files[0]))
    path = [asdict(p) for p in parser.player_tracks[0].path]
    boundary = next(p["time"] for p in path if p["event"] == "capture_resume")
    assert in_capture_gap(path, boundary - 1)
    assert draw(path, boundary - 1) == {"strokes": [], "dots": [], "position": None}
    result = draw(path, path[-1]["time"])
    distance = sum(abs(b[0] - a[0]) for s in result["strokes"] for a, b in zip(s, s[1:]))
    assert distance == 10  # whole source moved1000 ->1010 in final contiguous segment
    print("LUA/FILE/PARSER/CANVAS PROOF: gap has no dot/lookup/trail; post-gap trail=10 units; ET/canvas synthetic")


@pytest.mark.parametrize("time", [8000, 10600, 10800])
def test_actual_review_pause_interval_has_no_future_dot_or_gap_trail(time):
    path = [point(200, 10), point(10600, 50, "capture_resume"), point(10800, 60)]
    result = draw(path, time)
    if time == 8000:
        assert result == {"strokes": [], "dots": [], "position": None}
    else:
        assert result["position"] == {"x": 50 if time == 10600 else 60, "y": 0}
        distance = sum(abs(b[0] - a[0]) for stroke in result["strokes"]
                       for a, b in zip(stroke, stroke[1:]))
        assert distance <= 10
