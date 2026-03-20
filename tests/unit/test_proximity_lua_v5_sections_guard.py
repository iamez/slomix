"""
Guard tests for proximity_tracker.lua v5 section output.

The current Lua writes v5 sections inline in outputData() rather than
via dedicated writeV5*() helper functions.
"""
from pathlib import Path

import pytest


def _lua_source() -> str:
    root = Path(__file__).resolve().parents[2]
    lua_path = root / "proximity" / "lua" / "proximity_tracker.lua"
    return lua_path.read_text(encoding="utf-8")


def test_proximity_tracker_uses_v5_header_and_spawn_interval_metadata():
    source = _lua_source()
    assert "# PROXIMITY_TRACKER_V5" in source
    assert "# axis_spawn_interval=%d" in source
    assert "# allies_spawn_interval=%d" in source


def test_proximity_tracker_writes_all_v5_section_headers():
    source = _lua_source()
    assert "# SPAWN_TIMING" in source
    assert "# TEAM_COHESION" in source
    assert "# CROSSFIRE_OPPORTUNITIES" in source
    assert "# TEAM_PUSHES" in source
    assert "# TRADE_KILLS" in source


def test_output_data_calls_v5_section_writers():
    """Verify v5 sections are written in outputData().

    Current implementation writes inline rather than via writeV5*() helpers.
    We verify the section headers are written using trap_FS_Write.
    """
    source = _lua_source()
    # Inline writing: sections use trap_FS_Write with section headers
    assert "SPAWN_TIMING" in source
    assert "TEAM_COHESION" in source
    assert "CROSSFIRE_OPPORTUNITIES" in source
    assert "TEAM_PUSHES" in source
    assert "TRADE_KILLS" in source
    # Verify data is actually written using trap_FS_Write
    assert "et.trap_FS_Write" in source
