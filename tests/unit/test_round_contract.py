from __future__ import annotations

from bot.core.round_contract import (
    normalize_side_value,
    score_confidence_state,
    normalize_end_reason,
    derive_stopwatch_contract,
    derive_end_reason_display,
)


def test_normalize_side_value_supports_int_and_aliases():
    assert normalize_side_value(1) == 1
    assert normalize_side_value(2) == 2
    assert normalize_side_value("axis") == 1
    assert normalize_side_value("allies") == 2
    assert normalize_side_value("draw") == 0
    assert normalize_side_value("unknown") == 0


def test_score_confidence_state_variants():
    assert score_confidence_state(1, 2, reasons=[]) == "verified_header"
    assert score_confidence_state(1, 0, reasons=[]) == "missing"
    assert score_confidence_state(1, 2, reasons=["winner_non_numeric"]) == "ambiguous"
    assert (
        score_confidence_state(1, 2, reasons=["winner_fallback_from_round1"], fallback_used=True)
        == "time_fallback"
    )


def test_normalize_end_reason_to_enum():
    assert normalize_end_reason("surrender") == "SURRENDER"
    assert normalize_end_reason("objective") == "NORMAL"
    assert normalize_end_reason("time_expired") == "NORMAL"
    assert normalize_end_reason("mapchange") == "MAP_CHANGE"
    assert normalize_end_reason("map_restart") == "MAP_RESTART"
    assert normalize_end_reason("serverrestart") == "SERVER_RESTART"
    assert normalize_end_reason(None) == "NORMAL"


def test_derive_stopwatch_contract_r1_time_set_and_fullhold():
    # Round 1, attackers set time in 8:30 on 20:00 map.
    set_case = derive_stopwatch_contract(1, "20:00", "8:30", end_reason="NORMAL")
    assert set_case["round_stopwatch_state"] == "TIME_SET"
    assert set_case["time_to_beat_seconds"] == 510
    assert set_case["next_timelimit_minutes"] == 9

    # Round 1, hold near timelimit.
    hold_case = derive_stopwatch_contract(1, "20:00", "19:50", end_reason="NORMAL")
    assert hold_case["round_stopwatch_state"] == "FULL_HOLD"
    assert hold_case["time_to_beat_seconds"] is None
    assert hold_case["next_timelimit_minutes"] == 20


def test_derive_end_reason_display_classification():
    assert derive_end_reason_display("surrender", None) == "SURRENDER_END"
    assert derive_end_reason_display("map_change", None) == "MAP_CHANGE_END"
    assert derive_end_reason_display("map_restart", None) == "MAP_RESTART_END"
    assert derive_end_reason_display("server_restart", None) == "SERVER_RESTART_END"
    assert derive_end_reason_display("objective", "FULL_HOLD") == "FULL_HOLD"
    assert derive_end_reason_display("objective", "TIME_SET") == "TIME_SET"
