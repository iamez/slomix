"""A date resolves to exactly ONE gaming session (owner definition 2026-08-14).

Sessions are gap-bounded units; a day can hold several and a session can cross
midnight, so a date is only a lookup key. The old strategy returned ALL rounds
of ALL sessions touching the date — a date shared by one session's midnight
tail and the next evening's session (2026-08-04 = gsid 142's tail + gsid 143)
was presented as one 19-map "session" on the sessions page, while BOX/
storytelling correctly showed 8. These tests pin the resolution rule:
started-on-date first, fallback to touching, most recent among several,
never merged.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.services.session_data_service import SessionDataService


def _service(candidates, rounds_by_gsid):
    """Fake adapter: 1st fetch_all → candidate (gsid, start_date) rows;
    2nd fetch_all → the chosen session's rounds; fetch_one → player count."""
    svc = SessionDataService.__new__(SessionDataService)
    svc.db_adapter = MagicMock()
    calls = {"n": 0}

    async def fetch_all(query, params=()):
        calls["n"] += 1
        if calls["n"] == 1:
            return candidates
        # Second call must be the single-session rounds query.
        assert "gaming_session_id = ?" in query, "rounds must be fetched for ONE session"
        (gsid,) = params
        return rounds_by_gsid[gsid]

    svc.db_adapter.fetch_all = fetch_all
    svc.db_adapter.fetch_one = AsyncMock(return_value=(6,))
    return svc


@pytest.mark.asyncio
async def test_tail_plus_new_session_date_picks_the_started_one():
    # 2026-08-04 touches gsid 142 (started 08-03, midnight tail) and gsid 143
    # (started 08-04). The date must resolve to 143 alone — never both.
    svc = _service(
        candidates=[(143, "2026-08-04"), (142, "2026-08-03")],
        rounds_by_gsid={143: [(9001, "supply", 1, "5:00"), (9002, "supply", 2, "4:00")]},
    )
    sessions, ids, _, players = await svc.fetch_session_data_by_date("2026-08-04")
    assert [s[0] for s in sessions] == [9001, 9002]
    assert players == 6


@pytest.mark.asyncio
async def test_tail_only_date_falls_back_to_the_whole_session():
    # Querying the tail date of a midnight-crossing session (no session
    # started that day) still returns that session complete.
    svc = _service(
        candidates=[(142, "2026-08-03")],  # touches 08-04, started 08-03
        rounds_by_gsid={142: [(8001, "etl_adlernest", 1, "3:00")]},
    )
    sessions, *_ = await svc.fetch_session_data_by_date("2026-08-04")
    assert [s[0] for s in sessions] == [8001]


@pytest.mark.asyncio
async def test_two_sessions_started_same_date_picks_most_recent():
    # A day can hold several sessions (owner: even 10); the date-keyed lookup
    # returns the most recent one, not a blend.
    svc = _service(
        candidates=[(146, "2026-08-12"), (145, "2026-08-12")],
        rounds_by_gsid={146: [(9500, "goldrush", 1, "6:00")]},
    )
    sessions, *_ = await svc.fetch_session_data_by_date("2026-08-12")
    assert [s[0] for s in sessions] == [9500]


@pytest.mark.asyncio
async def test_no_sessions_returns_empty():
    svc = _service(candidates=[], rounds_by_gsid={})
    assert await svc.fetch_session_data_by_date("1999-01-01") == (None, None, None, 0)
