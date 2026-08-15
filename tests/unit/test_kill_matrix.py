"""Kill matrix service — the shaping rules, not the SQL.

Two of these are the reason the endpoint exists at all rather than being a
raw GROUP BY: a self-kill row must never sit on the diagonal claiming a
dominance nobody had, and the row/column axes must be the SAME player list, or
"who killed whom" silently becomes two different orderings.
"""
from __future__ import annotations

import pytest

from website.backend.services.storytelling.kill_matrix import _KillMatrixMixin


class FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.queries: list[tuple[str, tuple]] = []

    async def fetch_all(self, query, params=None):
        self.queries.append((" ".join(query.split()), params or ()))
        return self.rows


class _Svc(_KillMatrixMixin):
    def __init__(self, db):
        self.db = db


class _Scope:
    gaming_session_id = 144


def _row(killer, victim, killer_name, victim_name, kills, gibs=0, revived=0):
    return (killer, victim, killer_name, victim_name, kills, gibs, revived)


@pytest.mark.asyncio
async def test_builds_a_square_matrix_with_shared_axes():
    db = FakeDB([
        _row("AAAAAAAA", "BBBBBBBB", "^1vid", "^7lgz", 45),
        _row("BBBBBBBB", "AAAAAAAA", "^7lgz", "^1vid", 12),
        _row("CCCCCCCC", "AAAAAAAA", "squuaze", "^1vid", 7),
    ])
    out = await _Svc(db).compute_kill_matrix(_Scope())

    assert out["available"] is True
    keys = [p["guid_short"] for p in out["players"]]
    # Everyone who killed OR died appears exactly once, on both axes.
    assert sorted(keys) == ["AAAAAAAA", "BBBBBBBB", "CCCCCCCC"]
    assert len(keys) == len(set(keys))
    # Colour codes are stripped for display.
    assert {p["name"] for p in out["players"]} == {"vid", "lgz", "squuaze"}
    assert out["total_kills"] == 64


@pytest.mark.asyncio
async def test_kills_and_deaths_are_counted_from_both_sides():
    db = FakeDB([
        _row("AAAAAAAA", "BBBBBBBB", "vid", "lgz", 45),
        _row("BBBBBBBB", "AAAAAAAA", "lgz", "vid", 12),
    ])
    out = await _Svc(db).compute_kill_matrix(_Scope())
    by_key = {p["guid_short"]: p for p in out["players"]}

    assert by_key["AAAAAAAA"]["kills"] == 45
    assert by_key["AAAAAAAA"]["deaths"] == 12
    assert by_key["BBBBBBBB"]["kills"] == 12
    assert by_key["BBBBBBBB"]["deaths"] == 45
    # Ordered by kills, so the night's top fragger reads first.
    assert out["players"][0]["guid_short"] == "AAAAAAAA"


@pytest.mark.asyncio
async def test_self_kills_never_reach_the_diagonal():
    db = FakeDB([
        _row("AAAAAAAA", "AAAAAAAA", "vid", "vid", 9),      # /kill rows
        _row("AAAAAAAA", "BBBBBBBB", "vid", "lgz", 3),
    ])
    out = await _Svc(db).compute_kill_matrix(_Scope())

    assert all(c["killer"] != c["victim"] for c in out["cells"])
    by_key = {p["guid_short"]: p for p in out["players"]}
    assert by_key["AAAAAAAA"]["kills"] == 3          # self-kills excluded
    assert by_key["AAAAAAAA"]["deaths"] == 0
    assert out["total_kills"] == 3


@pytest.mark.asyncio
async def test_gibs_and_revives_ride_along_with_each_pairing():
    db = FakeDB([_row("AAAAAAAA", "BBBBBBBB", "vid", "lgz", 10, gibs=4, revived=3)])
    out = await _Svc(db).compute_kill_matrix(_Scope())

    cell = out["cells"][0]
    assert (cell["kills"], cell["gibs"], cell["revived"]) == (10, 4, 3)


@pytest.mark.asyncio
async def test_session_without_proximity_data_says_so():
    out = await _Svc(FakeDB([])).compute_kill_matrix(_Scope())

    assert out["available"] is False
    assert out["reason"] == "no_kill_data"
    assert out["players"] == [] and out["cells"] == []


@pytest.mark.asyncio
async def test_scopes_by_gaming_session_id_and_gates_bot_rounds():
    """The scoping choice is the point: the canonical round key would see only
    the rounds that carry round_start_unix (15 % of session 144)."""
    db = FakeDB([])
    await _Svc(db).compute_kill_matrix(_Scope())

    sql, params = db.queries[0]
    assert "JOIN rounds r ON r.id = o.round_id" in sql
    assert "r.gaming_session_id = $1" in sql
    assert "r.is_bot_round IS DISTINCT FROM TRUE" in sql
    assert "r.is_valid IS DISTINCT FROM FALSE" in sql
    assert params == (144,)
