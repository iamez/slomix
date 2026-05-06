"""Tests for SessionEmbedBuilder pure helpers.

These four staticmethods + one instance method are the foundation of
every session embed (`!last_session`). A regression silently:

- Pushes a >1024-char field to Discord → 400 error → entire embed
  fails → user sees no session summary.
- Mis-formats delta times → +/- swapped → operator misreads timing.
- Mis-categorises endstats values → "100 damage" shown as "100%".

Pin every branch.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from bot.services.session_embed_builder import SessionEmbedBuilder


@pytest.fixture
def builder():
    """Build an instance — _format_endstats_value is non-static, others
    are staticmethods but we use the instance accessor for uniformity."""
    return SessionEmbedBuilder(timing_shadow_service=MagicMock())


# ---------------------------------------------------------------------------
# _safe_field_value — Discord 1024-char limit guard
# ---------------------------------------------------------------------------


def test_safe_field_passes_short_text_unchanged():
    out = SessionEmbedBuilder._safe_field_value("hello")
    assert out == "hello"


def test_safe_field_passes_text_at_exact_limit():
    """Exactly 1024 chars → unchanged (limit is inclusive)."""
    text = "x" * 1024
    out = SessionEmbedBuilder._safe_field_value(text)
    assert out == text


def test_safe_field_truncates_above_limit_with_marker():
    """>1024 chars → truncated to 1020 + "\\n...". Pin so a regression
    that drops the marker silently corrupts the embed."""
    text = "x" * 2000
    out = SessionEmbedBuilder._safe_field_value(text)
    assert len(out) == 1024  # 1020 + "\n..." = 1024 chars
    assert out.endswith("\n...")


def test_safe_field_custom_max_chars():
    """Custom limit honoured for nested embeds with smaller fields."""
    out = SessionEmbedBuilder._safe_field_value("x" * 100, max_chars=50)
    assert len(out) == 50
    assert out.endswith("\n...")


def test_safe_field_empty_string():
    assert SessionEmbedBuilder._safe_field_value("") == ""


# ---------------------------------------------------------------------------
# _chunk_field_lines — split lines to fit field limit
# ---------------------------------------------------------------------------


def test_chunk_returns_empty_for_no_lines():
    assert SessionEmbedBuilder._chunk_field_lines([]) == []


def test_chunk_keeps_short_lines_in_one_chunk():
    """3 short lines → single chunk."""
    out = SessionEmbedBuilder._chunk_field_lines(["a", "b", "c"])
    assert out == ["a\nb\nc"]


def test_chunk_splits_when_combined_exceeds_max_chars():
    """Joined size > max_chars → split into multiple chunks. Pin so
    a regression that uses >= instead of <= doesn't squeeze 1025
    chars into a 1024-cap field."""
    lines = ["x" * 600, "y" * 600]  # 600 + "\n" + 600 = 1201 > 1024
    out = SessionEmbedBuilder._chunk_field_lines(lines)
    assert len(out) == 2
    assert out[0] == "x" * 600
    assert out[1] == "y" * 600


def test_chunk_truncates_individual_oversized_line():
    """A single line that exceeds max_chars is truncated with "..."
    suffix. Pin so a single fat row doesn't crash the whole embed."""
    line = "x" * 2000
    out = SessionEmbedBuilder._chunk_field_lines([line], max_chars=100)
    assert len(out) == 1
    assert len(out[0]) == 100
    assert out[0].endswith("...")


def test_chunk_uses_custom_separator():
    """Default is "\\n"; custom separator must be honoured."""
    out = SessionEmbedBuilder._chunk_field_lines(
        ["a", "b", "c"], separator=" | ",
    )
    assert out == ["a | b | c"]


def test_chunk_packs_as_many_lines_per_chunk_as_fit():
    """Greedy packing: each chunk holds the max number of lines that
    fit. Pin so a regression that flushes early bloats the embed
    field count."""
    lines = ["aaa"] * 100  # 3 chars + "\n" = 4 each, ~256 lines per 1024
    out = SessionEmbedBuilder._chunk_field_lines(lines, max_chars=20)
    # 20 chars / (3+1) = 5 lines per chunk → ceil(100/5) = 20 chunks
    # First chunk: "aaa\naaa\naaa\naaa\naaa" = 19 chars ✓
    assert all(len(c) <= 20 for c in out)


# ---------------------------------------------------------------------------
# _format_delta_seconds — signed MM:SS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("delta, expected", [
    (0,    "0:00"),
    (60,   "+1:00"),
    (-60,  "-1:00"),
    (90,   "+1:30"),
    (-125, "-2:05"),
    (3600, "+60:00"),
])
def test_format_delta_known_values(delta, expected):
    assert SessionEmbedBuilder._format_delta_seconds(delta) == expected


def test_format_delta_zero_has_no_sign():
    """0 → "0:00" (no + or -)."""
    out = SessionEmbedBuilder._format_delta_seconds(0)
    assert "+" not in out
    assert "-" not in out


def test_format_delta_handles_none():
    """`None` → "0:00" (treated as zero). Pin fail-safe."""
    out = SessionEmbedBuilder._format_delta_seconds(None)
    assert out == "0:00"


def test_format_delta_handles_float_truncated():
    """Float input → int conversion truncates fractional seconds."""
    out = SessionEmbedBuilder._format_delta_seconds(60.7)
    # int(60.7) = 60 → "+1:00"
    assert out == "+1:00"


def test_format_delta_seconds_zero_padded():
    """Sub-10 second values pad with leading zero ("+1:05" NOT "+1:5")."""
    out = SessionEmbedBuilder._format_delta_seconds(65)
    assert out == "+1:05"


# ---------------------------------------------------------------------------
# _format_endstats_value — value → display string by award category
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value, name, expected", [
    # Damage → K format ≥1000, plain int <1000
    (3200,  "Most damage given",        "3.2K"),
    (500,   "Most damage given",        "500"),
    # Accuracy → percent
    (52,    "Highest accuracy",         "52%"),
    (99.5,  "Highest light accuracy",   "100%"),
    # Time / spawn → m:ss
    (150,   "Longest spawn time",       "2:30"),
    (60,    "Most time alive",          "1:00"),
    # Ratio → 2 decimals
    (3.14,  "Best K/D ratio",           "3.14"),
    # Default ≥1000 → K
    (2000,  "Most kills",               "2.0K"),
    (5,     "Most kills",               "5"),
    (3.5,   "Most rifle kills",         "3.5"),
])
def test_format_endstats_value_known_categories(builder, value, name, expected):
    """Pin the format truth table — same shape as endstats_aggregator
    but separate codepath. A regression in either drift breaks
    visual consistency between !round and !last_session embeds."""
    assert builder._format_endstats_value(value, name) == expected


def test_format_endstats_handles_none(builder):
    """None value → "0" placeholder (pin so missing data doesn't
    crash the embed builder)."""
    assert builder._format_endstats_value(None, "Most kills") == "0"


def test_format_endstats_priority_damage_before_default(builder):
    """A >1000 damage value uses K via the damage branch, NOT default."""
    out = builder._format_endstats_value(3000, "Most damage given")
    assert out == "3.0K"


def test_format_endstats_priority_accuracy_over_default(builder):
    """High accuracy value would render 'K' under default — pin
    accuracy precedence so 99% never becomes "0.1K"."""
    out = builder._format_endstats_value(99, "Highest accuracy")
    assert out == "99%"


def test_format_endstats_zero_value_handled_per_category(builder):
    assert builder._format_endstats_value(0, "Most damage given") == "0"
    assert builder._format_endstats_value(0, "Most kills") == "0"
    assert builder._format_endstats_value(0, "Highest accuracy") == "0%"
    assert builder._format_endstats_value(0, "Best ratio") == "0.00"
