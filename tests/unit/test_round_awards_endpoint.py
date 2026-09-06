"""/rounds/{round_id}/awards — the per-round breakdown of the award table.

⛔⛔ WHY THE BOT FILTER IS PINNED HERE. The session-level aggregate over this
same table has dropped bots since it was written (`sessions_router.py:2634`).
This endpoint did not, so one fact had two answers: 2120 of the 27269 award
rows are bots across 83 rounds, and a person opening a round saw names the
session summary had hidden. The filter is not cosmetic — it is what makes the
two views agree.

⭐ Measured before the change: 2059 of those 2120 (97%) sit in rounds with NO
human award at all, so the filter empties an all-bot round rather than
thinning a mixed one. That is why the empty state matters as much as the
filter, and both are tested here.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from website.backend.dependencies import get_db
from website.backend.routers.records_matches import router

#: round_awards column order: award_name, player_name, player_guid,
#: award_value, award_value_numeric
_HUMAN = ("Most Kills", "alpha", "AAAAAAAA", "31", 31.0)
#: ⚠️ Both nullable fields at once. `numeric` is None for awards whose figure
#: is a rendered string; typing it `float` once turned 3 rounds out of 40 into
#: a 500. `guid` is None for rows that never resolved to a player (496 today).
_UNRESOLVED = ("Best Streak", "nameless", None, "7 in a row", None)
_BOT = ("Most Kills", "[BOT] eve", "OMNIBOT04bc6dd06bc927a9934367f17", "99", 99.0)


class _StubDB:
    def __init__(self, award_rows, round_row=("supply", 2, "2026-09-01")):
        self.award_rows = award_rows
        self.round_row = round_row
        self.queries: list[str] = []

    async def fetch_one(self, query, params=None):
        self.queries.append(query)
        q = " ".join(query.split())
        # ⛔ A stub that answers every fetch_one with the same tuple LIES. The
        # handler also resolves display names through fetch_one, and returning
        # the round row there made every award's player read "supply" — the
        # map name — while the test still saw a 200.
        if "FROM rounds" in q:
            return self.round_row
        return None

    async def fetch_all(self, query, params=None):
        self.queries.append(query)
        q = " ".join(query.split())
        if "FROM round_awards" in q:
            rows = list(self.award_rows)
            # The stub behaves like the database: it applies the filter the
            # SQL asked for. ⛔ Asserting `"NOT LIKE" in sql` instead would
            # pass for a filter that is present but wrong.
            if "NOT LIKE 'OMNIBOT%'" in q:
                rows = [r for r in rows if not str(r[2] or "").upper().startswith("OMNIBOT")]
            if "NOT LIKE '%[BOT]%'" in q:
                rows = [r for r in rows if "[BOT]" not in str(r[1] or "")]
            return rows
        return []


def _client(db):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


def _all_players(payload) -> list[str]:
    return [a["player"] for cat in payload["categories"].values() for a in cat["awards"]]


@pytest.mark.asyncio
async def test_a_bot_award_does_not_reach_the_round_view():
    db = _StubDB([_HUMAN, _BOT])
    async with _client(db) as c:
        r = await c.get("/api/rounds/4242/awards")
    assert r.status_code == 200
    players = _all_players(r.json())
    assert "alpha" in players
    assert not [p for p in players if "[BOT]" in p], "the session summary hides these; so must the round"


@pytest.mark.asyncio
async def test_an_all_bot_round_answers_empty_rather_than_inventing_winners():
    """⛔ 97% of bot award rows live in rounds like this one."""
    db = _StubDB([_BOT])
    async with _client(db) as c:
        r = await c.get("/api/rounds/4242/awards")
    assert r.status_code == 200
    assert r.json()["categories"] == {}


@pytest.mark.asyncio
async def test_an_award_with_no_guid_and_no_numeric_still_renders():
    db = _StubDB([_UNRESOLVED])
    async with _client(db) as c:
        r = await c.get("/api/rounds/4242/awards")
    assert r.status_code == 200, r.text
    entries = [a for cat in r.json()["categories"].values() for a in cat["awards"]]
    assert len(entries) == 1
    assert entries[0]["value"] == "7 in a row"
    assert entries[0]["numeric"] is None


@pytest.mark.asyncio
async def test_an_unknown_round_is_404_not_an_empty_award_set():
    db = _StubDB([_HUMAN], round_row=None)
    async with _client(db) as c:
        r = await c.get("/api/rounds/999999/awards")
    assert r.status_code == 404
