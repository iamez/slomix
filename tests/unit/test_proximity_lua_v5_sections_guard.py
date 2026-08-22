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


def test_proximity_tracker_shot_fired_section_is_gated_and_additive():
    """v9 true-aim: SHOT_FIRED must exist, stay feature-gated, and keep its shape.

    ⚠️ This test used to require the flag to default to FALSE, on the reasoning
    that an off default leaves "production behaviour unchanged until explicitly
    enabled". The opposite happened. The live server ran with the capture ON as
    an uncommitted edit, so the first deploy of this file turned it OFF: shot
    rows stop dead on 2026-08-11 and every session since has no gunfire data.
    An off default did not preserve production behaviour — it silently replaced
    it, and the loss is not recoverable after the fact.

    `aim_lock` is the control that shows the difference: it is true in this file,
    and it survived the same deploy with 92% August coverage.

    So the default is TRUE now, deliberately, and what this test guards is what
    actually matters: the section exists, it is still gated behind
    isFeatureEnabled (on-by-default must not mean ungated), and the emission
    shape is unchanged so existing parsers keep working.
    """
    source = _lua_source()
    assert "# SHOT_FIRED" in source
    assert 'isFeatureEnabled("shot_fired")' in source
    # Deliberately ON so the repository agrees with the server it deploys to.
    assert "shot_fired = true," in source
    # emission shape time;guid;weapon;ox;oy;oz;yaw;pitch
    assert "# time;guid;weapon;ox;oy;oz;yaw;pitch" in source


def test_spawn_select_reads_a_field_the_engine_actually_has():
    """`sess.spawnObjectiveIndex` does not exist anywhere in ET:Legacy.

    It was read here until 2026-08-22 because LUA_V7_CAPTURE_RESEARCH_2026-06.md
    called it a documented field. The name appears zero times in the engine
    source (commit 732518ef), so every capture it made was the -1 fallback.
    `sess.userSpawnPointValue` is the real field — exposed to Lua as FIELD_INT
    at src/game/g_lua.c:1313 — and on a local bot round it returns two distinct
    spawn points (0 and 4) where the old field returned -1 for everything.
    """
    source = _lua_source()
    # Assert on the READ, not on the mere presence of the name: the comment
    # above the fix names the old field on purpose, so that nobody restores it
    # from the stale research note. A substring check would forbid the very
    # documentation that prevents the regression.
    assert 'safe_gentity_get(clientNum, "sess.userSpawnPointValue")' in source
    assert 'safe_gentity_get(clientNum, "sess.spawnObjectiveIndex")' not in source


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
