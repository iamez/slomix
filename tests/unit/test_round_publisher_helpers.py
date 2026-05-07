"""Tests for RoundPublisherService static helpers.

These five staticmethods are pure formatters/parsers used in every
`!last_session` style embed render. A regression in `_chunk_embed_lines`
in particular would push >1024-char fields into Discord and silently
truncate content; a regression in `_format_delta_seconds` would flip
sign on win/loss deltas. Pin each contract.
"""
from __future__ import annotations

import pytest

from bot.services.round_publisher_service import RoundPublisherService


# ---------------------------------------------------------------------------
# _derive_side_marker
# ---------------------------------------------------------------------------


def test_derive_side_marker_axis_only():
    assert RoundPublisherService._derive_side_marker(3, 0) == ("[AXIS]", False)


def test_derive_side_marker_allies_only():
    assert RoundPublisherService._derive_side_marker(0, 3) == ("[ALLIES]", False)


def test_derive_side_marker_mixed_is_ambiguous():
    """A player with rows on BOTH sides → MIXED + ambiguous=True so the
    embed render can flag it (player swapped teams mid-round)."""
    assert RoundPublisherService._derive_side_marker(2, 1) == ("[MIXED]", True)


def test_derive_side_marker_no_rows_is_unknown_ambiguous():
    """Both zero → UNK + ambiguous (parser couldn't attribute the player)."""
    assert RoundPublisherService._derive_side_marker(0, 0) == ("[UNK]", True)


def test_derive_side_marker_handles_none_inputs():
    """None coerces via int(... or 0); pin that resilience."""
    assert RoundPublisherService._derive_side_marker(None, None) == ("[UNK]", True)


def test_derive_side_marker_handles_string_numerics():
    """asyncpg sometimes returns numerics as strings — int() coerces."""
    assert RoundPublisherService._derive_side_marker("3", "0") == ("[AXIS]", False)


# ---------------------------------------------------------------------------
# _chunk_embed_lines
# ---------------------------------------------------------------------------


def test_chunk_returns_empty_for_no_lines():
    assert RoundPublisherService._chunk_embed_lines([]) == []
    assert RoundPublisherService._chunk_embed_lines(None) == []


def test_chunk_keeps_short_lines_in_one_chunk():
    lines = ["a", "b", "c"]
    out = RoundPublisherService._chunk_embed_lines(lines)
    assert len(out) == 1
    assert out[0] == "a\n\nb\n\nc"


def test_chunk_splits_when_combined_exceeds_max():
    """Chunks roll over BEFORE adding a line that pushes past max_chars."""
    # 3 lines of 500 chars each = 1500 raw + separators
    long_lines = ["x" * 500, "y" * 500, "z" * 500]
    out = RoundPublisherService._chunk_embed_lines(long_lines, max_chars=1024)
    # 500 + 2 + 500 = 1002 fits; adding next 500 = 1504 doesn't → split
    assert len(out) == 2
    assert all(len(c) <= 1024 for c in out)


def test_chunk_truncates_a_single_oversized_line():
    """A single line longer than max_chars gets truncated with '...'.
    Without this, Discord would reject the embed entirely."""
    huge = "x" * 2000
    out = RoundPublisherService._chunk_embed_lines([huge], max_chars=100)
    assert len(out) == 1
    assert len(out[0]) == 100
    assert out[0].endswith("...")


def test_chunk_default_separator_is_double_newline():
    """Default separator forms paragraph spacing in the Discord embed."""
    out = RoundPublisherService._chunk_embed_lines(["a", "b"])
    assert "\n\n" in out[0]


def test_chunk_custom_separator_is_used():
    out = RoundPublisherService._chunk_embed_lines(["a", "b"], separator=" | ")
    assert out == ["a | b"]


def test_chunk_default_max_is_1024():
    """Discord embed field value limit is 1024. Pin the default explicitly."""
    line_999 = "x" * 999
    out = RoundPublisherService._chunk_embed_lines([line_999, "yy"])
    # 999 + 2 + 2 = 1003 ≤ 1024 → one chunk
    assert len(out) == 1


# ---------------------------------------------------------------------------
# _parse_time_to_seconds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text, expected", [
    ("4:30",     270),       # MM:SS
    ("0:00",     0),
    ("1:00:00",  3600),      # HH:MM:SS
    ("0:04:30",  270),
    ("60",       60),        # plain numeric → seconds
    ("0",        0),
    ("1.5",      90),        # decimal → minutes (1.5 min = 90 sec)
])
def test_parse_time_known_formats(text, expected):
    assert RoundPublisherService._parse_time_to_seconds(text) == expected


@pytest.mark.parametrize("bad", [
    None, "", "   ", "unknown", "UNKNOWN", "Unknown",
    "garbage", "abc:def", "1:2:3:4",
])
def test_parse_time_returns_none_for_unparseable(bad):
    assert RoundPublisherService._parse_time_to_seconds(bad) is None


def test_parse_time_handles_int_input():
    assert RoundPublisherService._parse_time_to_seconds(120) == 120


# ---------------------------------------------------------------------------
# _format_seconds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seconds, expected", [
    (0,      "0:00"),
    (1,      "0:01"),
    (59,     "0:59"),
    (60,     "1:00"),
    (61,     "1:01"),
    (599,    "9:59"),
    (600,    "10:00"),
    (3600,   "60:00"),  # 1h rendered as MM:SS — no HH rollover
])
def test_format_seconds_known_values(seconds, expected):
    assert RoundPublisherService._format_seconds(seconds) == expected


def test_format_seconds_negative_clamps_to_zero():
    """Defensive: negative seconds (clock skew) shouldn't display as
    "-1:00"; clamp to 0:00."""
    assert RoundPublisherService._format_seconds(-30) == "0:00"


def test_format_seconds_handles_none():
    assert RoundPublisherService._format_seconds(None) == "0:00"


def test_format_seconds_zero_pads_seconds():
    """5 seconds renders as 0:05, not 0:5 — required for MM:SS layout."""
    assert RoundPublisherService._format_seconds(5) == "0:05"


# ---------------------------------------------------------------------------
# _format_delta_seconds
# ---------------------------------------------------------------------------


def test_format_delta_zero_has_no_sign():
    """0 is unsigned (no `+0:00` because 0 isn't a positive delta)."""
    assert RoundPublisherService._format_delta_seconds(0) == "0:00"


@pytest.mark.parametrize("delta, expected", [
    (1,      "+0:01"),
    (60,     "+1:00"),
    (75,     "+1:15"),
    (-1,     "-0:01"),
    (-90,    "-1:30"),
    (-3661,  "-61:01"),
])
def test_format_delta_signed_values(delta, expected):
    assert RoundPublisherService._format_delta_seconds(delta) == expected


def test_format_delta_handles_none():
    assert RoundPublisherService._format_delta_seconds(None) == "0:00"


def test_format_delta_negative_zero_seconds_is_unsigned():
    """`-0` → 0 → "0:00" (not "-0:00"). Pin that the abs() + zero-check
    branch comes before the sign assignment."""
    assert RoundPublisherService._format_delta_seconds(-0) == "0:00"


def test_format_delta_seconds_zero_pad():
    """+0:05 not +0:5 — same MM:SS rule as _format_seconds."""
    assert RoundPublisherService._format_delta_seconds(5) == "+0:05"
