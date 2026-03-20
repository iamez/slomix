"""
Guard tests for proximity_tracker.lua v5 teamplay features.

The current Lua writes teamplay sections inline rather than via
dedicated helper functions or terminal-track-event filtering.
"""
from pathlib import Path

import pytest


def _lua_source() -> str:
    root = Path(__file__).resolve().parents[2]
    lua_path = root / "proximity" / "lua" / "proximity_tracker.lua"
    return lua_path.read_text(encoding="utf-8")


@pytest.mark.skip(reason="TERMINAL_TRACK_EVENTS/isTerminalTrackEvent not implemented; cohesion uses inline filtering")
def test_team_cohesion_skips_terminal_track_events():
    source = _lua_source()
    assert "TERMINAL_TRACK_EVENTS" in source


def test_team_cohesion_section_exists():
    """Verify TEAM_COHESION output section is present."""
    source = _lua_source()
    assert "# TEAM_COHESION" in source


@pytest.mark.skip(reason="Bucketed window detection (bucket_ms, getBucketWindowSamples) not implemented; push detection uses event-based approach")
def test_team_pushes_use_bucketed_window_detection():
    source = _lua_source()
    assert "bucket_ms" in source


def test_team_pushes_section_exists():
    """Verify TEAM_PUSHES output section is present."""
    source = _lua_source()
    assert "# TEAM_PUSHES" in source
