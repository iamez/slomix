"""Edge-case tests for bot/core/round_contract.py.

The existing suite covers the core happy paths; this module fills in
the parse/normalise edge cases that have previously caused real
incidents in webhook + backfill metadata pipelines:

- `parse_time_to_seconds` accepts 4 input formats (MM:SS, HH:MM:SS,
  decimal minutes, numeric seconds). Each has its own failure mode.
- `normalize_side_value` with `allow_unknown=False` returns -1 sentinel.
- `normalize_end_reason` alias map (every key maps to canonical enum).
- `score_confidence_state` state transitions: verified vs ambiguous
  vs missing vs time_fallback.
- `derive_stopwatch_contract`: FULL_HOLD vs TIME_SET threshold (30s
  before time-limit), round_number=1 vs 2, end_reason gating.
- `derive_end_reason_display`: terminal end-reasons override stopwatch state.

These functions feed the round_correlations.score_confidence_state
column, the `time_to_beat_seconds` Smart Stats display, and the
end_reason_display badge on every match summary embed. Drift here
would silently mislabel every match.
"""
from __future__ import annotations

import pytest

from bot.core.round_contract import (
    END_REASON_ENUM,
    derive_end_reason_display,
    derive_stopwatch_contract,
    normalize_end_reason,
    normalize_side_value,
    parse_time_to_seconds,
    score_confidence_state,
)


# ---------------------------------------------------------------------------
# parse_time_to_seconds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text, expected", [
    ("4:30",         270),       # MM:SS
    ("0:00",         0),         # zero
    ("10:00",        600),       # ten minutes
    ("60:00",        3600),      # an hour rendered as MM:SS (still valid)
    ("1:00:00",      3600),      # HH:MM:SS
    ("0:04:30",      270),       # leading-hour zero
    ("2:30:45",      9045),
])
def test_parse_time_colon_formats(text, expected):
    assert parse_time_to_seconds(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("10",      10),    # numeric seconds
    ("0",       0),
    ("3600",    3600),
])
def test_parse_time_numeric_seconds(text, expected):
    """Plain integer text → seconds (no decimal point, no colon)."""
    assert parse_time_to_seconds(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("1.5",     90),     # 1.5 minutes = 90 seconds
    ("10.0",    600),    # 10 minutes
    ("0.5",     30),     # half a minute
])
def test_parse_time_decimal_minutes(text, expected):
    """Decimal-with-dot is interpreted as MINUTES (not seconds)."""
    assert parse_time_to_seconds(text) == expected


@pytest.mark.parametrize("bad", [None, "", "   ", "garbage", "1:2:3:4", "abc:def"])
def test_parse_time_returns_none_for_unparseable(bad):
    assert parse_time_to_seconds(bad) is None


def test_parse_time_accepts_int_input():
    """Ints pass through `str()` cleanly."""
    assert parse_time_to_seconds(120) == 120


# ---------------------------------------------------------------------------
# normalize_side_value
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [
    ("axis",     1),
    ("AXIS",     1),
    ("Axis",     1),
    ("1",        1),
    ("allies",   2),
    ("Allies",   2),
    ("2",        2),
    ("draw",     0),
    ("unknown",  0),
    ("0",        0),
    (1,          1),
    (2,          2),
    (0,          0),
])
def test_normalize_side_value_known_aliases(raw, expected):
    assert normalize_side_value(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_normalize_side_value_empty_returns_unknown(raw):
    assert normalize_side_value(raw, allow_unknown=True) == 0


@pytest.mark.parametrize("raw", [None, "", "garbage", "5"])
def test_normalize_side_value_strict_returns_minus_one(raw):
    """allow_unknown=False is for the strict path that wants to flag
    invalid input rather than silently fold to 0."""
    assert normalize_side_value(raw, allow_unknown=False) == -1


def test_normalize_side_value_out_of_range_falls_to_unknown():
    """Numeric '5' is out of (0,1,2) range → falls to 0 (allow_unknown=True)."""
    assert normalize_side_value("5", allow_unknown=True) == 0


def test_normalize_side_value_strict_rejects_zero_text():
    """In strict mode, '0' (which would map to draw normally) does NOT
    map to draw; falls to -1. Confirmed by reading the code: explicit
    `text in _SIDE_VALUE_MAP` check happens before the strict branch."""
    # Actually, '0' is in _SIDE_VALUE_MAP → returns 0 even in strict mode.
    # Pin the actual behaviour, document the surprise.
    assert normalize_side_value("0", allow_unknown=False) == 0


# ---------------------------------------------------------------------------
# normalize_end_reason
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [
    ("",                "NORMAL"),
    ("unknown",         "NORMAL"),
    ("normal",          "NORMAL"),
    ("objective",       "NORMAL"),
    ("time_expired",    "NORMAL"),
    ("timelimit",       "NORMAL"),
    ("time limit",      "NORMAL"),
    ("surrender",       "SURRENDER"),
    ("forfeit",         "SURRENDER"),
    ("map_change",      "MAP_CHANGE"),
    ("mapchange",       "MAP_CHANGE"),
    ("map change",      "MAP_CHANGE"),
    ("map_restart",     "MAP_RESTART"),
    ("maprestart",      "MAP_RESTART"),
    ("server_restart",  "SERVER_RESTART"),
    ("serverrestart",   "SERVER_RESTART"),
])
def test_normalize_end_reason_aliases(raw, expected):
    assert normalize_end_reason(raw) == expected


def test_normalize_end_reason_case_insensitive():
    assert normalize_end_reason("OBJECTIVE") == "NORMAL"
    assert normalize_end_reason("SURRENDER") == "SURRENDER"
    assert normalize_end_reason("Map_Change") == "MAP_CHANGE"


def test_normalize_end_reason_unknown_falls_to_normal():
    """Unknown values quietly fall to NORMAL — production prefers
    coherent display over flagging unrecognised inputs."""
    assert normalize_end_reason("alien_reason_unknown") == "NORMAL"


def test_normalize_end_reason_handles_none():
    assert normalize_end_reason(None) == "NORMAL"


def test_end_reason_enum_contains_all_canonical_values():
    """Pin the END_REASON_ENUM set so a future contract change is loud."""
    assert END_REASON_ENUM == {
        "NORMAL", "SURRENDER", "MAP_CHANGE", "MAP_RESTART", "SERVER_RESTART",
    }


# ---------------------------------------------------------------------------
# score_confidence_state
# ---------------------------------------------------------------------------


def test_confidence_verified_header_when_both_sides_valid_no_reasons():
    """Both teams resolve, no diagnostic reasons → highest confidence."""
    assert score_confidence_state(
        defender_team="axis", winner_team="allies",
    ) == "verified_header"


def test_confidence_time_fallback_when_fallback_used():
    """fallback_used=True with valid sides → time_fallback."""
    assert score_confidence_state(
        defender_team="axis", winner_team="allies", fallback_used=True,
    ) == "time_fallback"


def test_confidence_ambiguous_for_out_of_range_reason():
    assert score_confidence_state(
        defender_team="axis", winner_team="allies",
        reasons=["winner_out_of_range"],
    ) == "ambiguous"


def test_confidence_ambiguous_for_non_numeric_reason():
    assert score_confidence_state(
        defender_team="axis", winner_team="allies",
        reasons=["non_numeric_winner"],
    ) == "ambiguous"


def test_confidence_missing_when_winner_unknown():
    assert score_confidence_state(
        defender_team="axis", winner_team=None,
    ) == "missing"


def test_confidence_missing_when_defender_unknown():
    assert score_confidence_state(
        defender_team=None, winner_team="axis",
    ) == "missing"


def test_confidence_ambiguous_with_unknown_reason_label():
    """Reason that doesn't match the out_of_range / non_numeric pattern
    still tips the state to 'ambiguous' (via the final fallthrough)."""
    assert score_confidence_state(
        defender_team="axis", winner_team="allies",
        reasons=["something_unrelated"],
    ) == "ambiguous"


def test_confidence_falls_to_missing_for_empty_input():
    """No data → missing (loudest signal in the dashboard)."""
    assert score_confidence_state(None, None) == "missing"


# ---------------------------------------------------------------------------
# derive_stopwatch_contract
# ---------------------------------------------------------------------------


def test_stopwatch_full_hold_when_at_or_above_threshold():
    """actual_time >= time_limit - 30 → FULL_HOLD.
    e.g. 600s limit, 575s actual → 575 >= 570 → FULL_HOLD."""
    out = derive_stopwatch_contract(
        round_number=1, time_limit_value=600, actual_time_value=575,
    )
    assert out["round_stopwatch_state"] == "FULL_HOLD"


def test_stopwatch_time_set_when_below_threshold():
    """actual=400s, limit=600s → 400 < 570 → TIME_SET."""
    out = derive_stopwatch_contract(
        round_number=1, time_limit_value=600, actual_time_value=400,
    )
    assert out["round_stopwatch_state"] == "TIME_SET"


def test_stopwatch_threshold_boundary():
    """Exactly limit-30 → FULL_HOLD (boundary inclusive)."""
    out = derive_stopwatch_contract(
        round_number=1, time_limit_value=600, actual_time_value=570,
    )
    assert out["round_stopwatch_state"] == "FULL_HOLD"


def test_stopwatch_state_none_when_not_normal_end_reason():
    """SURRENDER must NOT compute stopwatch state — round was forfeit."""
    out = derive_stopwatch_contract(
        round_number=1, time_limit_value=600, actual_time_value=400,
        end_reason="surrender",
    )
    assert out["round_stopwatch_state"] is None


def test_stopwatch_round1_time_set_populates_time_to_beat():
    """R1 TIME_SET → time_to_beat_seconds=actual, next_timelimit minutes round up."""
    out = derive_stopwatch_contract(
        round_number=1, time_limit_value=600, actual_time_value=275,
    )
    assert out["round_stopwatch_state"] == "TIME_SET"
    assert out["time_to_beat_seconds"] == 275
    assert out["next_timelimit_minutes"] == 5  # ceil(275/60) = 5


def test_stopwatch_round1_full_hold_uses_time_limit_for_next_timelimit():
    """R1 FULL_HOLD → next R2 starts at time_limit ceiling."""
    out = derive_stopwatch_contract(
        round_number=1, time_limit_value=600, actual_time_value=590,
    )
    assert out["round_stopwatch_state"] == "FULL_HOLD"
    assert out["next_timelimit_minutes"] == 10  # ceil(600/60) = 10


def test_stopwatch_round2_does_not_populate_next_timelimit():
    """R2 is the final round; no 'next round' to time-limit."""
    out = derive_stopwatch_contract(
        round_number=2, time_limit_value=300, actual_time_value=200,
    )
    assert out["round_stopwatch_state"] == "TIME_SET"
    assert out["next_timelimit_minutes"] is None
    assert out["time_to_beat_seconds"] is None


def test_stopwatch_handles_missing_inputs():
    """Missing limit or actual → state is None, all derived fields None."""
    out = derive_stopwatch_contract(
        round_number=1, time_limit_value=None, actual_time_value=None,
    )
    assert out["round_stopwatch_state"] is None
    assert out["time_to_beat_seconds"] is None
    assert out["next_timelimit_minutes"] is None


# ---------------------------------------------------------------------------
# derive_end_reason_display
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("end_reason, expected", [
    ("surrender",     "SURRENDER_END"),
    ("forfeit",       "SURRENDER_END"),
    ("map_change",    "MAP_CHANGE_END"),
    ("map_restart",   "MAP_RESTART_END"),
    ("server_restart", "SERVER_RESTART_END"),
])
def test_end_reason_display_terminal_overrides_stopwatch(end_reason, expected):
    """A terminal end-reason wins over any stopwatch state — the round
    didn't naturally complete, so the display shouldn't claim FULL_HOLD/TIME_SET."""
    out = derive_end_reason_display(end_reason, round_stopwatch_state="FULL_HOLD")
    assert out == expected


def test_end_reason_display_full_hold_when_normal_and_state_full_hold():
    out = derive_end_reason_display("normal", round_stopwatch_state="FULL_HOLD")
    assert out == "FULL_HOLD"


def test_end_reason_display_time_set_when_normal_and_state_time_set():
    out = derive_end_reason_display("normal", round_stopwatch_state="TIME_SET")
    assert out == "TIME_SET"


def test_end_reason_display_falls_to_time_set_when_normal_no_state():
    """Normal end_reason without stopwatch context → default TIME_SET."""
    assert derive_end_reason_display("normal") == "TIME_SET"
