"""Tests for EndStatsParser pure helpers + AWARD_CATEGORIES integrity.

The endstats parser ingests "endstats" files for the !last_session
awards section. A regression silently:

- Drops every award (parse_filename returns None for valid files).
- Mis-extracts numeric value (downstream sort/aggregate breaks).
- Mis-categorises awards (Top players show in wrong section).
- AWARD_CATEGORIES has duplicate or missing entries (a referenced
  award name disappears from the embed).

Pin the contract for parse_filename, parse_value, categorize_awards,
validate_endstats_filename, and AWARD_CATEGORIES integrity.
"""
from __future__ import annotations

import pytest

from bot.endstats_parser import (
    AWARD_CATEGORIES,
    EndStatsParser,
    validate_endstats_filename,
)


@pytest.fixture
def parser():
    return EndStatsParser()


# ---------------------------------------------------------------------------
# parse_filename
# ---------------------------------------------------------------------------


def test_parse_filename_extracts_components(parser):
    out = parser.parse_filename(
        "2026-01-12-224606-te_escape2-round-2-endstats.txt"
    )
    assert out is not None
    assert out["date"] == "2026-01-12"
    assert out["time"] == "224606"
    assert out["map_name"] == "te_escape2"
    assert out["round_number"] == 2
    assert out["match_id"] == "2026-01-12-224606-te_escape2"
    assert out["filename"] == "2026-01-12-224606-te_escape2-round-2-endstats.txt"


def test_parse_filename_strips_directory(parser):
    """Path with directory → only basename used. Pin so callers can
    pass a full SSH-downloaded path without crashing."""
    out = parser.parse_filename(
        "/var/data/uploads/2026-04-21-100000-supply-round-1-endstats.txt"
    )
    assert out is not None
    assert out["map_name"] == "supply"


def test_parse_filename_returns_none_for_non_matching_file(parser):
    """File without -endstats suffix → None."""
    assert parser.parse_filename("2026-04-21-100000-supply-round-1.txt") is None


def test_parse_filename_returns_none_for_garbage(parser):
    assert parser.parse_filename("garbage.txt") is None
    assert parser.parse_filename("") is None


def test_parse_filename_handles_round_10(parser):
    """Round number is captured by `(\\d+)` — pin so 10+ rounds parse."""
    out = parser.parse_filename(
        "2026-01-12-100000-supply-round-10-endstats.txt"
    )
    assert out is not None
    assert out["round_number"] == 10


def test_parse_filename_match_id_format(parser):
    """match_id format: `YYYY-MM-DD-HHMMSS-mapname` (no round) — must
    match main-stats match_id format so they can be joined."""
    out = parser.parse_filename(
        "2026-01-12-100000-mp_oasis-round-1-endstats.txt"
    )
    assert out["match_id"] == "2026-01-12-100000-mp_oasis"


# ---------------------------------------------------------------------------
# parse_value
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw, expected_numeric", [
    ("3214",                3214.0),
    ("1.78",                1.78),
    ("113 seconds",         113.0),
    ("50.47 percent",       50.47),
    ("100",                 100.0),
    ("0",                   0.0),
])
def test_parse_value_extracts_numeric(parser, raw, expected_numeric):
    """Award value strings carry an optional unit suffix. Pin the
    extraction — a regression that drops the unit-strip would fail
    on every "X seconds" or "X percent" award."""
    raw_out, num_out = parser.parse_value(raw)
    assert raw_out == raw  # original preserved
    assert num_out == expected_numeric


def test_parse_value_strips_whitespace(parser):
    """Leading/trailing whitespace is stripped before parsing."""
    raw_out, num_out = parser.parse_value("  42  ")
    assert raw_out == "42"  # stripped
    assert num_out == 42.0


def test_parse_value_handles_kills_in_seconds_format(parser):
    """Special: `5 kills in 12.34s` → numeric=5 (kills count, not time).
    Pin so a regression that picks up 12.34 instead of 5 doesn't
    silently mis-rank the killing-spree award."""
    raw_out, num_out = parser.parse_value("5 kills in 12.34s")
    # The first numeric regex matches "5" → numeric=5.0
    assert num_out == 5.0


def test_parse_value_returns_none_for_non_numeric(parser):
    """No numeric part → numeric is None (NOT raise)."""
    raw_out, num_out = parser.parse_value("nobody")
    assert raw_out == "nobody"
    assert num_out is None


def test_parse_value_handles_empty_string(parser):
    raw_out, num_out = parser.parse_value("")
    assert raw_out == ""
    assert num_out is None


# ---------------------------------------------------------------------------
# categorize_awards
# ---------------------------------------------------------------------------


def test_categorize_awards_sorts_by_AWARD_CATEGORIES(parser):
    """Awards are bucketed under their category, identified by exact
    name match against AWARD_CATEGORIES."""
    awards = [
        {"name": "Most damage given", "player": "alice", "value": "3000", "numeric": 3000},
        {"name": "Most kills per minute", "player": "bob", "value": "30", "numeric": 30},
    ]
    out = parser.categorize_awards(awards)
    assert "combat" in out
    assert len(out["combat"]) == 2


def test_categorize_awards_unknown_goes_to_other(parser):
    """Unknown award name → 'other' bucket. Pin so a renamed award
    doesn't silently vanish from the embed."""
    awards = [
        {"name": "Mystery Award", "player": "alice", "value": "1", "numeric": 1},
    ]
    out = parser.categorize_awards(awards)
    assert "other" in out
    assert len(out["other"]) == 1


def test_categorize_awards_drops_empty_categories(parser):
    """Categories with zero awards are removed from the output dict.
    Pin so the embed renderer doesn't iterate over empty 'Skills' etc."""
    awards = [
        {"name": "Most damage given", "player": "alice", "value": "1", "numeric": 1},
    ]
    out = parser.categorize_awards(awards)
    assert "skills" not in out
    assert "deaths" not in out
    assert list(out.keys()) == ["combat"]


def test_categorize_awards_returns_empty_dict_for_empty_list(parser):
    out = parser.categorize_awards([])
    assert out == {}


def test_categorize_awards_preserves_award_dict(parser):
    """Award dict is moved through unchanged (caller may rely on
    fields like 'numeric', 'value')."""
    award = {"name": "Most damage given", "player": "p", "value": "1", "numeric": 1}
    out = parser.categorize_awards([award])
    assert out["combat"][0] is award


# ---------------------------------------------------------------------------
# validate_endstats_filename (module-level)
# ---------------------------------------------------------------------------


def test_validate_endstats_accepts_canonical():
    assert validate_endstats_filename(
        "2026-01-12-224606-te_escape2-round-2-endstats.txt"
    ) is True


def test_validate_endstats_strips_directory():
    """Validation works on basename, so a full path validates."""
    assert validate_endstats_filename(
        "/tmp/2026-01-12-100000-supply-round-1-endstats.txt"
    ) is True


@pytest.mark.parametrize("bad", [
    "stats.txt",
    "2026-01-12-100000-supply-round-1.txt",  # not -endstats
    "2026-01-12-100000-supply-round-1-endstats.log",  # wrong ext
    "2026-1-12-100000-supply-round-1-endstats.txt",  # 1-digit month
    "garbage",
    "",
])
def test_validate_endstats_rejects_garbage(bad):
    assert validate_endstats_filename(bad) is False


# ---------------------------------------------------------------------------
# AWARD_CATEGORIES integrity — pin the canonical list
# ---------------------------------------------------------------------------


def test_award_categories_has_known_categories():
    """Pin the SHAPE of AWARD_CATEGORIES — keys are category names that
    downstream code (CATEGORY_DISPLAY in endstats_aggregator) maps to
    display labels. A renamed key would silently drop the section."""
    expected_keys = {"combat", "deaths", "skills", "weapons", "timing", "teamwork", "objectives"}
    assert expected_keys.issubset(set(AWARD_CATEGORIES.keys()))


def test_award_categories_values_are_lists():
    """Every category value is a list of award-name strings."""
    for cat, awards in AWARD_CATEGORIES.items():
        assert isinstance(awards, list), f"{cat} not a list"
        assert all(isinstance(a, str) for a in awards), f"{cat} non-string entries"


def test_award_categories_has_no_duplicates_within_category():
    """Same award name twice in same category is suspicious."""
    for cat, awards in AWARD_CATEGORIES.items():
        assert len(awards) == len(set(awards)), f"duplicates in {cat}"


def test_award_categories_no_award_in_two_categories():
    """An award name should appear in EXACTLY ONE category. Pin so
    a copy-paste bug placing 'Most damage given' in both 'combat' and
    'objectives' would be caught (categorize_awards picks the first
    match — silent mis-attribution)."""
    seen: dict[str, str] = {}
    for cat, awards in AWARD_CATEGORIES.items():
        for award in awards:
            assert award not in seen, f"{award} in {seen[award]} AND {cat}"
            seen[award] = cat


def test_award_categories_combat_includes_known_awards():
    """Spot-check a few canonical awards stay in the right bucket."""
    assert "Most damage given" in AWARD_CATEGORIES["combat"]
    assert "Best K/D ratio" in AWARD_CATEGORIES["combat"]


def test_award_categories_deaths_includes_known_awards():
    assert "Most deaths" in AWARD_CATEGORIES["deaths"]
    assert "Most teamkills" in AWARD_CATEGORIES["deaths"]


def test_award_categories_skills_includes_headshot_awards():
    """Headshot awards live under skills, not combat. Pin the choice
    so a refactor that "promotes" headshots to combat is loud."""
    assert "Most headshot kills" in AWARD_CATEGORIES["skills"]
