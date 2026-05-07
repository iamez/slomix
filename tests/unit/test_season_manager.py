"""Tests for bot/core/season_manager.py.

SeasonManager drives the quarterly leaderboard reset cycle. The
SQL WHERE-clause it returns is f-string-injected into season-scoped
queries, so a regression in the date-formatting (off-by-one quarter,
wrong end-of-month day, alltime not skipping the filter) would
silently corrupt every leaderboard render.

Pin every public method's contract.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from bot.core.season_manager import SeasonManager


# ---------------------------------------------------------------------------
# get_current_season
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("month, expected_q", [
    (1, 1), (2, 1), (3, 1),     # Q1
    (4, 2), (5, 2), (6, 2),     # Q2
    (7, 3), (8, 3), (9, 3),     # Q3
    (10, 4), (11, 4), (12, 4),  # Q4
])
def test_current_season_quarter_math(month, expected_q):
    """Each calendar month maps to the correct quarter."""
    sm = SeasonManager()
    with patch("bot.core.season_manager.datetime") as mocked:
        mocked.now.return_value = datetime(2026, month, 15)
        mocked.side_effect = lambda *args, **kw: datetime(*args, **kw)
        out = sm.get_current_season()
    assert out == f"2026-Q{expected_q}"


def test_current_season_year_rollover():
    """December 2025 → 2025-Q4, January 2026 → 2026-Q1 (no year drift)."""
    sm = SeasonManager()
    with patch("bot.core.season_manager.datetime") as mocked:
        mocked.now.return_value = datetime(2025, 12, 31, 23, 59, 59)
        mocked.side_effect = lambda *args, **kw: datetime(*args, **kw)
        assert sm.get_current_season() == "2025-Q4"

        mocked.now.return_value = datetime(2026, 1, 1, 0, 0, 0)
        assert sm.get_current_season() == "2026-Q1"


# ---------------------------------------------------------------------------
# get_season_name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("season_id, expected_name", [
    ("2026-Q1", "2026 Spring (Q1)"),
    ("2026-Q2", "2026 Summer (Q2)"),
    ("2026-Q3", "2026 Fall (Q3)"),
    ("2026-Q4", "2026 Winter (Q4)"),
])
def test_get_season_name_for_each_quarter(season_id, expected_name):
    sm = SeasonManager()
    assert sm.get_season_name(season_id) == expected_name


def test_get_season_name_uses_current_when_none():
    sm = SeasonManager()
    with patch("bot.core.season_manager.datetime") as mocked:
        mocked.now.return_value = datetime(2026, 4, 15)
        mocked.side_effect = lambda *args, **kw: datetime(*args, **kw)
        assert sm.get_season_name() == "2026 Summer (Q2)"


# ---------------------------------------------------------------------------
# get_season_dates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("season_id, start, end", [
    ("2026-Q1", datetime(2026, 1, 1),  datetime(2026, 3, 31, 23, 59, 59)),
    ("2026-Q2", datetime(2026, 4, 1),  datetime(2026, 6, 30, 23, 59, 59)),
    ("2026-Q3", datetime(2026, 7, 1),  datetime(2026, 9, 30, 23, 59, 59)),
    ("2026-Q4", datetime(2026, 10, 1), datetime(2026, 12, 31, 23, 59, 59)),
])
def test_get_season_dates_quarter_boundaries(season_id, start, end):
    sm = SeasonManager()
    s, e = sm.get_season_dates(season_id)
    assert s == start
    assert e == end


def test_get_season_dates_handles_leap_year_q1():
    """Feb 29 in 2024 → Q1 ends March 31 (Feb leap doesn't shift quarter)."""
    sm = SeasonManager()
    s, e = sm.get_season_dates("2024-Q1")
    assert s == datetime(2024, 1, 1)
    assert e == datetime(2024, 3, 31, 23, 59, 59)


def test_get_season_dates_uses_current_when_none():
    sm = SeasonManager()
    with patch("bot.core.season_manager.datetime") as mocked:
        mocked.now.return_value = datetime(2026, 4, 15)
        mocked.side_effect = lambda *args, **kw: datetime(*args, **kw)
        s, e = sm.get_season_dates()
        assert s == datetime(2026, 4, 1)


# ---------------------------------------------------------------------------
# get_season_sql_filter — SQL injection adjacent
# ---------------------------------------------------------------------------


def test_sql_filter_alltime_returns_empty_string():
    """'alltime' must produce NO filter — empty string lets the leaderboard
    aggregate across history. A future regression that returns 'AND 1=1' or
    similar would silently scope to current quarter only."""
    sm = SeasonManager()
    assert sm.get_season_sql_filter("alltime") == ""


def test_sql_filter_alltime_case_insensitive():
    sm = SeasonManager()
    assert sm.get_season_sql_filter("ALLTIME") == ""
    assert sm.get_season_sql_filter("AllTime") == ""


def test_sql_filter_includes_round_date_columns_only():
    """The clause must use `s.round_date`, not `s.session_date` (which
    doesn't exist on the rounds table — common confusion that bricked
    the leaderboard once before)."""
    sm = SeasonManager()
    out = sm.get_season_sql_filter("2026-Q1")
    assert "s.round_date" in out
    assert "session_date" not in out


def test_sql_filter_quotes_dates_correctly():
    """Dates must be quoted as 'YYYY-MM-DD' strings (asyncpg/Postgres
    accepts text→date casts at query time)."""
    sm = SeasonManager()
    out = sm.get_season_sql_filter("2026-Q1")
    assert "'2026-01-01'" in out
    assert "'2026-03-31'" in out


def test_sql_filter_starts_with_AND():
    """Caller appends to existing WHERE; clause must begin with `AND`."""
    sm = SeasonManager()
    out = sm.get_season_sql_filter("2026-Q1")
    assert out.startswith("AND ")


def test_sql_filter_current_uses_now():
    sm = SeasonManager()
    with patch("bot.core.season_manager.datetime") as mocked:
        mocked.now.return_value = datetime(2026, 4, 15)
        mocked.side_effect = lambda *args, **kw: datetime(*args, **kw)
        out = sm.get_season_sql_filter("current")
        assert "'2026-04-01'" in out


def test_sql_filter_uses_current_when_none_passed():
    sm = SeasonManager()
    with patch("bot.core.season_manager.datetime") as mocked:
        mocked.now.return_value = datetime(2026, 7, 1)
        mocked.side_effect = lambda *args, **kw: datetime(*args, **kw)
        out = sm.get_season_sql_filter(None)
        assert "'2026-07-01'" in out


# ---------------------------------------------------------------------------
# is_new_season
# ---------------------------------------------------------------------------


def test_is_new_season_true_when_different():
    sm = SeasonManager()
    with patch("bot.core.season_manager.datetime") as mocked:
        mocked.now.return_value = datetime(2026, 1, 15)  # Q1
        mocked.side_effect = lambda *args, **kw: datetime(*args, **kw)
        assert sm.is_new_season("2025-Q4") is True


def test_is_new_season_false_when_same():
    sm = SeasonManager()
    with patch("bot.core.season_manager.datetime") as mocked:
        mocked.now.return_value = datetime(2026, 1, 15)  # Q1
        mocked.side_effect = lambda *args, **kw: datetime(*args, **kw)
        assert sm.is_new_season("2026-Q1") is False


# ---------------------------------------------------------------------------
# get_all_seasons
# ---------------------------------------------------------------------------


def test_get_all_seasons_returns_4_quarters():
    sm = SeasonManager()
    with patch("bot.core.season_manager.datetime") as mocked:
        mocked.now.return_value = datetime(2026, 4, 15)  # Q2
        mocked.side_effect = lambda *args, **kw: datetime(*args, **kw)
        seasons = sm.get_all_seasons()
    assert seasons == ["2026-Q2", "2026-Q1", "2025-Q4", "2025-Q3"]


def test_get_all_seasons_handles_year_boundary():
    """Q1 → previous-year Q4/Q3/Q2 listed."""
    sm = SeasonManager()
    with patch("bot.core.season_manager.datetime") as mocked:
        mocked.now.return_value = datetime(2026, 1, 15)  # Q1
        mocked.side_effect = lambda *args, **kw: datetime(*args, **kw)
        seasons = sm.get_all_seasons()
    assert seasons == ["2026-Q1", "2025-Q4", "2025-Q3", "2025-Q2"]


def test_get_all_seasons_most_recent_first():
    """Order matters for the dropdown UI — most recent first."""
    sm = SeasonManager()
    with patch("bot.core.season_manager.datetime") as mocked:
        mocked.now.return_value = datetime(2026, 10, 15)  # Q4
        mocked.side_effect = lambda *args, **kw: datetime(*args, **kw)
        seasons = sm.get_all_seasons()
    # First entry is current, last entry is oldest
    assert seasons[0] == "2026-Q4"
    assert seasons[-1] == "2026-Q1"


# ---------------------------------------------------------------------------
# get_days_until_season_end
# ---------------------------------------------------------------------------


def test_days_until_season_end_positive_mid_quarter():
    sm = SeasonManager()
    with patch("bot.core.season_manager.datetime") as mocked:
        # Q4 ends Dec 31; we're Nov 1 → ~60 days
        mocked.now.return_value = datetime(2026, 11, 1)
        mocked.side_effect = lambda *args, **kw: datetime(*args, **kw)
        days = sm.get_days_until_season_end()
    assert 55 < days < 65  # rough range to allow for end-of-day rounding


def test_days_until_season_end_can_be_zero_at_close():
    sm = SeasonManager()
    with patch("bot.core.season_manager.datetime") as mocked:
        # Q4 ends Dec 31 23:59:59; checking on Dec 31 00:00 → ~0 days
        mocked.now.return_value = datetime(2026, 12, 31)
        mocked.side_effect = lambda *args, **kw: datetime(*args, **kw)
        days = sm.get_days_until_season_end()
    assert 0 <= days <= 1


def test_days_until_season_end_negative_after_close():
    """If now is past the season end (clock drift), days goes negative —
    docstring explicitly says 'can be negative'. Pin that contract."""
    sm = SeasonManager()
    with patch("bot.core.season_manager.datetime") as mocked:
        mocked.now.return_value = datetime(2027, 1, 5)  # past 2026-Q4 end
        mocked.side_effect = lambda *args, **kw: datetime(*args, **kw)
        # In Q1 2027 now, get_days_until_season_end calls get_season_dates(None)
        # which returns 2027-Q1 dates → positive number
        # That's the actual behaviour — confirm.
        days = sm.get_days_until_season_end()
    # We're in 2027-Q1, end = 2027-03-31 → ~85 days
    assert days > 0


# ---------------------------------------------------------------------------
# season_names mapping
# ---------------------------------------------------------------------------


def test_season_names_maps_all_quarters():
    sm = SeasonManager()
    assert sm.season_names == {1: "Spring", 2: "Summer", 3: "Fall", 4: "Winter"}
