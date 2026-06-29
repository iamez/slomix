"""Tests for WebsiteSessionDataService static-style helpers.

These three formatters surface in every Sessions/Recent-Matches page
render. A regression in `_time_ago` flips "Yesterday" labels into wrong
day counts; in `_get_format_tag` mislabels every 3v3/6v6 badge; in
`_team_name` swaps the Axis/Allies label on the winner badge.

Pin each contract.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from website.backend.services.website_session_data_service import (
    WebsiteSessionDataService,
)


@pytest.fixture
def svc():
    """Return a service instance bypassing the DB adapter (helpers don't touch it)."""
    return WebsiteSessionDataService.__new__(WebsiteSessionDataService)


# ---------------------------------------------------------------------------
# _team_name
# ---------------------------------------------------------------------------


def test_team_name_axis_for_1(svc):
    """Team int=1 → "Axis" (engine convention TEAM_AXIS=1; matches session-detail.js).
    Was previously inverted to "Allies" — see WAVE2 winner_team fix."""
    assert svc._team_name(1) == "Axis"


def test_team_name_allies_for_2(svc):
    """Team int=2 → "Allies"."""
    assert svc._team_name(2) == "Allies"


@pytest.mark.parametrize("team_int", [0, -1, 3, None])
def test_team_name_unknown_for_other_values(svc, team_int):
    """Anything else (0, None, draw, server-restart artefacts) → "Unknown".
    Critical: don't return empty string; the badge would render blank."""
    assert svc._team_name(team_int) == "Unknown"


# ---------------------------------------------------------------------------
# _time_ago
# ---------------------------------------------------------------------------


def _patch_now(year, month, day, hour=12):
    """Inject a fixed `datetime.now()` to make _time_ago deterministic."""
    fake_now = datetime(year, month, day, hour)
    return patch(
        "website.backend.services.website_session_data_service.datetime",
        wraps=datetime,
        now=lambda: fake_now,
    )


def test_time_ago_returns_today(svc):
    with patch(
        "website.backend.services.website_session_data_service.datetime"
    ) as mocked:
        mocked.now.return_value = datetime(2026, 5, 6, 12)
        mocked.strptime.side_effect = datetime.strptime
        mocked.combine.side_effect = datetime.combine
        mocked.min = datetime.min
        assert svc._time_ago("2026-05-06") == "Today"


def test_time_ago_returns_yesterday(svc):
    with patch(
        "website.backend.services.website_session_data_service.datetime"
    ) as mocked:
        mocked.now.return_value = datetime(2026, 5, 6, 12)
        mocked.strptime.side_effect = datetime.strptime
        mocked.combine.side_effect = datetime.combine
        mocked.min = datetime.min
        assert svc._time_ago("2026-05-05") == "Yesterday"


@pytest.mark.parametrize("days_ago, expected", [
    (2, "2 days ago"),
    (3, "3 days ago"),
    (6, "6 days ago"),
])
def test_time_ago_days_within_week(svc, days_ago, expected):
    with patch(
        "website.backend.services.website_session_data_service.datetime"
    ) as mocked:
        now = datetime(2026, 5, 6, 12)
        mocked.now.return_value = now
        mocked.strptime.side_effect = datetime.strptime
        mocked.combine.side_effect = datetime.combine
        mocked.min = datetime.min
        target = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        assert svc._time_ago(target) == expected


def test_time_ago_one_week_singular(svc):
    """`1 week ago` (singular) — pin so a future "1 weeks ago" plural
    regression is caught."""
    with patch(
        "website.backend.services.website_session_data_service.datetime"
    ) as mocked:
        now = datetime(2026, 5, 6, 12)
        mocked.now.return_value = now
        mocked.strptime.side_effect = datetime.strptime
        mocked.combine.side_effect = datetime.combine
        mocked.min = datetime.min
        target = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        assert svc._time_ago(target) == "1 week ago"


@pytest.mark.parametrize("days_ago, expected", [
    (14, "2 weeks ago"),
    (21, "3 weeks ago"),
    (29, "4 weeks ago"),
])
def test_time_ago_multi_weeks(svc, days_ago, expected):
    with patch(
        "website.backend.services.website_session_data_service.datetime"
    ) as mocked:
        now = datetime(2026, 5, 6, 12)
        mocked.now.return_value = now
        mocked.strptime.side_effect = datetime.strptime
        mocked.combine.side_effect = datetime.combine
        mocked.min = datetime.min
        target = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        assert svc._time_ago(target) == expected


def test_time_ago_more_than_30_days_returns_short_date(svc):
    """Past 30 days → "Apr 6" style abbreviated month+day."""
    with patch(
        "website.backend.services.website_session_data_service.datetime"
    ) as mocked:
        now = datetime(2026, 5, 6, 12)
        mocked.now.return_value = now
        mocked.strptime.side_effect = datetime.strptime
        mocked.combine.side_effect = datetime.combine
        mocked.min = datetime.min
        target = (now - timedelta(days=60)).strftime("%Y-%m-%d")
        out = svc._time_ago(target)
    # Result format is "Mar 07" or similar — month abbrev + day
    assert len(out) <= 7
    assert out[:3].isalpha()  # First 3 chars are month abbrev


def test_time_ago_handles_none(svc):
    assert svc._time_ago(None) == "Unknown"


def test_time_ago_handles_empty_string(svc):
    assert svc._time_ago("") == "Unknown"


def test_time_ago_handles_date_object_input(svc):
    """Accepts a `datetime.date`, not just a string — common in DB rows."""
    with patch(
        "website.backend.services.website_session_data_service.datetime"
    ) as mocked:
        now = datetime(2026, 5, 6, 12)
        mocked.now.return_value = now
        mocked.strptime.side_effect = datetime.strptime
        mocked.combine.side_effect = datetime.combine
        mocked.min = datetime.min
        out = svc._time_ago(date(2026, 5, 6))
    assert out == "Today"


def test_time_ago_falls_back_to_str_on_unparseable(svc):
    """A weirdly-formatted input → fall back to str() instead of crashing
    the entire matches API."""
    out = svc._time_ago("not-a-date")
    assert out == "not-a-date"


# ---------------------------------------------------------------------------
# _get_format_tag
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("player_count, expected", [
    (1,  "1v1"),    # one player → 1v1 (degenerate but still tagged)
    (2,  "1v1"),    # 1v1 cap
    (3,  "3v3"),    # rolls up to 3v3 once exceeding 2
    (4,  "3v3"),
    (5,  "3v3"),
    (6,  "3v3"),    # 3v3 cap
    (7,  "6v6"),
    (10, "6v6"),
    (12, "6v6"),    # 6v6 cap
])
def test_get_format_tag_known_brackets(svc, player_count, expected):
    assert svc._get_format_tag(player_count) == expected


@pytest.mark.parametrize("player_count, expected", [
    (14, "7v7"),
    (16, "8v8"),
    (20, "10v10"),
])
def test_get_format_tag_above_12_uses_half_count(svc, player_count, expected):
    """Above 12 players → fallback to NvN where N = total/2."""
    assert svc._get_format_tag(player_count) == expected


def test_get_format_tag_zero_players(svc):
    """Edge case: 0 players → 1v1 (catches "<= 2" branch).

    Pin so a future "if player_count == 0 → unknown" regression is loud."""
    assert svc._get_format_tag(0) == "1v1"


def test_get_format_tag_odd_high_count_truncates(svc):
    """13 players → 6v6 (integer division 13//2 = 6)."""
    assert svc._get_format_tag(13) == "6v6"
