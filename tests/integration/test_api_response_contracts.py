"""Response-shape contract tests (W8, docs/TASKS_FOR_SONNET_2026-07-29.md).

The reference incident: a backend change from five radar axes to four would
have blanked every profile chart, because the frontend RadarChart used to be
hardcoded to five sides and nothing asserted the contract — caught in code
review, not by a test. The frontend no longer hardcodes an axis count (it
derives sides from axes.length), but the API contract itself is still fixed
at 4 axes in a specific order (Aggression, Awareness, Teamplay, Timing) —
that's what this test pins. Contract drift like this is quiet: nothing
errors, the UI just shows the wrong thing or nothing.

Uses the same dependency-override + stub-DB pattern as
tests/unit/test_proximity_serving_layer_audit.py: mount just the router
under test, override get_db with a stub that returns empty result sets, and
assert the response shape survives the "no data" path. This is deliberately
NOT a data-correctness test (that's what the audit-fix tests are for) — it
only pins field names, types, and array lengths so a rename/removal fails
loudly here instead of silently in the UI.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from website.backend.dependencies import get_db
from website.backend.routers.proximity_player import router as proximity_player_router
from website.backend.routers.records_overview import router as records_overview_router
from website.backend.routers.records_seasons import router as records_seasons_router


class _EmptyDB:
    """Returns empty result sets for every query — exercises the no-data path.

    fetch_val is query-aware: a real empty table makes MIN/MAX aggregates
    return SQL NULL (-> None), while COUNT(*) returns 0 — collapsing both to
    a constant 0 would silently hide the "should be null, not zero" contract
    the overview endpoint promises for rounds_since/rounds_latest.
    """

    async def fetch_all(self, query, params=None):
        return []

    async def fetch_one(self, query, params=None):
        return None

    async def fetch_val(self, query, params=None):
        if "MIN(" in query or "MAX(" in query:
            return None
        return 0


def _app(router, db=None) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    if db is not None:
        app.dependency_overrides[get_db] = lambda: db
    return app


_req_counter = 0


async def _get(router, path, db=None):
    # Unique X-Forwarded-For per request: slowapi/RateLimitMiddleware key on
    # client IP with in-memory storage shared across the pytest process —
    # see test_proximity_serving_layer_audit.py for the same gotcha.
    global _req_counter
    _req_counter += 1
    transport = ASGITransport(app=_app(router, db))
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        return await client.get(
            path,
            headers={"X-Forwarded-For": f"10.98.{_req_counter // 250}.{_req_counter % 250}"},
        )


@pytest.mark.asyncio
async def test_proximity_radar_returns_exactly_four_axes():
    """Reference incident: 5->4 axes would blank every profile RadarChart."""
    response = await _get(
        proximity_player_router,
        "/api/proximity/player/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/radar",
        db=_EmptyDB(),
    )

    assert response.status_code == 200
    body = response.json()

    assert "axes" in body
    assert isinstance(body["axes"], list)
    assert len(body["axes"]) == 4, (
        f"expected exactly 4 radar axes, got {len(body['axes'])} — "
        "this is the player-radar-v2 API contract, independent of the "
        "frontend's (now variable) axis-count support"
    )
    # Exact label sequence: ProximityPlayer.tsx branches on
    # `a.label === 'Teamplay'` to mark fallback/degraded sourcing, so a
    # rename or reorder needs to fail loudly here.
    assert [axis["label"] for axis in body["axes"]] == [
        "Aggression", "Awareness", "Teamplay", "Timing",
    ]
    for axis in body["axes"]:
        assert set(axis.keys()) >= {"label", "value"}
        assert isinstance(axis["label"], str) and axis["label"]
        assert isinstance(axis["value"], (int, float))

    # composite is fed into RadarChart alongside axes (ProximityPlayer.tsx) —
    # a dropped/renamed/mistyped field would silently blank that display.
    assert "composite" in body
    assert isinstance(body["composite"], (int, float))


@pytest.mark.asyncio
async def test_stats_overview_required_fields_present_and_typed():
    response = await _get(records_overview_router, "/api/stats/overview", db=_EmptyDB())

    assert response.status_code == 200
    body = response.json()

    required_int_fields = [
        "rounds", "players", "sessions", "total_kills",
        "rounds_14d", "players_all_time", "players_14d",
        "sessions_14d", "total_kills_14d", "window_days",
    ]
    for field in required_int_fields:
        assert field in body, f"missing required field: {field}"
        # bool is a subclass of int in Python — isinstance(True, int) is
        # True, so a field that regressed to a JSON boolean would pass an
        # isinstance check. formatNumber() on the frontend expects a number.
        assert type(body[field]) is int, f"{field} should be int, got {type(body[field])}"

    # Present even with no data — null, not missing/omitted. Verified against
    # the actual empty-table SQL behavior (MIN/MAX -> NULL), not just against
    # this stub's default.
    for field in ("rounds_since", "rounds_latest", "most_active_overall", "most_active_14d"):
        assert field in body, f"missing required field: {field}"
        assert body[field] is None, f"{field} should be null on the no-data path, got {body[field]!r}"


@pytest.mark.asyncio
async def test_seasons_current_required_fields_present():
    # No DB dependency for this endpoint (pure SeasonManager logic).
    response = await _get(records_seasons_router, "/api/seasons/current")

    assert response.status_code == 200
    body = response.json()

    # Every field except days_left is declared as a required (non-nullable)
    # string in website/frontend/src/api/types.ts SeasonInfo — a regression
    # to null/number/object there would silently break string interpolation
    # on the frontend.
    required_string_fields = [
        "id", "name", "start_date", "end_date",
        "next_season_id", "next_season_name", "next_season_start",
    ]
    for field in required_string_fields:
        assert field in body, f"missing required field: {field}"
        assert type(body[field]) is str, f"{field} should be str, got {type(body[field])}"

    assert "days_left" in body, "missing required field: days_left"
    assert type(body["days_left"]) is int, f"days_left should be int, got {type(body['days_left'])}"
