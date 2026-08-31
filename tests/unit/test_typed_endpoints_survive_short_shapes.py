"""⛔ A CORPUS OF ONE SESSION CANNOT SHOW THE SHORT SHAPE OF A RESPONSE.

Flagged by the workstream next door after `session-detail`, typed against a
session that fills every field, crashed on three of the first four older
sessions it met. Their cause was an early `return` that OMITS keys rather than
nulling them — `{status, gaming_session_id, candidates: []}` with no
`total_votes`, so `total_votes === 0` was false for `undefined` and the drawing
branch ran anyway.

For a page that is a TypeError. For a `response_model` it is worse: FastAPI
validates the handler's return against the model AFTER the handler succeeds, so
a missing required key becomes a **500 on the server**, on an endpoint that
used to answer 200.

⚠️ STATIC ANALYSIS DID NOT SETTLE IT. An AST pass over my typed endpoints found
no early return dropping a required key — but it reads literal dicts only, and
12 of the returns build their value elsewhere (`return result`, `return maps`,
a list comprehension). "The scanner found nothing" and "nothing is there" are
different claims when the scanner cannot see.

⚠️ NEITHER DID THE LIVE DATABASE. Running these against the dev data passed 36
of 36 — but that only exercises the branches today's rows happen to reach, and
CI has no such data at all. So the empties are forced here instead: a stub that
answers nothing at all drives every handler down its short path, which is where
the omitted keys live.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from website.backend.dependencies import get_db
from website.backend.routers import (
    challenges_router,
    diagnostics_router,
    players_router,
    records_maps,
    records_matches,
    records_overview,
    records_seasons,
    records_trends,
    records_weapons,
    season_awards_router,
    sessions_router,
)

#: Every GET that carries a response_model and needs no path parameter beyond
#: ones an empty database still resolves.
TYPED_PATHS = [
    "/api/stats/maps",
    "/api/records/maps/segments",
    "/api/stats/activity-calendar",
    "/api/stats/activity-calendar?days=1",
    "/api/stats/trends",
    "/api/stats/trends?metrics=maps",
    "/api/stats/trends?metrics=rounds",
    "/api/stats/weapons",
    "/api/stats/weapons/hall-of-fame?period=month",
    "/api/challenges/current",
    "/api/voice-activity/current",
    "/api/player/search?query=zz",
    "/api/rounds/recent?limit=1",
    "/api/stats/session-leaderboard",
    "/api/stats/session-leaderboard?session_id=999999",
]

#: Routes that guard on existence first. Against an empty stub they answer 404
#: and the model never runs, so they are exercised with a stub that lets the
#: guard pass.
GUARDED_PATHS = [
    "/api/rounds/1/viz",
    "/api/rounds/1/awards",
    "/api/stats/session/1/rounds",
]


class _NothingAtAll:
    """Answers every query with nothing — the shortest path through each
    handler, and the one a single-session corpus never records."""

    async def fetch_all(self, *_a, **_k):
        return []

    async def fetch_one(self, *_a, **_k):
        return None

    async def fetch_val(self, *_a, **_k):
        return None

    async def execute(self, *_a, **_k):
        return None


class _RoundButNothingElse:
    """⛔ THE EMPTY STUB IS NOT ENOUGH FOR THE PARAMETERISED ROUTES.

    Three of the endpoints check that the round or session exists first and
    raise 404 when it does not. Against `_NothingAtAll` they answer 404 — which
    the assertion below counts as a pass while THE MODEL NEVER RAN. Exactly the
    trap the workstream next door hit choosing session 145 for a regression
    test: it 404s, so the panel that crashed was never rendered and the test was
    green against the very defect it was written for.

    So this stub says the round exists and everything under it is empty: the
    handler proceeds past its guard and down the short path, where the omitted
    keys are.
    """

    #: ⚠️ POSITIONAL TUPLES, AND THE THREE HANDLERS SELECT DIFFERENT COLUMNS.
    #: My first version returned one shape to all of them and produced two
    #: validation errors — which looked exactly like a defect in the endpoints
    #: until I read the SELECTs. A stub that lies about column order tests the
    #: stub, not the code.
    #:
    #:   viz     : id, map_name, round_date, round_number, winner_team,
    #:             actual_duration_seconds
    #:   awards  : map_name, round_number, round_date
    #:   session : id, map, round_number, played_at, duration, end_reason,
    #:             status, match_id, is_valid, is_bot_round
    _VIZ = (1, "supply", "2026-08-26", 1, 1, 454)
    _AWARDS = ("supply", 1, "2026-08-26")
    _SESSION_ROUND = (1, "supply", 1, "2026-08-26 21:09:58", 454, "NORMAL",
                      "completed", "m1", True, False)

    async def fetch_all(self, query, *_a, **_k):
        text = query if isinstance(query, str) else ""
        if "FROM rounds r" in text and "player_comprehensive_stats" not in text:
            return [self._SESSION_ROUND]
        return []

    async def fetch_one(self, query, *_a, **_k):
        text = query if isinstance(query, str) else ""
        if "winner_team" in text:
            return self._VIZ
        if "SELECT map_name, round_number, round_date" in text:
            return self._AWARDS
        return self._SESSION_ROUND

    async def fetch_val(self, *_a, **_k):
        return None

    async def execute(self, *_a, **_k):
        return None


def _app(db=None) -> FastAPI:
    app = FastAPI()
    for module in (records_maps, records_matches, records_overview, records_trends,
                   records_weapons, sessions_router, challenges_router,
                   season_awards_router, diagnostics_router, players_router,
                   records_seasons):
        app.include_router(module.router, prefix="/api")
    stub = db if db is not None else _NothingAtAll()
    app.dependency_overrides[get_db] = lambda: stub
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize("url", TYPED_PATHS)
async def test_the_short_shape_does_not_become_a_500(url):
    """404 is a fine answer. 4xx is a fine answer. 500 means the model and the
    handler disagree about what the handler returns — which no amount of live
    data will reveal if the live data never takes that branch."""
    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get(url)

    assert response.status_code < 500, (
        f"{url} answered {response.status_code} on an empty database — a "
        f"response model rejecting its own handler's output:\n"
        f"{response.text[:400]}")


@pytest.mark.asyncio
@pytest.mark.parametrize("url", GUARDED_PATHS)
async def test_a_guarded_route_reaches_its_model(url):
    """⚠️ A 404 IS NOT COVERAGE. These three raise 404 before the model runs,
    so against the empty stub they pass without proving anything. Here the
    round exists and everything under it is empty — the guard passes and the
    short path is actually taken."""
    transport = ASGITransport(app=_app(_RoundButNothingElse()))
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get(url)

    assert response.status_code != 404, (
        f"{url} still 404s — the stub does not satisfy its guard, so the model "
        f"is untested")
    assert response.status_code < 500, (
        f"{url} answered {response.status_code}:\n{response.text[:400]}")


@pytest.mark.asyncio
async def test_the_stub_really_is_empty():
    """States the premise: if the stub started returning rows, every case above
    would pass while testing the long path — silently, which is the dangerous
    way for a suite to stop working."""
    stub = _NothingAtAll()
    assert await stub.fetch_all("SELECT 1") == []
    assert await stub.fetch_one("SELECT 1") is None


@pytest.mark.asyncio
async def test_a_model_that_disagrees_is_actually_caught():
    """And that the harness can fail. A route whose model demands a key its
    handler never returns must produce the 500 this file exists to prevent."""
    from pydantic import BaseModel

    class NeedsMore(BaseModel):
        present: str
        absent: str

    app = FastAPI()

    @app.get("/probe", response_model=NeedsMore)
    async def probe():  # noqa: ANN202 - test route
        return {"present": "yes"}

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get("/probe")
    assert response.status_code >= 500, (
        "a model demanding a missing key did not fail — the check above proves "
        "nothing")
