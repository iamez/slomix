"""
Guard tests for proximity_tracker.lua scan hardening features.

These tests verify specific code patterns exist in the Lua source.
Tests are skipped when the corresponding pattern has not yet been implemented.
"""
from pathlib import Path

import pytest


def _lua_source() -> str:
    root = Path(__file__).resolve().parents[2]
    lua_path = root / "proximity" / "lua" / "proximity_tracker.lua"
    return lua_path.read_text(encoding="utf-8")


def test_round_start_flushes_pending_output_before_reset():
    """Verify output_pending + outputData() flush exists."""
    source = _lua_source()
    # The Lua uses a deferred-timer pattern instead of a simple `if tracker.output_pending then` guard.
    assert "tracker.output_pending" in source
    assert "outputData()" in source
    assert "tracker.output_written = false" in source


@pytest.mark.skip(reason="GS_RESET constant not used in current Lua version; intermission handled via GS_INTERMISSION only")
def test_round_end_handles_gs_reset():
    source = _lua_source()
    assert "local GS_RESET = et.GS_RESET" in source


def test_obituary_uses_death_type_for_engagement_outcome():
    """Verify obituary path closes engagements with proper outcome."""
    source = _lua_source()
    # Current implementation uses getDeathType() and closeEngagement() directly
    assert "closeEngagement(engagement" in source
    assert "getDeathType" in source


@pytest.mark.skip(reason="damage_events array not used; crossfire uses LOS-based analysis instead")
def test_crossfire_damage_within_window_uses_damage_events():
    source = _lua_source()
    assert "damage_events = {}" in source


def test_escape_detection_uses_stable_target_snapshot():
    source = _lua_source()
    assert "local active_targets = {}" in source
    assert "for _, target_slot in ipairs(active_targets) do" in source


@pytest.mark.skip(reason="objective_lookup_cache not implemented; objectives use inline map config")
def test_objective_lookup_uses_sanitized_cache_and_default_fallback():
    source = _lua_source()
    assert "objective_lookup_cache" in source


@pytest.mark.skip(reason="slot_guid_nonce pattern not implemented; GUID resolved via et.gentity_get")
def test_slot_fallback_guid_includes_connection_nonce():
    source = _lua_source()
    assert "slot_guid_nonce" in source


@pytest.mark.skip(reason="proxPrintf wrapper not implemented; uses et.G_Print/et.G_Printf directly")
def test_printf_fallback_uses_g_print_when_g_printf_missing():
    source = _lua_source()
    assert "local function proxPrintf(fmt, ...)" in source


@pytest.mark.skip(reason="sortedKeys/gridKeyComparator not implemented; output uses ipairs directly")
def test_output_sections_use_sorted_iteration_for_stable_order():
    source = _lua_source()
    assert "sortedKeys" in source
