"""Tests for SessionViewHandlers pure static + factor helpers.

These tiny helpers shape every paginated `!last_session` view embed.
A regression silently:

- format_seconds: produces wrong MM:SS → operator misreads round
  durations.
- _format_delta_seconds: drops the `+` sign or returns "+0:00"
  (positive zero) → ambiguous "is this earlier or later".
- _parse_time_to_seconds: returns 0 for legitimate input → all
  rounds look "instant".
- _row_get: tuple/dict polymorphism breaks → AttributeError on
  dict-shaped rows.
- _normalize_round_factor_payload: clamp/validation drops legitimate
  factors → timing-shadow comparison is wrong for that session.

Pin every branch.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from bot.services.session_view_handlers import SessionViewHandlers


@pytest.fixture
def handlers():
    """Build a SessionViewHandlers — instance methods don't touch DB."""
    return SessionViewHandlers(
        db_adapter=MagicMock(),
        stats_calculator=MagicMock(),
    )


# ---------------------------------------------------------------------------
# format_seconds — MM:SS rendering
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("secs, expected", [
    (0,     "0:00"),
    (60,    "1:00"),
    (90,    "1:30"),
    (3600,  "60:00"),
    (5,     "0:05"),  # zero-padded
    (3661,  "61:01"),  # ≥1h still MM:SS
])
def test_format_seconds_known_values(secs, expected):
    assert SessionViewHandlers.format_seconds(secs) == expected


def test_format_seconds_handles_none():
    """None → "0:00" (fail-safe)."""
    assert SessionViewHandlers.format_seconds(None) == "0:00"


def test_format_seconds_rounds_floats():
    """5.7s → 6 → "0:06" (rounded, not truncated)."""
    assert SessionViewHandlers.format_seconds(5.7) == "0:06"


def test_format_seconds_handles_garbage():
    """Non-numeric input → "0:00" (try/except guard)."""
    assert SessionViewHandlers.format_seconds("abc") == "0:00"


# ---------------------------------------------------------------------------
# _format_delta_seconds — signed MM:SS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("delta, expected", [
    (60,   "+1:00"),
    (-60,  "-1:00"),
    (90,   "+1:30"),
    (-125, "-2:05"),
    (3600, "+60:00"),
    (5,    "+0:05"),
])
def test_format_delta_signed_values(delta, expected):
    assert SessionViewHandlers._format_delta_seconds(delta) == expected


def test_format_delta_zero_has_no_sign():
    """0 → "0:00" (NO + or -)."""
    out = SessionViewHandlers._format_delta_seconds(0)
    assert out == "0:00"


def test_format_delta_does_not_handle_none_directly():
    """OBSERVED: passing None raises TypeError (production code does
    `if delta_seconds > 0` BEFORE the `delta_seconds or 0` guard).
    Pin observed behaviour as a tripwire — a caller passing None
    crashes before reaching the abs(int(...)) safe path. Operators
    should pass 0 explicitly."""
    with pytest.raises(TypeError):
        SessionViewHandlers._format_delta_seconds(None)


def test_format_delta_negative_zero_seconds_is_unsigned():
    """Pin observed: 0 is sentinel for "unsigned 0:00" — pin so a
    regression that adds a sign to 0 is loud."""
    assert SessionViewHandlers._format_delta_seconds(0) == "0:00"
    assert "+" not in SessionViewHandlers._format_delta_seconds(0)
    assert "-" not in SessionViewHandlers._format_delta_seconds(0)


# ---------------------------------------------------------------------------
# _parse_time_to_seconds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value, expected", [
    ("10:30",  630),     # MM:SS
    ("1:00:30", 3630),   # HH:MM:SS
    ("0:00",   0),
    ("100",    100),     # raw int
    ("1.5",    90),      # decimal minutes (* 60)
    (60,       60),      # numeric int
    (None,     0),
    ("",       0),
    ("garbage", 0),
])
def test_parse_time_known_values(value, expected):
    assert SessionViewHandlers._parse_time_to_seconds(value) == expected


def test_parse_time_strips_whitespace():
    assert SessionViewHandlers._parse_time_to_seconds("  10:30  ") == 630


def test_parse_time_handles_garbage_in_components():
    """`abc:30` → 0 (try/except). Pin fail-safe so a parser glitch
    doesn't crash the view rendering."""
    assert SessionViewHandlers._parse_time_to_seconds("abc:30") == 0


# ---------------------------------------------------------------------------
# _row_get — tuple/dict polymorphism
# ---------------------------------------------------------------------------


def test_row_get_reads_dict_by_key():
    row = {"player_name": "Alice", "kills": 10}
    assert SessionViewHandlers._row_get(row, 0, "player_name") == "Alice"
    assert SessionViewHandlers._row_get(row, 1, "kills") == 10


def test_row_get_reads_tuple_by_index():
    row = ("Alice", 10, 5)
    assert SessionViewHandlers._row_get(row, 0, "ignored") == "Alice"
    assert SessionViewHandlers._row_get(row, 1, "ignored") == 10


def test_row_get_returns_default_for_missing_dict_key():
    row = {"a": 1}
    assert SessionViewHandlers._row_get(row, 0, "missing", default="X") == "X"


def test_row_get_returns_default_on_index_error():
    """Tuple index out of range → default. Pin so a short row from
    a partial query doesn't crash the embed builder."""
    row = ("a", "b")
    assert SessionViewHandlers._row_get(row, 99, "ignored", default=None) is None


def test_row_get_default_value_is_none_by_default():
    row = ()
    assert SessionViewHandlers._row_get(row, 0, "x") is None


def test_row_get_dict_uses_key_not_idx():
    """When row is dict, idx is IGNORED. Pin so a regression that
    falls through to row[idx] on a dict mis-reads."""
    row = {"a": "expected", "b": "wrong"}
    # idx 99 doesn't matter — key lookup wins
    assert SessionViewHandlers._row_get(row, 99, "a") == "expected"


# ---------------------------------------------------------------------------
# _normalize_round_factor_payload
# ---------------------------------------------------------------------------


def test_normalize_factors_returns_empty_for_none(handlers):
    assert handlers._normalize_round_factor_payload(None) == {}


def test_normalize_factors_dict_roundid_to_float(handlers):
    """Dict {round_id: factor} → cleaned dict with int keys + float vals."""
    out = handlers._normalize_round_factor_payload({"1": 0.95, "2": 1.05})
    assert out == {1: 0.95, 2: 1.05}


def test_normalize_factors_dict_with_round_factors_wrapper(handlers):
    """`{round_factors: {...}}` wrapper → unwrapped."""
    out = handlers._normalize_round_factor_payload({"round_factors": {"1": 0.9}})
    assert out == {1: 0.9}


def test_normalize_factors_dict_factors_key_alias(handlers):
    """`{factors: {...}}` and `{by_round: {...}}` are also unwrapped."""
    out = handlers._normalize_round_factor_payload({"factors": {"1": 0.5}})
    assert out == {1: 0.5}
    out = handlers._normalize_round_factor_payload({"by_round": {"2": 1.5}})
    assert out == {2: 1.5}


def test_normalize_factors_clamps_above_2(handlers):
    """Factors > 2.0 → clamped to 2.0. Pin the cap so an outlier
    timing-shadow value doesn't push KIS scores to absurd levels."""
    out = handlers._normalize_round_factor_payload({"1": 5.0})
    assert out == {1: 2.0}


def test_normalize_factors_drops_zero_or_negative(handlers):
    """Factor ≤ 0 → DROPPED (not clamped to 0). Pin so a parser
    glitch silently removes a round from comparison rather than
    falsely showing 0% timing change."""
    out = handlers._normalize_round_factor_payload({"1": 0.0, "2": -0.5, "3": 1.0})
    assert out == {3: 1.0}


def test_normalize_factors_skips_unparseable_keys(handlers):
    """Non-int round_id key → skipped without raising."""
    out = handlers._normalize_round_factor_payload({"abc": 1.0, "1": 0.9})
    assert out == {1: 0.9}


def test_normalize_factors_skips_unparseable_values(handlers):
    """Non-float factor → skipped."""
    out = handlers._normalize_round_factor_payload({"1": "oops", "2": 1.0})
    assert out == {2: 1.0}


def test_normalize_factors_list_of_dicts(handlers):
    """List shape: [{round_id, factor}, ...]."""
    out = handlers._normalize_round_factor_payload([
        {"round_id": 1, "factor": 0.8},
        {"round_id": 2, "factor": 1.2},
    ])
    assert out == {1: 0.8, 2: 1.2}


def test_normalize_factors_list_uses_id_alias(handlers):
    """List entry with `id` instead of `round_id` is honoured."""
    out = handlers._normalize_round_factor_payload([
        {"id": 5, "factor": 0.9},
    ])
    assert out == {5: 0.9}


def test_normalize_factors_list_uses_correction_factor_alias(handlers):
    """`correction_factor` and `duration_factor` are aliases for `factor`."""
    out = handlers._normalize_round_factor_payload([
        {"round_id": 1, "correction_factor": 0.7},
        {"round_id": 2, "duration_factor": 1.1},
    ])
    assert out == {1: 0.7, 2: 1.1}


def test_normalize_factors_list_skips_non_dict_items(handlers):
    """List with mixed types → only dicts processed."""
    out = handlers._normalize_round_factor_payload([
        {"round_id": 1, "factor": 0.9},
        "garbage",
        42,
        {"round_id": 2, "factor": 1.0},
    ])
    assert out == {1: 0.9, 2: 1.0}
