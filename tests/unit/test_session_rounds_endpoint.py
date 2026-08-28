"""⛔ A ROUND THAT WAS PLAYED MUST BE VISIBLE, EVEN IF IT DOES NOT COUNT.

`/stats/session/{id}/detail` filters `round_status = 'cancelled'` out of the
session and says nothing about it. The filter is right — those rounds should not
land in totals — but the silence is not: session 153 has one such round (11326,
supply R1, surrender, six players, valid rows), and the player who played it has
nowhere to learn why their round is missing.

`/stats/session/{id}/rounds` returns every round and labels it instead, so the
caller can show it AND leave it out of totals. One flag cannot do both jobs if
the row is absent.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from website.backend.dependencies import get_db
from website.backend.routers.sessions_router import (
    COUNTING_ROUND_STATUSES,
    SessionRounds,
    _counts_toward_totals,
    router,
)

#: (id, map, round_number, played_at, duration, end_reason, status, match_id,
#:  is_valid, is_bot_round)
_ROUNDS = [
    (1, "supply", 1, "2026-08-26 21:09:58", 454, "SURRENDER", "cancelled", "m1", True, False),
    (2, "supply", 1, "2026-08-26 21:23:58", 565, "OBJECTIVE", "completed", "m2", True, False),
    (3, "et_brewdog", 2, "2026-08-26 22:30:13", 164, "NORMAL", None, "m3", True, False),
    # completed but INVALID, and completed but a BOT round: the two cases the
    # first version of this endpoint marked as counting because it only looked
    # at the status string. 88 such rounds exist on the live database.
    (4, "supply", 2, "2026-08-26 21:40:00", 300, "NORMAL", "completed", "m2", False, False),
    (5, "radar", 1, "2026-08-26 22:00:00", 300, "NORMAL", "completed", "m4", True, True),
]
#: (round_id, guid, name, team, secs, gibs, dmg_recv, dmg_given, k, d, hs,
#:  hs_kills, rev_given, rev_taken, xp)
_PLAYERS = [
    (1, "AAA", "^1player one", 1, 450, 3, 1204, 1510, 8, 3, 12, 2, 1, 0, 55.0),
    (2, "AAA", "player one", 2, 560, 5, 2104, 1987, 9, 7, 20, 4, 3, 1, 88.0),
    (3, "BBB", "player two", 1, 160, 0, 712, 1104, 5, 3, 8, 1, 0, 2, 30.0),
]


class _StubDB:
    async def fetch_all(self, query, _params=None):
        if "FROM rounds r" in query and "player_comprehensive_stats" not in query:
            return _ROUNDS
        return _PLAYERS


class _EmptyDB:
    async def fetch_all(self, query, _params=None):
        return []


async def _get(db) -> tuple[int, dict]:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get("/api/stats/session/153/rounds")
    return response.status_code, (response.json() if response.content else {})


@pytest.mark.asyncio
async def test_a_cancelled_round_is_returned_not_filtered():
    status, body = await _get(_StubDB())
    assert status == 200
    ids = [r["round_id"] for r in body["rounds"]]
    assert 1 in ids, "the cancelled round was dropped — the defect this fixes"


@pytest.mark.asyncio
async def test_it_is_returned_and_marked_as_not_counting():
    """Both halves of the fact. Returning it without the flag would put a
    surrendered round into every total; flagging it without returning it is
    what the old endpoint did."""
    _, body = await _get(_StubDB())
    cancelled = next(r for r in body["rounds"] if r["round_id"] == 1)
    assert cancelled["round_status"] == "cancelled"
    assert cancelled["counts_toward_totals"] is False
    assert cancelled["players"], "a cancelled round still has its roster"


@pytest.mark.asyncio
async def test_the_counts_disagree_on_purpose():
    _, body = await _get(_StubDB())
    assert body["total_rounds"] == 5
    assert body["counted_rounds"] == 2, (
        "counted and total must differ when a round does not count — equal "
        "numbers would hide the very thing this endpoint exists to show")


@pytest.mark.asyncio
async def test_status_alone_does_not_decide():
    """⚠️ THIS TEST USED TO ASSERT THE WEAKER RULE — that every non-cancelled
    round counts. Two of the fixtures are `completed` and still must not:
    round 4 is invalid, round 5 is a bot round. Reading only the status is the
    defect this endpoint shipped with."""
    _, body = await _get(_StubDB())
    by_id = {r["round_id"]: r for r in body["rounds"]}
    assert by_id[2]["counts_toward_totals"] is True    # completed, valid, human
    assert by_id[3]["counts_toward_totals"] is True    # null status
    assert by_id[4]["counts_toward_totals"] is False   # completed but invalid
    assert by_id[5]["counts_toward_totals"] is False   # completed but bot
    assert by_id[4]["round_status"] == by_id[2]["round_status"], (
        "the two disagree on counting while sharing a status — which is "
        "exactly why status alone cannot decide")


@pytest.mark.asyncio
async def test_a_null_status_counts():
    """`round_status IS NULL` is the historical shape for an ordinary round.
    Treating null as "not counting" would silently empty older sessions."""
    _, body = await _get(_StubDB())
    null_status = next(r for r in body["rounds"] if r["round_status"] is None)
    assert null_status["counts_toward_totals"] is True


@pytest.mark.asyncio
async def test_the_fields_the_rest_of_the_site_omits_are_present():
    """`time_played_seconds`, `gibs`, `damage_received` — the three a player
    asks about first and the reason this endpoint exists."""
    _, body = await _get(_StubDB())
    player = body["rounds"][0]["players"][0]
    for field in ("time_played_seconds", "gibs", "damage_received"):
        assert field in player, f"{field} missing"
    assert player["gibs"] == 3
    assert player["damage_received"] == 1204


@pytest.mark.asyncio
async def test_colour_codes_are_stripped_from_names():
    _, body = await _get(_StubDB())
    assert body["rounds"][0]["players"][0]["player_name"] == "player one"


@pytest.mark.asyncio
async def test_an_unknown_session_is_404_not_an_empty_success():
    """An empty list and a session that does not exist have the same shape.
    Answering 200 with nothing would make a typo look like a quiet night."""
    status, _ = await _get(_EmptyDB())
    assert status == 404


def test_the_counting_set_is_an_allowlist():
    """⛔ ALLOWLIST, NOT DENYLIST.

    The first version listed the statuses it knew to exclude, which marked as
    counting any status invented later — plus invalid and bot rounds, because
    it read only the status string.
    """
    assert {"completed", "substitution"} == COUNTING_ROUND_STATUSES
    assert "cancelled" not in COUNTING_ROUND_STATUSES


def test_an_invalid_or_bot_round_does_not_count_even_when_completed():
    """The session-total queries require valid, non-bot, completed/substitution
    /null. A flag that says otherwise is worse than no flag: it looks
    authoritative while disagreeing with every total on the site."""
    assert _counts_toward_totals("completed", True, False) is True
    assert _counts_toward_totals(None, True, False) is True
    assert _counts_toward_totals("substitution", True, False) is True
    assert _counts_toward_totals("completed", False, False) is False   # invalid
    assert _counts_toward_totals("completed", True, True) is False     # bot
    assert _counts_toward_totals("warmup", True, False) is False       # unknown
    assert _counts_toward_totals("cancelled", True, False) is False


def test_the_response_model_declares_the_measured_fields():
    fields = SessionRounds.model_fields
    assert {"counted_rounds", "total_rounds", "rounds"} <= set(fields)


class TestTheSqlItself:
    """⚠️ THE STUB CANNOT SEE A WHERE CLAUSE.

    `_StubDB` returns fixed rows whatever the query says, so
    `test_a_cancelled_round_is_returned_not_filtered` passes even if the SQL
    grows `AND round_status <> 'cancelled'` — mutation-checked, it did.

    The stub tests the assembly; these test the query text, which is the only
    place the filtering decision actually lives.
    """

    def _sql(self) -> str:
        from website.backend.routers.sessions_router import _SESSION_ROUNDS_SQL
        return _SESSION_ROUNDS_SQL

    def test_the_round_query_does_not_filter_on_status(self):
        sql = self._sql()
        assert "round_status" in sql, "status must be SELECTed to be shown"
        where = sql.split("WHERE", 1)[1]
        assert "round_status" not in where, (
            "the round query filters on status — the cancelled round vanishes "
            "again and nothing tells the player why")

    def test_it_still_filters_the_things_that_are_not_rounds(self):
        """Removing one filter must not remove them all: R0 rows are the
        importer's summary copy, not a played round."""
        assert "round_number IN (1, 2)" in self._sql()

    def test_the_player_query_excludes_bots_by_both_identities(self):
        from website.backend.routers.sessions_router import _SESSION_PLAYERS_SQL
        assert "OMNIBOT" in _SESSION_PLAYERS_SQL
        assert "[BOT]" in _SESSION_PLAYERS_SQL, (
            "bot identity is the union of guid and name; one predicate lets "
            "a [BOT] with an ordinary guid into the roster")

    def test_the_duration_is_the_measured_clock(self):
        """`rounds.actual_time` is the stopwatch TARGET and overstates ~15% of
        rounds (RCA 2026-08-18). It may only be the fallback."""
        sql = self._sql()
        assert "actual_duration_seconds" in sql
        measured_first = sql.index("actual_duration_seconds") < sql.index("actual_time")
        assert measured_first, "the target clock is being preferred over the measurement"


def test_played_at_is_not_the_ingestion_time():
    """`created_at` is when the ROW was written, not when the round was played.

    The importer supplies round_date and round_time and leaves created_at at
    its database default, so for historical imports the two diverge — measured
    on this database: 907 rounds have a created_at on a different DAY than
    their round_date. Showing an import date as "when this happened" is not a
    rounding error.
    """
    from website.backend.routers.sessions_router import _SESSION_ROUNDS_SQL
    select = _SESSION_ROUNDS_SQL.split("FROM", 1)[0]
    assert "round_date" in select and "round_time" in select
    assert "AS played_at" in select
    # created_at may remain only as the fallback inside COALESCE
    assert "COALESCE(" in select, "the fallback for rows without a clock is gone"
