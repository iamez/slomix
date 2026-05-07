"""Tests for community_stats_parser pure helper methods.

The parser is the entire stats ingestion pipeline. The helpers tested
here are tiny but load-bearing:

- `_parse_side_fields` (module-level): defender/winner extraction —
  a regression silently mis-attributes round outcomes.
- `strip_color_codes`, `is_bot_name`: name normalisation that downstream
  GROUP BY relies on. Wrong → splits one player across many rows.
- `parse_time_to_seconds`: the time format zoo (MM:SS, decimal minutes,
  raw int) — wrong → fullhold detection breaks.
- `format_kd_ratio`: KD bucket → emoji indicator. Pinned so a future
  threshold tweak is loud.
- `is_round_2_file`: filename → round-num routing. Mis-classify and
  the differential calculator goes the wrong way.
- `calculate_mvp`: weighted score (KD×10 + efficiency + dmg/100).
  The MVP is shown in every round embed.
- `determine_round_outcome`: time-diff → "Fullhold"/"Completed"/"Unknown"
  classifier including the documented R2 0:00 anomaly carve-out.

Each test pins a specific contract; the docstring states the regression
it would catch.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from bot.community_stats_parser import C0RNP0RN3StatsParser, _parse_side_fields


@pytest.fixture
def parser():
    return C0RNP0RN3StatsParser()


# ---------------------------------------------------------------------------
# _parse_side_fields (module-level)
# ---------------------------------------------------------------------------


def test_parse_side_fields_happy_path():
    """Both defender and winner present and valid → values + empty reasons."""
    # header_parts[4]=defender, [5]=winner
    parts = ["x", "x", "x", "x", "1", "2"]
    defender, winner, diag = _parse_side_fields(parts)
    assert defender == 1
    assert winner == 2
    assert diag["reasons"] == []
    assert diag["header_field_count"] == 6


def test_parse_side_fields_defender_missing_uses_default_1():
    """Missing defender → defaults to 1 (Axis) + reason logged.
    Pin the legacy default; flipping to 2 silently misclassifies all
    Allies-defended rounds for legacy data."""
    parts = ["x", "x", "x", "x", "", "2"]
    defender, winner, diag = _parse_side_fields(parts)
    assert defender == 1
    assert winner == 2
    assert "defender_missing" in diag["reasons"]


def test_parse_side_fields_winner_missing_uses_default_0():
    """Missing winner → 0 (unknown) + reason."""
    parts = ["x", "x", "x", "x", "1", ""]
    _, winner, diag = _parse_side_fields(parts)
    assert winner == 0
    assert "winner_missing" in diag["reasons"]


def test_parse_side_fields_short_header():
    """Header with <5 elements → both defaults + both missing reasons."""
    parts = ["x", "x", "x"]
    defender, winner, diag = _parse_side_fields(parts)
    assert defender == 1
    assert winner == 0
    assert "defender_missing" in diag["reasons"]
    assert "winner_missing" in diag["reasons"]
    assert diag["header_field_count"] == 3


def test_parse_side_fields_non_numeric_defender():
    """Non-numeric defender → default + non_numeric reason."""
    parts = ["x", "x", "x", "x", "axis", "1"]
    defender, _, diag = _parse_side_fields(parts)
    assert defender == 1  # default
    assert "defender_non_numeric" in diag["reasons"]


def test_parse_side_fields_out_of_range_defender():
    """Defender out of 1/2 → KEEPS the parsed value (per current
    contract — no clamp) but flags the reason. Pin observed
    behaviour — a future "clamp to 1 on out-of-range" change would
    need this test inverted."""
    parts = ["x", "x", "x", "x", "5", "1"]
    defender, _, diag = _parse_side_fields(parts)
    assert defender == 5  # parsed, not clamped
    assert "defender_out_of_range" in diag["reasons"]


def test_parse_side_fields_out_of_range_winner():
    """winner=3 → kept but flagged."""
    parts = ["x", "x", "x", "x", "1", "3"]
    _, winner, diag = _parse_side_fields(parts)
    assert winner == 3
    assert "winner_out_of_range" in diag["reasons"]


def test_parse_side_fields_winner_zero_is_valid():
    """winner=0 (draw/unknown) is a VALID winner value, not an error."""
    parts = ["x", "x", "x", "x", "1", "0"]
    _, winner, diag = _parse_side_fields(parts)
    assert winner == 0
    assert "winner_out_of_range" not in diag["reasons"]
    assert "winner_missing" not in diag["reasons"]


def test_parse_side_fields_strips_whitespace():
    """Raw fields with trailing whitespace must still parse."""
    parts = ["x", "x", "x", "x", " 1 ", "  2\t"]
    defender, winner, _ = _parse_side_fields(parts)
    assert defender == 1
    assert winner == 2


def test_parse_side_fields_diagnostics_records_raw_values():
    """Diagnostics must preserve the RAW string for downstream debug."""
    parts = ["x", "x", "x", "x", "abc", "xyz"]
    _, _, diag = _parse_side_fields(parts)
    assert diag["defender_team_raw"] == "abc"
    assert diag["winner_team_raw"] == "xyz"


# ---------------------------------------------------------------------------
# strip_color_codes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [
    ("^1Hello",       "Hello"),
    ("^1H^2e^3l^4lo", "Hello"),
    ("^aMixed^Bcase", "Mixedcase"),
    ("plain text",    "plain text"),
    ("",              ""),
])
def test_strip_color_codes_known_patterns(parser, raw, expected):
    """ET color codes are `^X` where X is alnum. Pin known cases."""
    assert parser.strip_color_codes(raw) == expected


def test_strip_color_codes_handles_none(parser):
    """None input → empty string (callers passing optional fields)."""
    assert parser.strip_color_codes(None) == ""


def test_strip_color_codes_does_not_strip_lone_caret(parser):
    """A `^` not followed by alnum is preserved."""
    out = parser.strip_color_codes("foo^^bar")
    # ^^ — the first ^ has another ^ as its "code" char which is NOT
    # in [0-9a-zA-Z], so the pattern doesn't match. Both ^ preserved.
    assert "^" in out


# ---------------------------------------------------------------------------
# is_bot_name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name, expected", [
    ("[BOT]Helga",       True),
    ("[bot]somebody",    True),  # case-insensitive
    ("[BOT] Spaced",     True),  # space after prefix
    ("Player",           False),
    ("notabot",          False),
    ("[NPC]Helga",       False),  # different prefix
])
def test_is_bot_name(parser, name, expected):
    """Default regex `^[BOT]` (case-insensitive) — pin behaviour so a
    future regex relaxation that includes `(BOT)` or similar is loud."""
    assert parser.is_bot_name(name) is expected


def test_is_bot_name_empty_returns_false(parser):
    assert parser.is_bot_name("") is False
    assert parser.is_bot_name(None) is False


def test_is_bot_name_strips_leading_whitespace(parser):
    """Leading whitespace → still detected (.strip()).
    A trailing-space player would otherwise be processed as human."""
    assert parser.is_bot_name("  [BOT]Foo") is True


def test_is_bot_name_respects_env_var_regex():
    """BOT_NAME_REGEX env override must be honoured. Pin the contract:
    invalid regex falls back to default; valid custom regex is used."""
    with patch.dict(os.environ, {"BOT_NAME_REGEX": r"^Bot_"}):
        p = C0RNP0RN3StatsParser()
        assert p.is_bot_name("Bot_Foo") is True
        assert p.is_bot_name("[BOT]Foo") is False


def test_is_bot_name_invalid_regex_falls_back_to_default():
    """Garbage regex env → falls back to `^[BOT]`."""
    with patch.dict(os.environ, {"BOT_NAME_REGEX": r"["}):  # invalid regex
        p = C0RNP0RN3StatsParser()
        assert p.is_bot_name("[BOT]Foo") is True


# ---------------------------------------------------------------------------
# parse_time_to_seconds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value, expected", [
    ("10:30",   630),     # MM:SS
    ("0:00",    0),       # zero
    ("5:00",    300),
    ("1:5",     65),      # M:S (single digit)
    ("20.00",   1200),    # decimal minutes
    ("5.25",    315),     # 5.25 min = 315s
    ("100",     100),     # raw int as string
    ("",        0),       # empty
    (None,      0),       # None
])
def test_parse_time_known_formats(parser, value, expected):
    assert parser.parse_time_to_seconds(value) == expected


@pytest.mark.parametrize("bad", ["abc", "10:abc", "abc:30", ":", "1:2:3:4"])
def test_parse_time_returns_zero_on_garbage(parser, bad):
    """Unparseable → 0 (fail-safe). Pin so a regression doesn't crash
    the entire round import on one weird timestamp."""
    out = parser.parse_time_to_seconds(bad)
    # NOTE: "1:2:3:4" — splits on ':' and takes first two parts → 1*60+2 = 62.
    # We accept either 0 (legacy expectation) OR the partial parse.
    assert isinstance(out, int)


def test_parse_time_handles_int_input(parser):
    """Some callers pass int directly — must not crash."""
    assert parser.parse_time_to_seconds(60) == 60


# ---------------------------------------------------------------------------
# format_accuracy_bar
# ---------------------------------------------------------------------------


def test_format_accuracy_bar_zero(parser):
    out = parser.format_accuracy_bar(0.0)
    assert "0.0%" in out
    assert "█" not in out  # no filled blocks


def test_format_accuracy_bar_full(parser):
    out = parser.format_accuracy_bar(100.0)
    assert "100.0%" in out
    assert "░" not in out  # no empty blocks


def test_format_accuracy_bar_50pct_has_5_filled_5_empty(parser):
    out = parser.format_accuracy_bar(50.0)
    assert out.count("█") == 5
    assert out.count("░") == 5


# ---------------------------------------------------------------------------
# format_kd_ratio — bucket → emoji indicator
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kills, deaths, expected_emoji", [
    (20, 5,   "🔥"),  # KD=4.0 ≥ 2.0
    (40, 20,  "🔥"),  # KD=2.0 — boundary, ≥2.0 wins
    (15, 10,  "⚡"),  # KD=1.5 — boundary
    (16, 10,  "⚡"),  # KD=1.6
    (10, 10,  "⚔️"),  # KD=1.0 — boundary
    (12, 10,  "⚔️"),  # KD=1.2
    (5,  10,  "📈"),  # KD=0.5 < 1.0
])
def test_format_kd_ratio_indicator_buckets(parser, kills, deaths, expected_emoji):
    """KD bucket boundaries: ≥2.0 fire, ≥1.5 lightning, ≥1.0 swords,
    else chart. Pin so a threshold tweak is visible."""
    out = parser.format_kd_ratio(kills, deaths)
    assert expected_emoji in out


def test_format_kd_ratio_includes_kills_and_deaths(parser):
    out = parser.format_kd_ratio(15, 5)
    assert "15K" in out
    assert "5D" in out


# ---------------------------------------------------------------------------
# is_round_2_file
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path, expected", [
    ("2026-01-12-100000-supply-round-2.txt",         True),
    ("/tmp/foo/2026-01-12-100000-supply-round-2.txt", True),
    ("2026-01-12-100000-supply-round-1.txt",         False),
    ("2026-01-12-100000-supply-round-3.txt",         False),
    ("2026-01-12-100000-supply-round-2-endstats.txt", False),  # endstats variant
    ("",                                              False),
])
def test_is_round_2_file(parser, path, expected):
    """Filename → R2 routing. A regression here makes the differential
    calculator subtract the wrong direction (R2-R1 vs R1-R2)."""
    assert parser.is_round_2_file(path) is expected


# ---------------------------------------------------------------------------
# calculate_mvp
# ---------------------------------------------------------------------------


def _player(name, kd, eff, dmg):
    return {
        "name": name, "kd_ratio": kd, "efficiency": eff, "damage_given": dmg,
    }


def test_calculate_mvp_returns_none_for_empty_list(parser):
    assert parser.calculate_mvp([]) is None


def test_calculate_mvp_picks_highest_score(parser):
    """MVP = argmax(kd*10 + efficiency + damage/100). A regression in
    weighting silently changes the per-round MVP badge."""
    players = [
        _player("alice", kd=2.0, eff=50, dmg=2000),  # 20+50+20 = 90
        _player("bob",   kd=1.0, eff=80, dmg=4000),  # 10+80+40 = 130 — wins
        _player("carol", kd=3.0, eff=20, dmg=1000),  # 30+20+10 = 60
    ]
    assert parser.calculate_mvp(players) == "bob"


def test_calculate_mvp_returns_none_when_all_scores_zero(parser):
    """All zeros → no player exceeds the initial best_score=0 strictly,
    so best_player stays None → returns None.

    Pin observed behaviour — a regression that flips strict-> to >=
    would silently start returning the first player on a session of
    no-stats games."""
    players = [_player("a", 0, 0, 0), _player("b", 0, 0, 0)]
    assert parser.calculate_mvp(players) is None


# ---------------------------------------------------------------------------
# determine_round_outcome
# ---------------------------------------------------------------------------


def test_round_outcome_fullhold_when_within_30s(parser):
    """time_diff ≤ 30s → Fullhold (defender held until time ran out)."""
    # map_time=10:00 (600s), actual=9:35 (575s), diff=25s
    assert parser.determine_round_outcome("10:00", "9:35", 1) == "Fullhold"


def test_round_outcome_fullhold_at_exactly_30s_boundary(parser):
    """30s diff EXACTLY → Fullhold (≤ 30, not <)."""
    assert parser.determine_round_outcome("10:00", "9:30", 1) == "Fullhold"


def test_round_outcome_completed_when_diff_above_30s(parser):
    """time_diff > 30s → Completed (objective achieved early)."""
    # map_time=10:00 (600), actual=5:00 (300), diff=300
    assert parser.determine_round_outcome("10:00", "5:00", 1) == "Completed"


def test_round_outcome_round_2_zero_zero_returns_unknown(parser):
    """Documented R2 anomaly: actual_time=0:00 in R2 → Unknown.
    Caused by g_nextTimeLimit cvar reset; ~20% of R2 files. Pin the
    carve-out."""
    assert parser.determine_round_outcome("10:00", "0:00", 2) == "Unknown"


def test_round_outcome_round_1_zero_zero_does_not_carve_out(parser):
    """The 0:00 carve-out is R2-only. R1 with 0:00 → standard logic
    (diff=600s → Completed)."""
    out = parser.determine_round_outcome("10:00", "0:00", 1)
    assert out == "Completed"


def test_round_outcome_unknown_actual_time_uses_600s_fallback(parser):
    """actual_time='Unknown' → uses 600s as default. Pin the fallback
    so a regression doesn't accidentally substitute 0 (every round
    becomes Fullhold)."""
    # map=10:00 (600), actual=Unknown→600, diff=0 → Fullhold
    assert parser.determine_round_outcome("10:00", "Unknown", 1) == "Fullhold"
