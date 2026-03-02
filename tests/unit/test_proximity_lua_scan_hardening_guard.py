from pathlib import Path


def _lua_source() -> str:
    root = Path(__file__).resolve().parents[2]
    lua_path = root / "proximity" / "lua" / "proximity_tracker.lua"
    return lua_path.read_text(encoding="utf-8")


def test_round_start_flushes_pending_output_before_reset():
    source = _lua_source()
    assert "if tracker.output_pending then" in source
    assert "outputData()" in source
    assert "tracker.output_written = false" in source


def test_round_end_handles_gs_reset():
    source = _lua_source()
    assert "local GS_RESET = et.GS_RESET" in source
    assert "gamestate == GS_INTERMISSION or (GS_RESET ~= nil and gamestate == GS_RESET)" in source


def test_obituary_uses_death_type_for_engagement_outcome():
    source = _lua_source()
    assert 'local engagement_outcome = death_type or "unknown"' in source
    assert "closeEngagement(engagement, engagement_outcome, killer_for_outcome)" in source


def test_crossfire_damage_within_window_uses_damage_events():
    source = _lua_source()
    assert "damage_events = {}" in source
    assert "table.insert(attacker.damage_events" in source
    assert "event.time >= first_hit" in source
    assert "event.time <= window_end" in source


def test_escape_detection_uses_stable_target_snapshot():
    source = _lua_source()
    assert "local active_targets = {}" in source
    assert "for _, target_slot in ipairs(active_targets) do" in source


def test_objective_lookup_uses_sanitized_cache_and_default_fallback():
    source = _lua_source()
    assert "local objective_lookup_cache = {" in source
    assert "sanitizeObjectiveEntries" in source
    assert "buildObjectiveLookupCache()" in source
    assert "objective_lookup_cache.default" in source


def test_slot_fallback_guid_includes_connection_nonce():
    source = _lua_source()
    assert "return string.format(\"SLOT%d_%d\", clientnum, nonce)" in source
    assert "slot_guid_nonce[clientNum] = (slot_guid_nonce[clientNum] or 0) + 1" in source


def test_printf_fallback_uses_g_print_when_g_printf_missing():
    source = _lua_source()
    assert "local function proxPrintf(fmt, ...)" in source
    assert "if et.G_Printf then" in source
    assert "et.G_Print(string.format(fmt, ...))" in source
    assert source.count("et.G_Printf(") == 1


def test_output_sections_use_sorted_iteration_for_stable_order():
    source = _lua_source()
    assert "for _, key in ipairs(sortedKeys(tracker.kill_heatmap, gridKeyComparator)) do" in source
    assert "for _, key in ipairs(sortedKeys(tracker.movement_heatmap, gridKeyComparator)) do" in source
    assert "for _, guid in ipairs(sortedKeys(tracker.objective_stats" in source
