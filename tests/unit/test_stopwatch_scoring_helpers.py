"""Tests for StopwatchScoringService pure helpers.

These compute the map-winner scoring used everywhere in the bot
(`!last_session`, session detail page, matchup analytics). A regression
silently:

- `normalize_side` drops a legitimate variant (e.g., upper-case "AXIS"
  unhandled) → that round's side gets None → roster splits wrong →
  team_a/team_b columns swap on display.
- `normalize_side` accepts a non-canonical value as 1 → maps a
  "spectator" row into team1 → leaderboard pollution.
- `parse_time_to_seconds` returns 0 for legitimate input → map looks
  unfinished → scoring treats both teams as fullholds → 1-1 tie.
- `parse_time_to_seconds` decimal minutes (1.5 → 90s) regression →
  off by 60x.
- `calculate_map_score` tie tie-break flips → Team1 advantage on
  identical times silently goes to Team2.
- `calculate_map_score` fullhold-on-both → must be a 1-1 draw (BOX
  scale, owner rule 2026-07-05), NOT a 2-0 award-by-default → pin the
  symmetric defence case. Wins are 2-0; every map is worth 2 points.
- `calculate_map_score` no-limit-known fallback (limit_sec<=0) treats
  ANY positive time as completion — pin so a header-missing R0 file
  doesn't silently award double points.

Pin every branch.
"""
from __future__ import annotations

import pytest

from bot.services.stopwatch_scoring_service import (
    StopwatchScoringService,
    normalize_side,
)

# ---------------------------------------------------------------------------
# normalize_side — legacy data variant handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("input_value", [1, "1", "Axis", "axis"])
def test_normalize_side_axis_variants_to_one(input_value):
    """Pin the canonical mapping: int 1, str "1", "Axis", "axis" → 1.
    Pin so a refactor that drops a variant silently makes that row
    look like spectator (None)."""
    assert normalize_side(input_value) == 1


@pytest.mark.parametrize("input_value", [2, "2", "Allies", "allies"])
def test_normalize_side_allies_variants_to_two(input_value):
    """Mirror of axis. Pin every Allies variant."""
    assert normalize_side(input_value) == 2


def test_normalize_side_unknown_returns_none():
    """Spectator/unknown sides → None (NOT default to 1 or 2). Pin
    so pre-game spectator rows don't pollute team rosters."""
    assert normalize_side("spectator") is None
    assert normalize_side(0) is None
    assert normalize_side(3) is None
    assert normalize_side("") is None


def test_normalize_side_none_input_returns_none():
    """Pin so a NULL DB row passes through cleanly."""
    assert normalize_side(None) is None


def test_normalize_side_uppercase_axis_not_accepted():
    """"AXIS" (all-caps) is NOT in the accepted set → None.

    Pin observed semantics: production rows store either the canonical
    casing ("Axis") or the lowercase variant. A future PR that adds
    upper-case acceptance would intentionally update this test."""
    assert normalize_side("AXIS") is None
    assert normalize_side("ALLIES") is None


def test_normalize_side_mixed_casing_partial_accepted():
    """Pin observed: only "Axis" and "axis" accepted, NOT "axIs"."""
    assert normalize_side("axIs") is None


# ---------------------------------------------------------------------------
# parse_time_to_seconds — MM:SS, M:SS, decimal-minutes, raw int
# ---------------------------------------------------------------------------


@pytest.fixture
def svc():
    """We just need a no-op db_adapter for the helper to bind to self."""
    return StopwatchScoringService(db_adapter=None)


@pytest.mark.parametrize("text, expected", [
    ("0:00",   0),
    ("1:00",   60),
    ("1:30",   90),
    ("10:30",  630),
    ("99:59",  99 * 60 + 59),
])
def test_parse_time_mm_ss(svc, text, expected):
    """Pin canonical MM:SS parsing."""
    assert svc.parse_time_to_seconds(text) == expected


def test_parse_time_decimal_minutes(svc):
    """Decimal-minute string `1.5` → 90s (×60). Pin so a refactor
    that drops the * 60 makes every map look 60x shorter."""
    assert svc.parse_time_to_seconds("1.5") == 90


def test_parse_time_raw_integer_seconds(svc):
    """No `:` and no `.` → integer seconds direct (NO * 60)."""
    assert svc.parse_time_to_seconds("60") == 60
    assert svc.parse_time_to_seconds("125") == 125


def test_parse_time_handles_whitespace(svc):
    """Leading/trailing whitespace stripped."""
    assert svc.parse_time_to_seconds("  10:30  ") == 630


def test_parse_time_empty_returns_zero(svc):
    """Empty/None → 0 (NOT raise). Pin defensive default for
    incomplete header rows."""
    assert svc.parse_time_to_seconds("") == 0
    assert svc.parse_time_to_seconds(None) == 0


def test_parse_time_garbage_returns_zero(svc):
    """Non-numeric → 0 (try/except guard). Pin so a parser glitch
    doesn't crash the scorer mid-calculation."""
    assert svc.parse_time_to_seconds("garbage") == 0
    assert svc.parse_time_to_seconds("abc:def") == 0


def test_parse_time_extra_colons_truncated_to_first_two_segments(svc):
    """`H:M:S` style → only minutes and seconds parsed (NO hour-of-day
    handling). Pin observed split-by-colon behaviour."""
    out = svc.parse_time_to_seconds("1:00:30")
    assert out == 60  # only first two parts: 1 minute + 0 seconds, drops :30


def test_parse_time_negative_or_zero_seconds(svc):
    """0:00 → 0; pin so a "fullhold" row reads as no-completion."""
    assert svc.parse_time_to_seconds("0:00") == 0


# ---------------------------------------------------------------------------
# calculate_map_score — map-winner table
# ---------------------------------------------------------------------------


def test_calc_both_complete_team1_faster_wins(svc):
    """Both finished; T1 faster → 1-0 to Team1."""
    t1, t2, desc = svc.calculate_map_score("10:00", "5:00", "7:00")
    assert (t1, t2) == (2, 0)
    assert "R1 attackers 5:00" in desc


def test_calc_both_complete_team2_faster_wins(svc):
    """T2 faster → 0-1 to Team2."""
    t1, t2, desc = svc.calculate_map_score("10:00", "8:00", "5:00")
    assert (t1, t2) == (0, 2)
    assert "R2 attackers 5:00" in desc


def test_calc_both_complete_tie_goes_to_team1(svc):
    """Tie tie-break → Team1 wins (the `<=` in production). Pin so
    a refactor that flips to `<` silently flips every tied map."""
    t1, t2, _ = svc.calculate_map_score("10:00", "5:00", "5:00")
    assert (t1, t2) == (2, 0)


def test_calc_team1_completes_team2_fullhold(svc):
    """T1 finishes; T2 doesn't (time >= limit) → 1-0 Team1."""
    t1, t2, desc = svc.calculate_map_score("10:00", "8:30", "10:00")
    assert (t1, t2) == (2, 0)
    assert "R2 fullhold" in desc


def test_calc_team2_completes_team1_fullhold(svc):
    """T2 finishes; T1 doesn't → 0-1 Team2."""
    t1, t2, desc = svc.calculate_map_score("10:00", "10:00", "8:30")
    assert (t1, t2) == (0, 2)
    assert "R1 fullhold" in desc


def test_calc_double_fullhold_is_tie(svc):
    """Both teams fail to complete → 0-0 (no-points tie). Pin the
    symmetric-defence case so it never silently awards a default."""
    t1, t2, desc = svc.calculate_map_score("10:00", "10:00", "10:00")
    assert (t1, t2) == (1, 1)
    assert "no completion" in desc.lower()


def test_calc_no_actual_times_is_tie(svc):
    """Both R1 and R2 have empty actual_time → 0-0."""
    t1, t2, _ = svc.calculate_map_score("10:00", "", "")
    assert (t1, t2) == (1, 1)


def test_calc_no_time_limit_uses_positive_time_as_completion(svc):
    """If limit_sec <= 0 (header missing) → ANY positive time counts as
    completion. Pin observed fallback so a header-missing R0 doesn't
    silently look like a fullhold."""
    t1, t2, _ = svc.calculate_map_score("", "5:00", "8:00")
    # Both have positive time → both completed → faster (T1) wins
    assert (t1, t2) == (2, 0)


def test_calc_no_time_limit_one_side_zero_treated_as_fullhold(svc):
    """No limit + T2 has 0 time → T1 wins (T2 didn't complete)."""
    t1, t2, _ = svc.calculate_map_score("", "5:00", "0:00")
    assert (t1, t2) == (2, 0)


def test_calc_at_exact_limit_is_fullhold(svc):
    """actual_time == limit → NOT completion (strict `<`).
    Pin so a clock-exactly-zero edge doesn't flip a fullhold into
    a time win."""
    t1, t2, _ = svc.calculate_map_score("10:00", "10:00", "")
    # T1 == limit → fullhold; T2 empty → fullhold → 0-0
    assert (t1, t2) == (1, 1)


def test_calc_returns_three_tuple_with_string_description(svc):
    """Public contract: (int, int, str). Pin so frontend can rely on
    desc being non-empty for every outcome."""
    t1, t2, desc = svc.calculate_map_score("10:00", "5:00", "8:00")
    assert isinstance(t1, int)
    assert isinstance(t2, int)
    assert isinstance(desc, str)
    assert len(desc) > 0


def test_calc_negative_limit_treated_as_no_limit(svc):
    """Negative limit (impossible but defend) → uses positive-time
    fallback path."""
    t1, t2, _ = svc.calculate_map_score("-5:00", "3:00", "0:00")
    # limit parses to negative → fallback path → T1 wins
    assert (t1, t2) == (2, 0)
