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


@pytest.mark.asyncio
async def test_candidate_query_carries_eligibility_gate():
    """A newer all-invalid session (e.g. a bot test sharing the date with a
    real gather) must never be chosen over an eligible one. The candidate
    query itself filters on validity/status/round_number — pin that the SQL
    carries the same predicate as the rounds fetch (CodeRabbit on #730)."""
    seen = {}
    svc = SessionDataService.__new__(SessionDataService)
    svc.db_adapter = MagicMock()

    async def fetch_all(query, params=()):
        if "start_date" in query:
            seen["candidate_sql"] = query
            return []
        return []

    svc.db_adapter.fetch_all = fetch_all
    svc.db_adapter.fetch_one = AsyncMock(return_value=(0,))
    await svc.fetch_session_data_by_date("2026-08-11")
    sql = seen["candidate_sql"]
    assert sql.count("is_valid") == 2          # outer + inner subquery
    assert sql.count("round_number IN (1, 2)") == 2
    assert sql.count("round_status IN ('completed', 'cancelled', 'substitution')") == 2
