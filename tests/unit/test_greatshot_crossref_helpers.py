"""Tests for greatshot_crossref pure helpers + DB-light validators.

The existing test_greatshot_crossref.py covers high-level matching
flows but the building-block helpers (_normalize_winner,
_extract_date_from_filename, _calculate_player_overlap,
_validate_stats_match thresholds) had thin coverage.

These helpers feed the cross-reference confidence score that decides
whether a demo upload links to a DB round. A regression in the
threshold ladder silently mis-attributes demos to the wrong rounds.
"""
from __future__ import annotations

import pytest

from website.backend.services.greatshot_crossref import (
    _calculate_player_overlap,
    _extract_date_from_filename,
    _normalize_winner,
    _validate_stats_match,
)

# ---------------------------------------------------------------------------
# _normalize_winner
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [
    ("allies",   "allies"),
    ("ALLIES",   "allies"),
    ("Allies",   "allies"),
    ("axis",     "axis"),
    ("AXIS",     "axis"),
    ("2",        "allies"),
    ("1",        "axis"),
    ("0",        "draw"),
    ("draw",     "draw"),
    ("DRAW",     "draw"),
    ("none",     "draw"),
    ("None",     "draw"),
])
def test_normalize_winner_known_values(raw, expected):
    assert _normalize_winner(raw) == expected


def test_normalize_winner_strips_whitespace():
    """Demo upload metadata sometimes has trailing whitespace."""
    assert _normalize_winner("  allies  ") == "allies"
    assert _normalize_winner("\taxis\n") == "axis"


@pytest.mark.parametrize("bad", [None, "unknown", "team_red", "5", "", "garbage"])
def test_normalize_winner_returns_none_for_unknown(bad):
    """Unknown winner → None (caller handles missing winner gracefully)."""
    assert _normalize_winner(bad) is None


def test_normalize_winner_handles_int_input():
    """asyncpg may return integer team values."""
    assert _normalize_winner(1) == "axis"
    assert _normalize_winner(2) == "allies"
    assert _normalize_winner(0) == "draw"


# ---------------------------------------------------------------------------
# _extract_date_from_filename
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filename, expected", [
    ("2026-02-08-capture.dm_84",            "2026-02-08"),
    ("2026-02-08_match.dm_84",              "2026-02-08"),
    ("demo-2025-12-31.dm_84",               "2025-12-31"),
    ("multi_2026-04-21_round_1.dm_84",      "2026-04-21"),
])
def test_extract_date_iso_format(filename, expected):
    assert _extract_date_from_filename(filename) == expected


@pytest.mark.parametrize("filename, expected", [
    ("demo_2026_02_08.dm_84",       "2026-02-08"),
    ("clip_2025_12_31.dm_84",       "2025-12-31"),
])
def test_extract_date_underscore_format_normalised_to_iso(filename, expected):
    """Underscore date format is converted to dash-separated ISO."""
    assert _extract_date_from_filename(filename) == expected


def test_extract_date_iso_format_takes_precedence_over_underscore():
    """A filename with both formats — ISO match wins because regex
    runs first."""
    out = _extract_date_from_filename("2026-02-08_run_2025_12_31.dm_84")
    assert out == "2026-02-08"


@pytest.mark.parametrize("filename", [
    "gameplay.dm_84",                 # no date
    "demo_run.dm_84",
    "",                                # empty
    None,                              # falsy
    "demo_99_99_99.dm_84",            # bad month/day (regex still matches!)
])
def test_extract_date_unknown_filenames(filename):
    """All these have no recognisable YYYY pattern → None.
    Note: 99/99/99 is a malformed date but the regex doesn't validate
    month/day ranges; that case is handled separately."""
    if filename == "demo_99_99_99.dm_84":
        # The regex ((\d{4})_(\d{2})_(\d{2})) matches "99_99_99" if
        # there's a 4-digit prefix. There isn't here, so it returns None.
        assert _extract_date_from_filename(filename) is None
    else:
        assert _extract_date_from_filename(filename) is None


def test_extract_date_does_not_validate_month_day():
    """Regex captures any YYYY-MM-DD shape — month=13 is accepted.
    Pin this contract so callers know they need to validate downstream."""
    out = _extract_date_from_filename("2026-13-45-broken.dm_84")
    assert out == "2026-13-45"


# ---------------------------------------------------------------------------
# _calculate_player_overlap (DB-bound but easy to fake)
# ---------------------------------------------------------------------------


class _FakeDb:
    def __init__(self, rows):
        self.rows = rows

    async def fetch_all(self, query, params=None):
        return self.rows


@pytest.mark.asyncio
async def test_player_overlap_returns_zero_for_empty_demo_list():
    db = _FakeDb([("player1",)])
    out = await _calculate_player_overlap([], round_id=1, db=db)
    assert out == 0.0


@pytest.mark.asyncio
async def test_player_overlap_returns_zero_when_db_round_has_no_players():
    db = _FakeDb([])
    out = await _calculate_player_overlap(["player1"], round_id=1, db=db)
    assert out == 0.0


@pytest.mark.asyncio
async def test_player_overlap_full_match_returns_one():
    db = _FakeDb([("alice",), ("bob",), ("carol",)])
    out = await _calculate_player_overlap(
        ["alice", "bob", "carol"], round_id=1, db=db,
    )
    assert out == 1.0


@pytest.mark.asyncio
async def test_player_overlap_partial():
    """2 of 3 demo players match → 0.667 overlap."""
    db = _FakeDb([("alice",), ("bob",)])
    out = await _calculate_player_overlap(
        ["alice", "bob", "stranger"], round_id=1, db=db,
    )
    assert out == pytest.approx(2/3, abs=1e-6)


@pytest.mark.asyncio
async def test_player_overlap_case_insensitive():
    """Demo "Alice" should match DB "alice" (lowered)."""
    db = _FakeDb([("alice",)])
    out = await _calculate_player_overlap(["ALICE"], round_id=1, db=db)
    assert out == 1.0


@pytest.mark.asyncio
async def test_player_overlap_strips_whitespace():
    db = _FakeDb([("alice",)])
    out = await _calculate_player_overlap(["  alice  "], round_id=1, db=db)
    assert out == 1.0


@pytest.mark.asyncio
async def test_player_overlap_skips_none_players():
    """A None entry in either list is silently dropped."""
    db = _FakeDb([("alice",), (None,), ("bob",)])
    out = await _calculate_player_overlap(
        ["alice", None, "bob"], round_id=1, db=db,
    )
    assert out == 1.0


# ---------------------------------------------------------------------------
# _validate_stats_match — confidence threshold ladder
# ---------------------------------------------------------------------------


class _StatsFakeDb:
    def __init__(self, total_kills=None):
        self.total_kills = total_kills

    async def fetch_one(self, query, params=None):
        if self.total_kills is None:
            return None
        return (self.total_kills, self.total_kills * 100)  # damage placeholder


@pytest.mark.asyncio
async def test_validate_stats_returns_zero_for_empty_demo():
    out = await _validate_stats_match({}, round_id=1, db=_StatsFakeDb())
    assert out == 0.0


@pytest.mark.asyncio
async def test_validate_stats_returns_zero_when_demo_has_no_kills():
    """Demo with players but 0 kills — sandbox/practice round → no signal."""
    out = await _validate_stats_match(
        {"p1": {"kills": 0}, "p2": {"kills": 0}},
        round_id=1, db=_StatsFakeDb(total_kills=20),
    )
    assert out == 0.0


@pytest.mark.asyncio
async def test_validate_stats_returns_zero_when_db_has_no_kills():
    """DB row has 0 kills → no usable stats → 0 confidence adjustment."""
    out = await _validate_stats_match(
        {"p1": {"kills": 10}},
        round_id=1, db=_StatsFakeDb(total_kills=0),
    )
    assert out == 0.0


@pytest.mark.asyncio
async def test_validate_stats_within_5pct_returns_15_bonus():
    """≤5% kill difference → +15 confidence (strong signal)."""
    # demo=98, db=100 → diff=2%, within 5%
    out = await _validate_stats_match(
        {"p1": {"kills": 98}},
        round_id=1, db=_StatsFakeDb(total_kills=100),
    )
    assert out == 15.0


@pytest.mark.asyncio
async def test_validate_stats_within_15pct_returns_5_bonus():
    """5% < diff ≤ 15% → +5 confidence."""
    # demo=85, db=100 → diff=15%, exactly at threshold (≤15%)
    out = await _validate_stats_match(
        {"p1": {"kills": 85}},
        round_id=1, db=_StatsFakeDb(total_kills=100),
    )
    assert out == 5.0


@pytest.mark.asyncio
async def test_validate_stats_above_50pct_returns_30_penalty():
    """≥50% kill difference → -30 confidence (probably wrong match)."""
    # demo=40, db=100 → diff=60% > 50%
    out = await _validate_stats_match(
        {"p1": {"kills": 40}},
        round_id=1, db=_StatsFakeDb(total_kills=100),
    )
    assert out == -30.0


@pytest.mark.asyncio
async def test_validate_stats_in_grey_zone_returns_zero():
    """15% < diff < 50% → 0 (neither boost nor penalty — ambiguous zone)."""
    # demo=70, db=100 → diff=30%
    out = await _validate_stats_match(
        {"p1": {"kills": 70}},
        round_id=1, db=_StatsFakeDb(total_kills=100),
    )
    assert out == 0.0


@pytest.mark.asyncio
async def test_validate_stats_aggregates_all_player_kills():
    """Multi-player demo: kills are summed across all players."""
    out = await _validate_stats_match(
        {"a": {"kills": 30}, "b": {"kills": 30}, "c": {"kills": 38}},
        round_id=1, db=_StatsFakeDb(total_kills=100),
    )
    # Total demo kills = 98, db = 100, diff = 2% → +15
    assert out == 15.0
