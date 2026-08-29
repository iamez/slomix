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
    "/api/rounds/999999/viz",
    "/api/rounds/999999/awards",
    "/api/stats/session/999999/rounds",
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


def _app() -> FastAPI:
    app = FastAPI()
    for module in (records_maps, records_matches, records_overview, records_trends,
                   records_weapons, sessions_router, challenges_router,
                   season_awards_router, diagnostics_router, players_router,
                   records_seasons):
        app.include_router(module.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: _NothingAtAll()
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
