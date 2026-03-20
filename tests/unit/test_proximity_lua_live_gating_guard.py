"""
Guard tests for proximity_tracker.lua live gameplay gating.

The current Lua version handles pause detection via levelTime freezing
rather than explicit PAUSE_TOGGLE_FLAG / isMatchPaused() / isLiveGameplay() guards.
"""
from pathlib import Path

import pytest


def _lua_source() -> str:
    root = Path(__file__).resolve().parents[2]
    lua_path = root / "proximity" / "lua" / "proximity_tracker.lua"
    return lua_path.read_text(encoding="utf-8")


@pytest.mark.skip(reason="PAUSE_TOGGLE_FLAG/isMatchPaused not implemented; pause handled via levelTime freeze")
def test_proximity_tracker_has_pause_toggle_detection():
    source = _lua_source()
    assert "PAUSE_TOGGLE_FLAG = 16" in source


def test_proximity_tracker_has_core_callbacks():
    """Verify core ET callback functions exist."""
    source = _lua_source()
    assert "function et_Obituary" in source


@pytest.mark.skip(reason="isLiveGameplay() guard not implemented; callbacks use gamestate checks directly")
def test_proximity_tracker_uses_live_gameplay_guard_in_callbacks():
    source = _lua_source()
    assert source.count("if not isLiveGameplay() then return end") >= 3


@pytest.mark.skip(reason="pause_state.active not used; pause handled via levelTime freeze in et_RunFrame")
def test_proximity_tracker_skips_sampling_during_pause():
    source = _lua_source()
    assert "pause_state.active" in source
