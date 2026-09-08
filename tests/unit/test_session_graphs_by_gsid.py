"""GET /api/stats/session/{gsid}/graphs — the graphs keyed by gaming session.

The date-keyed endpoint merges the sessions of a day (13 of 176 days hold
more than one, measured 2026-09-07) and gates rounds by status only. The
gsid endpoint must select its rows through SESSION_ROUNDS_SQL — the trio
/basics and /rounds use (`counts_toward_totals`) — and say so in the body,
so a panel can name the total it agrees with.
"""
from __future__ import annotations

import asyncio

import pytest

from website.backend.routers import sessions_router as sr


class _Db:
    def __init__(self, round_rows, player_rows):
        self.calls: list[tuple[str, tuple]] = []
        self._round_rows = round_rows
        self._player_rows = player_rows

    async def fetch_all(self, sql, params=()):
        self.calls.append((sql, tuple(params)))
        if sql is sr.SESSION_ROUNDS_SQL or "FROM rounds r" in sql and "gaming_session_id = $1" in sql:
            return self._round_rows
        return self._player_rows


def _player_row(guid, name, round_id, kills=10, deaths=5):
    # Positional, in the order of _GRAPH_ROWS_SQL's SELECT list.
    return (guid, name, 1, kills, deaths, 3000, 2000, 600, 1, 2, 3, 4, 40.0, 0, 1, 2, 1.0, 30, 5, 0,
            "etl_adlernest", round_id, 0, 1, 1, 0, 0, 1, 0, 0, 0, 100, 80.0)


def test_the_gsid_endpoint_selects_counted_rounds_and_names_its_gate():
    round_rows = [(11323, "etl_adlernest", 1, 2, "2026-08-23", "20:00", None, None, 600),
                  (11324, "etl_adlernest", 2, 1, "2026-08-23", "20:12", None, None, 480)]
    db = _Db(round_rows, [_player_row("AAAA1111", "one", 11323), _player_row("AAAA1111", "one", 11324, 4, 9)])
    out = asyncio.run(sr.get_session_graphs(152, db))
    assert out["gate"] == "counts_toward_totals"
    assert out["gaming_session_id"] == 152 and out["rounds_counted"] == 2 and out["date"] == "2026-08-23"
    assert [p["name"] for p in out["players"]] == ["one"]
    assert out["players"][0]["combat_offense"]["kills"] == 14
    # The first query is the counted-rounds gate, the second is the graph SQL
    # restricted to exactly those ids — not a date, not a status.
    assert db.calls[0][0] is sr.SESSION_ROUNDS_SQL and db.calls[0][1] == (152,)
    sql, params = db.calls[1]
    assert "r.id IN ($1, $2)" in sql and params == (11323, 11324)
    assert "round_date" not in sql.split("WHERE", 1)[1] and "round_status" not in sql.split("WHERE", 1)[1]


def test_an_unknown_session_is_a_404_not_an_empty_graph():
    db = _Db([], [])
    with pytest.raises(sr.HTTPException) as exc:
        asyncio.run(sr.get_session_graphs(999999, db))
    assert exc.value.status_code == 404


def test_both_endpoints_share_one_builder():
    """A regression pin: the date form and the gsid form must compute a
    player the same way, which holds only while both call the one builder."""
    import inspect

    assert "_build_session_graph_players(rows)" in inspect.getsource(sr.get_session_graph_stats)
    assert "_build_session_graph_players(rows)" in inspect.getsource(sr.get_session_graphs)
