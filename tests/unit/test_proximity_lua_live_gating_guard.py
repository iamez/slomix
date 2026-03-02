from pathlib import Path


def _lua_source() -> str:
    root = Path(__file__).resolve().parents[2]
    lua_path = root / "proximity" / "lua" / "proximity_tracker.lua"
    return lua_path.read_text(encoding="utf-8")


def test_proximity_tracker_has_pause_toggle_detection():
    source = _lua_source()
    assert "PAUSE_TOGGLE_FLAG = 16" in source
    assert "et.CS_SERVERTOGGLES" in source
    assert "local function isMatchPaused()" in source


def test_proximity_tracker_uses_live_gameplay_guard_in_callbacks():
    source = _lua_source()
    assert "function et_Damage" in source
    assert "function et_Obituary" in source
    assert "function et_ClientSpawn" in source
    assert source.count("if not isLiveGameplay() then return end") >= 3


def test_proximity_tracker_skips_sampling_during_pause():
    source = _lua_source()
    assert "if gamestate == GS_PLAYING and not pause_state.active then" in source
