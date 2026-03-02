from pathlib import Path


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
    source = _lua_source()
    assert "writeV5SpawnTiming(fd" in source
    assert "writeV5TeamCohesion(fd)" in source
    assert "writeV5CrossfireOpportunities(fd" in source
    assert "writeV5TeamPushes(fd)" in source
    assert "writeV5LuaTradeKills(fd)" in source
