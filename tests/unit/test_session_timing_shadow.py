"""Tests for SessionTimingShadowService pure helpers + compute_shadow_values.

The shadow timing service is a parallel "what would the new formula
say" system that runs alongside legacy timing. A regression in the
deterministic compute step silently:

- New dead/denied values violate invariants (negative, > played
  time) → KIS comparison shows nonsensical numbers.
- Fallback reason gets dropped → operator can't tell why a round
  was excluded.
- top_n_diff_summary mis-sorts → wrong players highlighted.

`compute_shadow_values` is the heart of this service and must be
deterministic. Pin every invariant.
"""
from __future__ import annotations

import pytest

from bot.services.session_timing_shadow_service import (
    PlayerSessionTimingShadow,
    SessionTimingShadowResult,
    SessionTimingShadowService,
)

# ---------------------------------------------------------------------------
# _coerce_int — defensive int cast
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value, expected", [
    (None,    0),
    (0,       0),
    (42,      42),
    (3.14,    3),       # float truncates via int(float(...))
    ("100",   100),     # string-int
    ("3.7",   3),       # string-float truncates
    ("",      0),       # empty → 0 (ValueError swallowed)
    ("garbage", 0),     # unparseable → 0
])
def test_coerce_int_known_values(value, expected):
    assert SessionTimingShadowService._coerce_int(value) == expected


def test_coerce_int_handles_complex_unparseable():
    """List/dict → 0 (TypeError swallowed)."""
    assert SessionTimingShadowService._coerce_int([1, 2]) == 0
    assert SessionTimingShadowService._coerce_int({"a": 1}) == 0


# ---------------------------------------------------------------------------
# _clamp
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("v, lo, hi, expected", [
    (5,    0,  10, 5),
    (-1,   0,  10, 0),
    (15,   0,  10, 10),
    (0,    0,  10, 0),
    (10,   0,  10, 10),
    (5,    5,  5,  5),  # range collapsed
])
def test_clamp_known_values(v, lo, hi, expected):
    assert SessionTimingShadowService._clamp(v, lo, hi) == expected


def test_clamp_inverted_bounds():
    """Inverted bounds (lo>hi) → returns hi (because min(value, high)
    runs first). Pin observed behaviour — caller's responsibility to
    pass valid bounds."""
    # max(10, min(5, 0)) → max(10, 0) → 10
    assert SessionTimingShadowService._clamp(5, 10, 0) == 10


# ---------------------------------------------------------------------------
# _guid_prefix
# ---------------------------------------------------------------------------


def test_guid_prefix_first_8_chars_lowercase():
    out = SessionTimingShadowService._guid_prefix("ABCDEF1234567890")
    assert out == "abcdef12"
    assert len(out) == 8


def test_guid_prefix_strips_whitespace():
    out = SessionTimingShadowService._guid_prefix("  abcdef1234  ")
    assert out == "abcdef12"


def test_guid_prefix_handles_short_guid():
    """GUID shorter than 8 chars → returned as-is (lowercased)."""
    out = SessionTimingShadowService._guid_prefix("ABC")
    assert out == "abc"


def test_guid_prefix_handles_none():
    """None → empty string."""
    assert SessionTimingShadowService._guid_prefix(None) == ""


def test_guid_prefix_handles_int():
    """Numeric GUID → str() then prefix."""
    out = SessionTimingShadowService._guid_prefix(12345678901234)
    assert out == "12345678"


# ---------------------------------------------------------------------------
# _format_reason
# ---------------------------------------------------------------------------


def test_format_reason_joins_with_pipe():
    """Multi-reason → pipe-separated."""
    out = SessionTimingShadowService._format_reason(["a", "b", "c"])
    assert out == "a|b|c"


def test_format_reason_returns_none_for_empty():
    """Empty list → "none" sentinel."""
    assert SessionTimingShadowService._format_reason([]) == "none"


def test_format_reason_filters_falsy_and_none_strings():
    """Filter "none" string + empty + None → "none" sentinel."""
    out = SessionTimingShadowService._format_reason(["none", "", None, "real"])
    assert out == "real"


def test_format_reason_all_filtered_returns_none_sentinel():
    out = SessionTimingShadowService._format_reason(["none", "", None])
    assert out == "none"


# ---------------------------------------------------------------------------
# compute_shadow_values — invariant-driven
# ---------------------------------------------------------------------------


def test_compute_shadow_lua_missing_returns_old_dead():
    """`lua_dead_seconds=None` → fall back to old_dead unchanged.
    Pin the missing-Lua path so a regression doesn't accidentally
    return Lua dummy 0."""
    out = SessionTimingShadowService.compute_shadow_values(
        time_played_seconds=600,
        old_dead_seconds=120,
        old_denied_playtime=30,
        lua_dead_seconds=None,
        lua_round_duration_seconds=None,
    )
    assert out.new_dead_seconds == 120
    assert out.new_denied_playtime == 30
    assert out.lua_dead_seconds_raw is None
    assert "lua_missing" in out.fallback_reason


def test_compute_shadow_lua_missing_uses_custom_reason():
    """Caller can override the missing-reason for diagnostics."""
    out = SessionTimingShadowService.compute_shadow_values(
        time_played_seconds=600,
        old_dead_seconds=0,
        old_denied_playtime=0,
        lua_dead_seconds=None,
        lua_round_duration_seconds=None,
        lua_missing_reason="custom_skip",
    )
    assert "custom_skip" in out.fallback_reason


def test_compute_shadow_lua_present_replaces_old_dead():
    """Lua data present → use it directly (no clamp needed when
    within bounds)."""
    out = SessionTimingShadowService.compute_shadow_values(
        time_played_seconds=600,
        old_dead_seconds=120,
        old_denied_playtime=30,
        lua_dead_seconds=180,
        lua_round_duration_seconds=600,
    )
    assert out.new_dead_seconds == 180
    assert out.lua_dead_seconds_raw == 180


def test_compute_shadow_lua_negative_clamped_to_zero():
    """Negative Lua dead → 0 with `lua_dead_negative_clamped` reason."""
    out = SessionTimingShadowService.compute_shadow_values(
        time_played_seconds=600,
        old_dead_seconds=0,
        old_denied_playtime=0,
        lua_dead_seconds=-50,
        lua_round_duration_seconds=600,
    )
    assert out.new_dead_seconds == 0
    assert "lua_dead_negative_clamped" in out.fallback_reason
    assert out.lua_dead_seconds_raw == -50  # raw preserved for audit


def test_compute_shadow_lua_caps_at_played_time():
    """Lua dead > time_played → clamp to time_played."""
    out = SessionTimingShadowService.compute_shadow_values(
        time_played_seconds=300,
        old_dead_seconds=0,
        old_denied_playtime=0,
        lua_dead_seconds=500,  # > played
        lua_round_duration_seconds=600,
    )
    # cap_limit = min(played=300, lua_round=600) = 300
    assert out.new_dead_seconds == 300
    assert "lua_dead_capped_to_plausible_limit" in out.fallback_reason


def test_compute_shadow_lua_caps_at_round_duration_when_smaller():
    """If lua_round_duration < time_played → cap at lua_round_duration."""
    out = SessionTimingShadowService.compute_shadow_values(
        time_played_seconds=600,
        old_dead_seconds=0,
        old_denied_playtime=0,
        lua_dead_seconds=500,
        lua_round_duration_seconds=400,  # smaller than played
    )
    # cap_limit = min(600, 400) = 400
    assert out.new_dead_seconds == 400
    assert "lua_dead_capped_to_plausible_limit" in out.fallback_reason


def test_compute_shadow_denied_scales_with_active_time():
    """When old_active=480, old_denied=48 (10% of active), new_active=
    420 (after Lua reduces dead) → new_denied ≈ 42 (10% of 420)."""
    out = SessionTimingShadowService.compute_shadow_values(
        time_played_seconds=600,
        old_dead_seconds=120,    # old_active = 480
        old_denied_playtime=48,  # 10% of 480
        lua_dead_seconds=180,    # new_active = 420
        lua_round_duration_seconds=600,
    )
    assert out.new_denied_playtime == 42  # round(48/480 * 420) = 42


def test_compute_shadow_denied_when_old_active_zero():
    """If old_dead==played, old_active=0 → can't compute denied rate.
    Pin observed: new_denied = clamp(old_denied, 0, new_active),
    NOT zero. Reason "old_active_zero" recorded for audit trail.
    A regression that returned 0 would silently zero out denied
    metric when player only had 0 active time in old data."""
    out = SessionTimingShadowService.compute_shadow_values(
        time_played_seconds=300,
        old_dead_seconds=300,    # old_active = 0
        old_denied_playtime=50,  # old_denied present
        lua_dead_seconds=100,    # new_active = 200
        lua_round_duration_seconds=300,
    )
    # old_denied=50 clamped to [0, new_active=200] → 50 (within bounds)
    assert out.new_denied_playtime == 50
    assert "old_active_zero" in out.fallback_reason


def test_compute_shadow_clamps_old_dead_to_played():
    """old_dead > time_played → clamped to played (input sanitisation)."""
    out = SessionTimingShadowService.compute_shadow_values(
        time_played_seconds=300,
        old_dead_seconds=500,     # > played
        old_denied_playtime=20,
        lua_dead_seconds=None,    # use old path
        lua_round_duration_seconds=None,
    )
    assert out.new_dead_seconds == 300  # clamped


def test_compute_shadow_negative_played_clamped_to_zero():
    """Negative played time → 0; downstream clamps cascade."""
    out = SessionTimingShadowService.compute_shadow_values(
        time_played_seconds=-100,
        old_dead_seconds=50,
        old_denied_playtime=10,
        lua_dead_seconds=None,
        lua_round_duration_seconds=None,
    )
    assert out.new_dead_seconds == 0
    assert out.new_denied_playtime == 0
    assert out.cap_limit_seconds == 0


def test_compute_shadow_handles_none_played_via_coerce():
    """None played_seconds → coerce to 0."""
    out = SessionTimingShadowService.compute_shadow_values(
        time_played_seconds=None,
        old_dead_seconds=0,
        old_denied_playtime=0,
        lua_dead_seconds=None,
        lua_round_duration_seconds=None,
    )
    assert out.cap_limit_seconds == 0


def test_compute_shadow_invariant_dead_le_played():
    """For any input, new_dead_seconds ≤ played time. Pin the
    invariant explicitly."""
    out = SessionTimingShadowService.compute_shadow_values(
        time_played_seconds=600,
        old_dead_seconds=0,
        old_denied_playtime=0,
        lua_dead_seconds=10000,  # huge
        lua_round_duration_seconds=None,
    )
    assert out.new_dead_seconds <= 600


def test_compute_shadow_invariant_dead_nonneg():
    """new_dead_seconds ≥ 0 always."""
    out = SessionTimingShadowService.compute_shadow_values(
        time_played_seconds=600,
        old_dead_seconds=0,
        old_denied_playtime=0,
        lua_dead_seconds=-9999,
        lua_round_duration_seconds=None,
    )
    assert out.new_dead_seconds >= 0


# ---------------------------------------------------------------------------
# top_n_diff_summary
# ---------------------------------------------------------------------------


def _make_summary(guid, dead_diff=0, denied_diff=0):
    return PlayerSessionTimingShadow(
        player_guid=guid, player_name=guid, rounds=1,
        old_time_played_seconds=600, old_dead_seconds=120,
        old_denied_playtime=20,
        new_dead_seconds=120 + dead_diff,
        new_denied_playtime=20 + denied_diff,
        dead_diff_seconds=dead_diff,
        denied_diff_seconds=denied_diff,
        lua_spawn_rows=10, rounds_with_lua=1, coverage_percent=100.0,
    )


def _make_result(summaries):
    return SessionTimingShadowResult(
        session_ids=(1,),
        generated_at=None,  # unused by sort
        player_rounds=tuple(),
        player_summaries=tuple(summaries),
        round_diagnostics=tuple(),
        overall_coverage_percent=100.0,
        artifact_path=None,
    )


def test_top_n_returns_empty_for_zero_n():
    svc = SessionTimingShadowService(db_adapter=None)
    result = _make_result([_make_summary("g1", dead_diff=100)])
    assert svc.top_n_diff_summary(result, n=0) == []


def test_top_n_returns_empty_for_negative_n():
    """Defensive: negative n → empty list."""
    svc = SessionTimingShadowService(db_adapter=None)
    result = _make_result([_make_summary("g1", dead_diff=100)])
    assert svc.top_n_diff_summary(result, n=-3) == []


def test_top_n_sorts_by_absolute_dead_diff():
    """Default metric=dead_diff_seconds, absolute=True. Pin so a
    -100s diff outranks a +50s diff."""
    svc = SessionTimingShadowService(db_adapter=None)
    result = _make_result([
        _make_summary("g1", dead_diff=50),
        _make_summary("g2", dead_diff=-100),
        _make_summary("g3", dead_diff=10),
    ])
    out = svc.top_n_diff_summary(result, n=3)
    assert out[0].player_guid == "g2"  # |-100| = 100 wins
    assert out[1].player_guid == "g1"  # 50
    assert out[2].player_guid == "g3"  # 10


def test_top_n_signed_mode_preserves_sign():
    """absolute=False → use signed value; -100 < 50."""
    svc = SessionTimingShadowService(db_adapter=None)
    result = _make_result([
        _make_summary("g1", dead_diff=50),
        _make_summary("g2", dead_diff=-100),
        _make_summary("g3", dead_diff=10),
    ])
    out = svc.top_n_diff_summary(result, n=3, absolute=False)
    # Sort DESC by signed → 50, 10, -100
    assert out[0].player_guid == "g1"
    assert out[1].player_guid == "g3"
    assert out[2].player_guid == "g2"


def test_top_n_supports_denied_diff_metric():
    svc = SessionTimingShadowService(db_adapter=None)
    result = _make_result([
        _make_summary("g1", denied_diff=10),
        _make_summary("g2", denied_diff=50),
    ])
    out = svc.top_n_diff_summary(result, n=2, metric="denied_diff_seconds")
    assert out[0].player_guid == "g2"


def test_top_n_rejects_unknown_metric():
    """Unknown metric → ValueError. Pin so a typo doesn't silently
    sort by player_guid hash."""
    svc = SessionTimingShadowService(db_adapter=None)
    result = _make_result([_make_summary("g1")])
    with pytest.raises(ValueError, match="Unsupported metric"):
        svc.top_n_diff_summary(result, n=3, metric="boom")


def test_top_n_truncates_to_n():
    svc = SessionTimingShadowService(db_adapter=None)
    result = _make_result([
        _make_summary(f"g{i}", dead_diff=i * 10) for i in range(10)
    ])
    out = svc.top_n_diff_summary(result, n=3)
    assert len(out) == 3


def test_top_n_tie_breaks_by_player_guid():
    """Same diff value → tie-broken by guid (alphabetical reversed
    via reverse=True). Pin determinism."""
    svc = SessionTimingShadowService(db_adapter=None)
    result = _make_result([
        _make_summary("alice", dead_diff=50),
        _make_summary("bob", dead_diff=50),
    ])
    out = svc.top_n_diff_summary(result, n=2)
    # Both have score 50; reverse=True → "bob" > "alice" alphabetically
    assert out[0].player_guid == "bob"
    assert out[1].player_guid == "alice"
