"""Per-player movement summary — the parts that are not a plain aggregate.

`distance_per_min` is the reason this service exists rather than a raw SUM:
a player who stays alive twice as long walks twice as far without being any
busier, so the session total alone ranks survival, not activity.
"""
from __future__ import annotations

import pytest

from website.backend.services.storytelling.movement import _MovementMixin


class FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.queries: list[tuple[str, tuple]] = []

    async def fetch_all(self, query, params=None):
        self.queries.append((" ".join(query.split()), params or ()))
        return self.rows


class _Svc(_MovementMixin):
    def __init__(self, db):
        self.db = db


class _Scope:
    gaming_session_id = 144


def _row(guid, name, lives, distance, avg_speed, peak, sprint_sec, post_spawn, alive_ms):
    """Column 6 is SUM(sprint_sec), not a percentage — see the weighted share."""
    return (guid, name, lives, distance, avg_speed, peak, sprint_sec, post_spawn, alive_ms)


@pytest.mark.asyncio
async def test_distance_is_normalised_per_minute_alive():
    db = FakeDB([
        # Same total distance, one player alive twice as long.
        _row("AAAAAAAA", "vid", 10, 600000.0, 260.0, 800.0, 22.0, 55.0, 60 * 60000),
        _row("BBBBBBBB", "lgz", 10, 600000.0, 260.0, 800.0, 22.0, 55.0, 30 * 60000),
    ])
    out = await _Svc(db).compute_movement(_Scope())
    by = {p["guid_short"]: p for p in out["players"]}

    assert by["AAAAAAAA"]["distance_per_min"] == 10000.0
    assert by["BBBBBBBB"]["distance_per_min"] == 20000.0   # busier per minute


@pytest.mark.asyncio
async def test_zero_alive_time_does_not_divide_by_zero():
    db = FakeDB([_row("AAAAAAAA", "vid", 1, 500.0, 0.0, 0.0, 0.0, 0.0, 0)])
    out = await _Svc(db).compute_movement(_Scope())

    assert out["players"][0]["distance_per_min"] is None


@pytest.mark.asyncio
async def test_players_are_ordered_by_distance_and_names_stripped():
    db = FakeDB([
        _row("AAAAAAAA", "^1vid", 5, 100.0, 200.0, 400.0, 10.0, 40.0, 60000),
        _row("BBBBBBBB", "^7lgz", 5, 900.0, 210.0, 410.0, 12.0, 42.0, 60000),
    ])
    out = await _Svc(db).compute_movement(_Scope())

    assert [p["guid_short"] for p in out["players"]] == ["BBBBBBBB", "AAAAAAAA"]
    assert {p["name"] for p in out["players"]} == {"vid", "lgz"}
    assert out["unit"] == "et_units"


@pytest.mark.asyncio
async def test_session_without_track_data_says_so():
    out = await _Svc(FakeDB([])).compute_movement(_Scope())

    assert out["available"] is False
    assert out["reason"] == "no_track_data"
    assert out["players"] == []


@pytest.mark.asyncio
async def test_scopes_by_gaming_session_id_and_gates_bot_rounds():
    db = FakeDB([])
    await _Svc(db).compute_movement(_Scope())

    sql, params = db.queries[0]
    assert "JOIN rounds r ON r.id = pt.round_id" in sql
    assert "r.gaming_session_id = $1" in sql
    assert "r.is_bot_round IS DISTINCT FROM TRUE" in sql
    assert "r.is_valid IS DISTINCT FROM FALSE" in sql
    assert params == (144,)


@pytest.mark.asyncio
async def test_sprint_share_is_weighted_by_alive_time():
    """AVG(sprint_percentage) would count a 4-second life as heavily as a
    4-minute one; on session 144 the two differ by 3.8 points."""
    # 120 s sprinting out of 600 s alive = 20 %.
    db = FakeDB([_row("AAAAAAAA", "vid", 8, 1000.0, 250.0, 500.0, 120.0, 50.0, 600_000)])
    out = await _Svc(db).compute_movement(_Scope())

    assert out["players"][0]["sprint_pct"] == 20.0


@pytest.mark.asyncio
async def test_sprint_share_is_none_without_alive_time():
    db = FakeDB([_row("AAAAAAAA", "vid", 1, 10.0, 0.0, 0.0, 5.0, 0.0, 0)])
    out = await _Svc(db).compute_movement(_Scope())

    assert out["players"][0]["sprint_pct"] is None
    assert out["players"][0]["distance_per_min"] is None


@pytest.mark.asyncio
async def test_query_sums_sprint_seconds_rather_than_averaging_percentages():
    db = FakeDB([])
    await _Svc(db).compute_movement(_Scope())

    sql, _ = db.queries[0]
    assert "SUM(pt.sprint_sec)" in sql
    assert "AVG(pt.sprint_percentage)" not in sql
