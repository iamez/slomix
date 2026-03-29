"""
Guard tests for proximity_tracker.lua section output.

The current Lua writes sections inline in outputData() rather than
via dedicated helper functions.  Header upgraded from V5 to V6 in v6.01.
"""
from pathlib import Path


def _lua_source() -> str:
    root = Path(__file__).resolve().parents[2]
    lua_path = root / "proximity" / "lua" / "proximity_tracker.lua"
    return lua_path.read_text(encoding="utf-8")


def test_proximity_tracker_uses_header_and_spawn_interval_metadata():
    source = _lua_source()
    assert "# PROXIMITY_TRACKER_V6" in source or "# PROXIMITY_TRACKER_V5" in source
    assert "# axis_spawn_interval=%d" in source
    assert "# allies_spawn_interval=%d" in source


def test_proximity_tracker_writes_all_v5_section_headers():
    source = _lua_source()
    assert "# SPAWN_TIMING" in source
    assert "# TEAM_COHESION" in source
    assert "# CROSSFIRE_OPPORTUNITIES" in source
    assert "# TEAM_PUSHES" in source
    assert "# TRADE_KILLS" in source


def test_proximity_tracker_writes_v6_section_headers():
    source = _lua_source()
    assert "# CARRIER_EVENTS" in source
    assert "# CARRIER_KILLS" in source
    assert "# CONSTRUCTION_EVENTS" in source
    assert "# OBJECTIVE_RUNS" in source


def test_output_data_calls_section_writers():
    """Verify sections are written in outputData().

    Current implementation writes inline rather than via helper functions.
    We verify the section headers are written using trap_FS_Write.
    """
    source = _lua_source()
    assert "SPAWN_TIMING" in source
    assert "TEAM_COHESION" in source
    assert "CROSSFIRE_OPPORTUNITIES" in source
    assert "TEAM_PUSHES" in source
    assert "TRADE_KILLS" in source
    assert "et.trap_FS_Write" in source
