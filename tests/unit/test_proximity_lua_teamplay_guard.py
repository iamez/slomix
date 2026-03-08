from pathlib import Path


def _lua_source() -> str:
    root = Path(__file__).resolve().parents[2]
    lua_path = root / "proximity" / "lua" / "proximity_tracker.lua"
    return lua_path.read_text(encoding="utf-8")


def test_team_cohesion_skips_terminal_track_events():
    source = _lua_source()
    assert "local TERMINAL_TRACK_EVENTS = {" in source
    assert "local function isTerminalTrackEvent(event_name)" in source
    assert "and not isTerminalTrackEvent(sample.event)" in source


def test_team_pushes_use_bucketed_window_detection():
    source = _lua_source()
    assert "local bucket_ms = 5000" in source
    assert "local min_push_participants = 2" in source
    assert "local min_alignment_score = 0.55" in source
    assert "local function getBucketWindowSamples(track, bucket_start, bucket_end)" in source
    assert "local function classifyPushObjectiveDirection(avg_origin, direction_x, direction_y, objectives)" in source
