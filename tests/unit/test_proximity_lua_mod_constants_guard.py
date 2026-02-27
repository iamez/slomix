from pathlib import Path


def _lua_source() -> str:
    root = Path(__file__).resolve().parents[2]
    lua_path = root / "proximity" / "lua" / "proximity_tracker.lua"
    return lua_path.read_text(encoding="utf-8")


def test_proximity_tracker_uses_engine_mod_constants():
    source = _lua_source()
    assert 'resolveModConstant("MOD_SUICIDE"' in source
    assert 'resolveModConstant("MOD_FALLING"' in source


def test_proximity_tracker_no_legacy_magic_mod_numbers():
    source = _lua_source()
    assert "local MOD_SELFKILL = 37" not in source
    assert "local MOD_FALLING = 38" not in source


def test_proximity_tracker_logs_mod_constant_summary_on_init():
    source = _lua_source()
    assert "logModConstantSummary()" in source
    assert "MOD constants: MOD_SUICIDE=" in source
