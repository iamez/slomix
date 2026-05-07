"""Tests for PredictionEmbedBuilder pure helpers + color constants.

This builder renders Discord embeds for `!predict`. A regression silently:

- Probability bars don't visually align with `XX%` label.
- Roster overflow → embed exceeds Discord 1024-char field limit.
- Mini-bar color logic flipped → blue when red expected (mis-attribution).
- Confidence color → red when high (operator panic).

Pure helpers are testable without Discord.
"""
from __future__ import annotations

import pytest

from bot.services.prediction_embed_builder import PredictionEmbedBuilder


@pytest.fixture
def builder():
    return PredictionEmbedBuilder()


# ---------------------------------------------------------------------------
# Color constants — pin RGB values
# ---------------------------------------------------------------------------


def test_color_constants():
    """Pin the canonical confidence palette. A regression that swaps
    high/low silently flips the visual signal in every prediction
    embed (operator sees red for high-confidence predictions)."""
    assert PredictionEmbedBuilder.COLOR_HIGH_CONFIDENCE == 0x00FF00
    assert PredictionEmbedBuilder.COLOR_MEDIUM_CONFIDENCE == 0xFFA500
    assert PredictionEmbedBuilder.COLOR_LOW_CONFIDENCE == 0xFF0000


# ---------------------------------------------------------------------------
# _create_probability_bar — visual fill bar
# ---------------------------------------------------------------------------


def test_probability_bar_zero(builder):
    """0.0 → all empty, "0%" label."""
    out = builder._create_probability_bar(0.0)
    assert "█" not in out
    assert "0%" in out
    assert out.count("░") == 10  # default length


def test_probability_bar_full(builder):
    out = builder._create_probability_bar(1.0)
    assert out.count("█") == 10
    assert "░" not in out
    assert "100%" in out


def test_probability_bar_50pct_has_5_filled(builder):
    out = builder._create_probability_bar(0.5)
    assert out.count("█") == 5
    assert out.count("░") == 5
    assert "50%" in out


def test_probability_bar_respects_length(builder):
    """Custom length scales the bar — pin so embed alignment is
    customisable."""
    out = builder._create_probability_bar(0.5, length=20)
    assert out.count("█") == 10
    assert out.count("░") == 10


def test_probability_bar_truncates_decimal_to_zero_decimals(builder):
    """0.654 → '65%' (rounded to 0 decimals via :.0% format)."""
    out = builder._create_probability_bar(0.654)
    assert "65%" in out
    assert ".5" not in out  # no decimal point in label


# ---------------------------------------------------------------------------
# _format_team_roster — name display + size cap
# ---------------------------------------------------------------------------


def test_format_roster_no_names_returns_count(builder):
    """player_names=None → fallback "N players"."""
    out = builder._format_team_roster(["g1", "g2", "g3"], player_names=None)
    assert out == "3 players"


def test_format_roster_no_names_handles_empty(builder):
    out = builder._format_team_roster([], player_names=None)
    assert out == "0 players"


def test_format_roster_uses_provided_names(builder):
    out = builder._format_team_roster(
        ["g1", "g2"],
        player_names={"g1": "Alice", "g2": "Bob"},
    )
    assert "Alice" in out
    assert "Bob" in out
    assert ", " in out  # comma-separated


def test_format_roster_falls_back_to_short_guid_for_unknown(builder):
    """Player name not in mapping → "Player_<short>" placeholder.

    Note: an EMPTY dict is falsy and falls into the "no names" path.
    The placeholder fallback only fires when the dict is non-empty
    but doesn't contain THIS guid (typical batch fetch with partial
    coverage)."""
    out = builder._format_team_roster(
        ["unknown-guid-12345"],
        player_names={"other-guid": "OtherPlayer"},  # non-empty, no match
    )
    assert "Player_" in out


def test_format_roster_falls_back_to_count_when_dict_empty(builder):
    """Empty dict {} is falsy → "N players" fallback (NOT placeholder
    formatting). Pin observed behaviour — caller must pass either
    None or a populated dict."""
    out = builder._format_team_roster(["g1"], player_names={})
    assert out == "1 players"


def test_format_roster_caps_at_six_names_with_overflow_label(builder):
    """7+ names → first 6 + "...+N more". Pin so embed field stays
    under 1024 chars even with long rosters."""
    guids = [f"g{i}" for i in range(8)]
    names = {f"g{i}": f"Player{i}" for i in range(8)}
    out = builder._format_team_roster(guids, player_names=names)
    assert "Player0" in out
    assert "Player5" in out
    assert "+2 more" in out
    assert "Player6" not in out
    assert "Player7" not in out


def test_format_roster_six_names_no_overflow(builder):
    """Exactly 6 names → all shown, NO overflow message."""
    guids = [f"g{i}" for i in range(6)]
    names = {f"g{i}": f"Player{i}" for i in range(6)}
    out = builder._format_team_roster(guids, player_names=names)
    assert "+0 more" not in out
    assert "+more" not in out
    assert "Player5" in out


def test_format_roster_mixed_known_and_unknown(builder):
    out = builder._format_team_roster(
        ["g1", "unknown"],
        player_names={"g1": "Alice"},
    )
    assert "Alice" in out
    assert "Player_" in out  # placeholder for unknown


# ---------------------------------------------------------------------------
# _create_mini_bar — factor score visual
# ---------------------------------------------------------------------------


def test_mini_bar_neutral_when_score_is_half(builder):
    """0.5 score → neutral white circles. Pin neutral signal."""
    out = builder._create_mini_bar(0.5)
    assert all(ch == "⚪" for ch in out)
    assert len(out) == 5  # default length


def test_mini_bar_team_a_favored_above_half(builder):
    """0.8 score → 4/5 blue + 1/5 white. Pin color (blue=Team A)."""
    out = builder._create_mini_bar(0.8)
    assert "🔵" in out
    assert "🔴" not in out
    assert out.count("🔵") == 4
    assert out.count("⚪") == 1


def test_mini_bar_team_b_favored_below_half(builder):
    """0.2 score → red (Team B). Pin color."""
    out = builder._create_mini_bar(0.2)
    assert "🔴" in out
    assert "🔵" not in out


def test_mini_bar_neutral_when_close_to_half(builder):
    """abs(filled - empty) <= 1 → neutral. Pin so a 0.4 score doesn't
    aggressively render as Team B (caller intent is "nearly even")."""
    # 0.4 * 5 = 2 filled, 3 empty → abs(2-3)=1 → neutral
    out = builder._create_mini_bar(0.4)
    assert all(ch == "⚪" for ch in out)


def test_mini_bar_respects_length_argument(builder):
    out = builder._create_mini_bar(1.0, length=10)
    assert out.count("🔵") == 10


def test_mini_bar_zero_score_renders_team_b(builder):
    """0.0 → 0 filled, 5 empty → abs(0-5)=5 > 1 → not neutral.
    But filled < empty → Team B → 0 red + 5 white. Pin observed."""
    out = builder._create_mini_bar(0.0)
    # Implementation: 🔴 * filled (0) + ⚪ * empty (5) = "⚪⚪⚪⚪⚪"
    assert out == "⚪⚪⚪⚪⚪"


def test_mini_bar_full_score_renders_team_a(builder):
    """1.0 → 5 filled, 0 empty → not neutral, filled > empty → blue."""
    out = builder._create_mini_bar(1.0)
    assert out == "🔵🔵🔵🔵🔵"


# ---------------------------------------------------------------------------
# _format_factor_breakdown — combines mini bars + details
# ---------------------------------------------------------------------------


def test_factor_breakdown_includes_all_four_factors(builder):
    """Output must include H2H, Form, Map, Subs lines."""
    factors = {
        "h2h":  {"score": 0.5, "details": "h2h-detail"},
        "form": {"score": 0.5, "details": "form-detail"},
        "map":  {"score": 0.5, "details": "map-detail"},
        "subs": {"score": 0.5, "details": "subs-detail"},
    }
    out = builder._format_factor_breakdown(factors)
    assert "Head-to-Head" in out
    assert "Recent Form" in out
    assert "Map Performance" in out
    assert "Substitutions" in out
    assert "h2h-detail" in out
    assert "form-detail" in out


def test_factor_breakdown_uses_mini_bar_for_score(builder):
    """Each factor row contains a mini-bar rendering of its score."""
    factors = {
        "h2h":  {"score": 1.0, "details": "X"},
        "form": {"score": 0.0, "details": "X"},
        "map":  {"score": 0.5, "details": "X"},
        "subs": {"score": 0.5, "details": "X"},
    }
    out = builder._format_factor_breakdown(factors)
    assert "🔵" in out  # h2h is full → blue
    assert "⚪" in out  # form/map/subs are 0 or 0.5 → contains white


def test_factor_breakdown_falls_back_to_NA_when_details_missing(builder):
    """Missing 'details' → 'N/A' placeholder, NOT crash."""
    factors = {
        "h2h":  {"score": 0.5},
        "form": {"score": 0.5},
        "map":  {"score": 0.5},
        "subs": {"score": 0.5},
    }
    out = builder._format_factor_breakdown(factors)
    assert "N/A" in out


def test_factor_breakdown_renders_one_line_per_factor(builder):
    factors = {
        "h2h":  {"score": 0.5, "details": "x"},
        "form": {"score": 0.5, "details": "x"},
        "map":  {"score": 0.5, "details": "x"},
        "subs": {"score": 0.5, "details": "x"},
    }
    out = builder._format_factor_breakdown(factors)
    assert out.count("\n") == 3  # 4 lines = 3 newlines
