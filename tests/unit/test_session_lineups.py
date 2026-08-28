"""/api/stats/session/{id}/lineups — the basic stat the site never had.

Pins the derivation the endpoint performs over lua_round_teams rosters:
persistent teams via guid overlap across stopwatch side swaps, membership
deltas between consecutive rounds (a substitution is a one-out/one-in pair,
a team switch is a mirror joined/left), and the honest unmeasured count for
pre-webhook rounds (absence is never "no changes").
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from website.backend.dependencies import get_db
from website.backend.routers.sessions_router import router as sessions_router


def _p(guid, name):
    return {"guid": guid, "name": name}


def _round(rid, map_name, rn, axis, allies):
    import json

    return (rid, map_name, rn, json.dumps(axis), json.dumps(allies))


class _StubDb:
    def __init__(self, rounds, team_rows=None):
        self.rounds = rounds
        self.team_rows = team_rows or []

    async def fetch_all(self, query, params=None):
        if "session_teams" in query:
            return self.team_rows
        return self.rounds

    async def fetch_val(self, query, params=None):
        return 0  # default: the session has no rounds at all -> 404


def _client(db):
    app = FastAPI()
    app.include_router(sessions_router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


A1, A2, A3 = _p("AAAA0001", "ana"), _p("AAAA0002", "bor"), _p("AAAA0003", "cvet")
B1, B2, B3 = _p("BBBB0001", "dane"), _p("BBBB0002", "eva"), _p("BBBB0003", "fran")
SUB = _p("CCCC0001", "gal")


@pytest.mark.asyncio
async def test_stable_evening_has_two_teams_and_no_changes():
    db = _StubDb([
        _round(1, "supply", 1, [A1, A2, A3], [B1, B2, B3]),
        # Stopwatch swap: same people, opposite sides — NOT a change.
        _round(2, "supply", 2, [B1, B2, B3], [A1, A2, A3]),
    ])
    async with _client(db) as c:
        body = (await c.get("/api/stats/session/7/lineups")).json()
    assert body["changes"] == []
    assert body["rounds_without_roster"] == 0
    teams = {t["key"]: [p["name"] for p in t["players"]] for t in body["teams"]}
    assert sorted(teams["a"]) == ["ana", "bor", "cvet"]
    assert sorted(teams["b"]) == ["dane", "eva", "fran"]


@pytest.mark.asyncio
async def test_substitution_is_a_named_out_in_pair():
    db = _StubDb([
        _round(1, "supply", 1, [A1, A2, A3], [B1, B2, B3]),
        _round(2, "goldrush", 1, [A1, A2, SUB], [B1, B2, B3]),
    ])
    async with _client(db) as c:
        body = (await c.get("/api/stats/session/7/lineups")).json()
    assert len(body["changes"]) == 1
    change = body["changes"][0]
    assert change["team"] == "a"
    assert change["swaps"] == [
        {"out": {"guid": "AAAA0003", "name": "cvet"},
         "incoming": {"guid": "CCCC0001", "name": "gal"}}
    ]
    # The roster is the STARTING lineup; the substitution lives in changes.
    a_names = {p["name"] for t in body["teams"] if t["key"] == "a" for p in t["players"]}
    assert a_names == {"ana", "bor", "cvet"}


@pytest.mark.asyncio
async def test_team_switch_is_mirrored_not_a_swap():
    db = _StubDb([
        _round(1, "supply", 1, [A1, A2, A3], [B1, B2, B3]),
        # A3 and B3 trade teams (the goldrush-evening event, 2026-08-26).
        _round(2, "escape", 1, [A1, A2, B3], [B1, B2, A3]),
    ])
    async with _client(db) as c:
        body = (await c.get("/api/stats/session/7/lineups")).json()
    by_team = {c_["team"]: c_ for c_ in body["changes"]}
    assert by_team["a"]["joined"][0]["name"] == "fran"
    assert by_team["a"]["left"][0]["name"] == "cvet"
    assert by_team["b"]["joined"][0]["name"] == "cvet"
    # A cross-team move must NOT be presented as a substitution pair.
    assert by_team["a"]["swaps"] == []
    assert by_team["b"]["swaps"] == []


@pytest.mark.asyncio
async def test_unmeasured_history_is_counted_not_silent():
    db = _StubDb([
        (1, "supply", 1, None, None),
        (2, "supply", 2, None, None),
    ])
    async with _client(db) as c:
        body = (await c.get("/api/stats/session/7/lineups")).json()
    assert body["teams"] == []
    assert body["changes"] == []
    assert body["rounds_without_roster"] == 2


@pytest.mark.asyncio
async def test_unknown_session_is_404():
    async with _client(_StubDb([])) as c:
        assert (await c.get("/api/stats/session/999/lineups")).status_code == 404


@pytest.mark.asyncio
async def test_bots_never_reach_the_lineup():
    bot = _p("OMNIBOT0", "[BOT]carniee")
    bot2 = _p("OMNIBOT1", "[bot]lower")
    db = _StubDb([
        _round(1, "supply", 1, [A1, A2, bot], [B1, B2, bot2]),
        # The historical bot->human turnover shape (sessions 104/116):
        # without the filter this was the only full-overlap tie the team
        # mapping ever hit.
        _round(2, "supply", 2, [B1, B2], [A1, A2]),
    ])
    async with _client(db) as c:
        body = (await c.get("/api/stats/session/7/lineups")).json()
    names = {p["name"] for t in body["teams"] for p in t["players"]}
    assert names == {"ana", "bor", "dane", "eva"}
    assert body["changes"] == []


@pytest.mark.asyncio
async def test_cancelled_only_session_is_unmeasured_not_404():
    class _CancelledOnlyDb(_StubDb):
        async def fetch_val(self, query, params=None):
            return 3  # the session exists; its rounds are all cancelled

    db = _CancelledOnlyDb([])
    async with _client(db) as c:
        resp = await c.get("/api/stats/session/7/lineups")
    assert resp.status_code == 200
    body = resp.json()
    assert body["teams"] == [] and body["rounds_without_roster"] == 0


@pytest.mark.asyncio
async def test_starting_lineup_survives_a_team_switch():
    db = _StubDb([
        _round(1, "supply", 1, [A1, A2, A3], [B1, B2, B3]),
        _round(2, "escape", 1, [A1, A2, B3], [B1, B2, A3]),
    ])
    async with _client(db) as c:
        body = (await c.get("/api/stats/session/7/lineups")).json()
    teams = {t["key"]: sorted(p["name"] for p in t["players"]) for t in body["teams"]}
    # 3v3 stays 3v3 — the switch is narrated, not folded into the roster.
    assert teams["a"] == ["ana", "bor", "cvet"]
    assert teams["b"] == ["dane", "eva", "fran"]
