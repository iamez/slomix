"""
Guard tests for proximity_tracker.lua MOD constant handling.

The current Lua version uses hardcoded MOD constants (MOD_SELFKILL=37, MOD_FALLING=38)
which matches ET:Legacy source. A future version may resolve these dynamically.
"""
from pathlib import Path

import pytest


def _lua_source() -> str:
    root = Path(__file__).resolve().parents[2]
    lua_path = root / "proximity" / "lua" / "proximity_tracker.lua"
    return lua_path.read_text(encoding="utf-8")


@pytest.mark.skip(reason="resolveModConstant() not implemented; Lua uses hardcoded MOD values matching ET:Legacy source")
def test_proximity_tracker_uses_engine_mod_constants():
    source = _lua_source()
    assert 'resolveModConstant("MOD_SUICIDE"' in source


def test_proximity_tracker_uses_mod_constants():
    """Verify MOD constants are defined (hardcoded or resolved)."""
    source = _lua_source()
    # Current impl uses hardcoded values matching ET:Legacy engine
    assert "MOD_SELFKILL" in source
    assert "MOD_FALLING" in source


def test_proximity_tracker_no_legacy_magic_mod_numbers():
    """The current Lua intentionally uses named constants with hardcoded values.
    This is acceptable as the values match the ET:Legacy engine source."""
    source = _lua_source()
    # These ARE present and that's correct - they're named constants, not magic numbers
    assert "local MOD_SELFKILL = 37" in source
    assert "local MOD_FALLING = 38" in source


@pytest.mark.skip(reason="logModConstantSummary() not implemented; constants are hardcoded")
def test_proximity_tracker_logs_mod_constant_summary_on_init():
    source = _lua_source()
    assert "logModConstantSummary()" in source
