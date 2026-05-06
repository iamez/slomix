"""Tests for EndstatsAggregator pure helpers.

`_format_value`, `_categorize_awards`, `build_round_awards_display`,
`build_awards_display`, `build_vs_stats_display` are pure formatters
that drive the !last_session awards section in the bot's Discord
embeds. A regression silently:

- Mis-formats values (e.g. damage shown as kills) — confuses operators.
- Drops categories or limits — embed exceeds Discord's 1024-char field.
- Mis-categorises awards — pushes "Most damage" into "Other".

Pin the contract for each.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bot.services.endstats_aggregator import EndstatsAggregator


@pytest.fixture
def agg():
    """Build aggregator with a stub DB — pure helpers don't touch it."""
    return EndstatsAggregator(db_adapter=AsyncMock())


# ---------------------------------------------------------------------------
# _format_value — value → display string by award category
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value, award_name, expected", [
    # Accuracy → percentage
    (52.0,    "Highest light weapons accuracy", "52%"),
    (0.0,     "Highest headshot accuracy",      "0%"),
    (99.5,    "Best accuracy",                  "100%"),
    # Time → m:ss
    (150.0,   "Longest spawn time",             "2:30"),
    (60.0,    "Most time alive",                "1:00"),
    (5.0,     "Time test",                      "0:05"),
    # Ratio → 2 decimals
    (3.14,    "Best K/D ratio",                 "3.14"),
    (1.0,     "Damage ratio",                   "1.00"),
    # Damage → K format when ≥1000
    (3200.0,  "Most damage given",              "3.2K"),
    (1500.0,  "Most damage received",           "1.5K"),
    # Damage <1000 → no K, default formatting (integer-clean → int str)
    (500.0,   "Most damage given",              "500"),
    # Default: ≥1000 → K format
    (2000.0,  "Most kills",                     "2.0K"),
    # Default: integer-clean small value
    (5.0,     "Most kills",                     "5"),
    # Default: float with decimal
    (3.5,     "Most rifle kills",               "3.5"),
])
def test_format_value_known_categories(agg, value, award_name, expected):
    """Pin the full format truth table.

    A regression that swaps accuracy/ratio formats would silently flip
    every percentage to "X.YZ" instead of "X%"."""
    assert agg._format_value(value, award_name) == expected


def test_format_value_accuracy_takes_precedence_over_default(agg):
    """Award name with 'accuracy' wins over default formatting even
    when the value is large. Pin the priority."""
    out = agg._format_value(95.5, "Highest accuracy")
    assert out == "96%"  # rounded
    assert "K" not in out


def test_format_value_time_takes_precedence_over_damage(agg):
    """If award has both 'time' and 'damage' substrings (rare but
    possible), 'time' branch fires first. Pin priority."""
    out = agg._format_value(120.0, "Most time damage")
    assert out == "2:00"


def test_format_value_handles_zero_value(agg):
    """Zero is handled cleanly per category."""
    assert agg._format_value(0.0, "Most kills") == "0"
    assert agg._format_value(0.0, "Best ratio") == "0.00"
    assert agg._format_value(0.0, "Most damage") == "0"


# ---------------------------------------------------------------------------
# _categorize_awards — awards_by_name → categorised dict
# ---------------------------------------------------------------------------


def test_categorize_groups_by_AWARD_CATEGORIES_lookup(agg):
    """Awards are placed under their category from AWARD_CATEGORIES."""
    awards_by_name = {
        "Most damage given": [("guid1", "alice", 3200.0, 1)],
        "Most kills per minute": [("guid2", "bob", 30.0, 2)],
    }
    out = agg._categorize_awards(awards_by_name)
    assert "combat" in out
    assert "Most damage given" in out["combat"]
    assert "Most kills per minute" in out["combat"]


def test_categorize_unknown_award_goes_to_other(agg):
    """Award name not in AWARD_CATEGORIES → 'other' bucket. Pin so
    a future renamed award doesn't silently vanish from the embed."""
    awards_by_name = {
        "Brand new award nobody knows about": [("guid1", "alice", 1.0, 1)],
    }
    out = agg._categorize_awards(awards_by_name)
    assert "other" in out
    assert "Brand new award nobody knows about" in out["other"]


def test_categorize_returns_empty_dict_for_no_awards(agg):
    out = agg._categorize_awards({})
    assert out == {}


def test_categorize_preserves_player_data(agg):
    """The list of players is moved through unchanged."""
    players = [("g1", "a", 100.0, 2), ("g2", "b", 50.0, 1)]
    awards_by_name = {"Most damage given": players}
    out = agg._categorize_awards(awards_by_name)
    assert out["combat"]["Most damage given"] is players


# ---------------------------------------------------------------------------
# build_round_awards_display — per-round awards rendering
# ---------------------------------------------------------------------------


def test_build_round_returns_message_when_empty(agg):
    """Empty awards list → user-facing message (NOT empty string)."""
    out = agg.build_round_awards_display([])
    assert out == "*No awards recorded for this round*"


def test_build_round_includes_category_header(agg):
    awards = [{
        "name": "Most damage given",
        "player": "alice",
        "numeric": 1500.0,
        "value": "1500",
    }]
    out = agg.build_round_awards_display(awards)
    assert "**Combat**" in out
    assert "alice" in out
    assert "1.5K" in out  # _format_value applied


def test_build_round_uses_category_priority_order(agg):
    """combat (1) before skills (2) before objectives (6) — pin order."""
    awards = [
        {"name": "Most light weapon kills", "player": "skills_p",
         "numeric": 10, "value": ""},
        {"name": "Most damage given", "player": "combat_p",
         "numeric": 100, "value": ""},
    ]
    out = agg.build_round_awards_display(awards)
    combat_idx = out.find("**Combat**")
    skills_idx = out.find("**Skills**")
    assert combat_idx >= 0 and skills_idx >= 0
    assert combat_idx < skills_idx


def test_build_round_other_category_appears_last(agg):
    """Unknown awards → "Other" placed AFTER all known categories."""
    awards = [
        {"name": "Most damage given", "player": "p1",
         "numeric": 100, "value": ""},
        {"name": "Brand new mystery award", "player": "p2",
         "numeric": 1, "value": ""},
    ]
    out = agg.build_round_awards_display(awards)
    combat_idx = out.find("**Combat**")
    other_idx = out.find("**Other**")
    assert combat_idx >= 0 and other_idx >= 0
    assert combat_idx < other_idx


def test_build_round_respects_max_per_category(agg):
    """max_per_category=1 → only one award per category shown.
    Critical for keeping the embed under Discord's 1024 field limit."""
    awards = [
        {"name": "Most damage given", "player": "p1",
         "numeric": 100, "value": ""},
        {"name": "Most kills per minute", "player": "p2",
         "numeric": 200, "value": ""},
    ]
    out = agg.build_round_awards_display(awards, max_per_category=1)
    # Both are 'combat' — only one should render
    assert "p1" in out or "p2" in out
    assert not ("p1" in out and "p2" in out)


def test_build_round_respects_max_total_appends_ellipsis(agg):
    """When total lines hit max_total mid-render, append "…and more"."""
    awards = [
        {"name": "Most damage given", "player": f"p{i}",
         "numeric": 100, "value": ""}
        for i in range(20)
    ]
    out = agg.build_round_awards_display(awards, max_total=3)
    assert "…and more" in out


def test_build_round_unknown_numeric_uses_value_field(agg):
    """numeric=None → fall back to the raw `value` string."""
    awards = [{
        "name": "Most damage given", "player": "alice",
        "numeric": None, "value": "RAW",
    }]
    out = agg.build_round_awards_display(awards)
    assert "RAW" in out


def test_build_round_handles_missing_keys(agg):
    """Awards with missing 'name' / 'player' fall back to "Unknown"."""
    awards = [{"numeric": 1.0, "value": ""}]
    out = agg.build_round_awards_display(awards)
    assert "Unknown" in out


# ---------------------------------------------------------------------------
# build_awards_display — session-level compact rendering
# ---------------------------------------------------------------------------


def test_build_session_returns_empty_string_for_no_awards(agg):
    out = agg.build_awards_display({})
    assert out == ""


def test_build_session_renders_top_player_per_award(agg):
    """top_awards picks first player (already sorted by value DESC)."""
    awards_by_category = {
        "combat": {
            "Most damage given": [("g1", "alice", 5000.0, 3)],
        },
    }
    out = agg.build_awards_display(awards_by_category)
    assert "alice" in out
    assert "5.0K" in out
    assert "3x" in out  # win_count


def test_build_session_skips_unknown_categories(agg):
    """Categories not in CATEGORY_DISPLAY are skipped (NOT pushed to
    "Other" — different from build_round_awards_display, which adds an
    'other' bucket. Pin the divergence)."""
    awards_by_category = {
        "totally-fake-category": {
            "Mystery award": [("g1", "alice", 1.0, 1)],
        },
    }
    out = agg.build_awards_display(awards_by_category)
    assert out == ""  # skipped → empty


def test_build_session_respects_max_categories(agg):
    """max_categories=1 → only one category renders."""
    awards_by_category = {
        "combat": {"Most damage given": [("g1", "p1", 100.0, 1)]},
        "skills": {"Most headshots": [("g2", "p2", 50.0, 1)]},
    }
    out = agg.build_awards_display(awards_by_category, max_categories=1)
    assert "**Combat:**" in out
    assert "**Skills:**" not in out


def test_build_session_uses_category_display_priority(agg):
    """Iteration order is sorted by CATEGORY_DISPLAY priority — pin
    so a regression that switches to insertion order doesn't change
    the rendered embed."""
    awards_by_category = {
        # Insertion order: skills (priority 2) BEFORE combat (priority 1)
        "skills": {"Most headshots": [("g2", "p2", 50.0, 1)]},
        "combat": {"Most damage given": [("g1", "p1", 100.0, 1)]},
    }
    out = agg.build_awards_display(awards_by_category)
    combat_idx = out.find("**Combat:**")
    skills_idx = out.find("**Skills:**")
    assert combat_idx >= 0 and skills_idx >= 0
    assert combat_idx < skills_idx


# ---------------------------------------------------------------------------
# build_vs_stats_display — VS table renderer
# ---------------------------------------------------------------------------


def test_build_vs_stats_with_data_returns_string(agg):
    """Implementation detail: just verify it doesn't crash on real input
    and returns a string."""
    vs = [("g1", "alice", 30, 12), ("g2", "bob", 25, 18)]
    out = agg.build_vs_stats_display(vs)
    assert isinstance(out, str)
