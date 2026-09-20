"""GET /api/stats/matches/{id} — the box score of one half.

Players are selected by the round's id. Selecting by (round_date, map_name,
round_number) — as the handler did until #988 — mixes two matches when a map
is replayed on the same date with the same half number, and the DISTINCT ON
then keeps one row per name from either. A round with no player rows is a
known absence: empty teams, not a 404.
"""
from __future__ import annotations

import asyncio

from website.backend.routers import records_matches as rm


class _Db:
    def __init__(self, round_row, player_rows):
        self.round_row = round_row
        self.player_rows = player_rows
        self.calls: list[tuple[str, tuple]] = []

    async def fetch_one(self, sql, params=()):
        self.calls.append((sql, tuple(params)))
        return self.round_row

    async def fetch_all(self, sql, params=()):
        self.calls.append((sql, tuple(params)))
        return self.player_rows


ROUND = (11321, "te_escape2", 2, "2026-08-23", 2, "6:28", "Completed", 152, "6:28", 196)


def _player(name, team, kills=5):
    return (name, kills, 3, 1200, 900, 300, team, 20.0, 4, 1, 40.0, 2, 0, 0, 1, 3, 100, 0.5, 30, 0, 0, 0, 0, 0, "AAAA1111", 2)


def test_players_are_selected_by_the_round_id_only():
    db = _Db(ROUND, [_player("axis one", 1), _player("allies one", 2)])
    out = asyncio.run(rm.get_match_details("11321", db))
    sql, params = db.calls[1]
    where = sql.split("WHERE", 1)[1]
    assert "round_id = $1" in where and params == (11321,)
    assert "round_date" not in where and "map_name" not in where and "round_number" not in where
    assert [p["name"] for p in out["team1"]["players"]] == ["axis one"]
    assert [p["name"] for p in out["team2"]["players"]] == ["allies one"]


def test_a_round_without_player_rows_answers_empty_teams_not_404():
    db = _Db(ROUND, [])
    out = asyncio.run(rm.get_match_details("11321", db))
    assert out["team1"]["players"] == [] and out["team2"]["players"] == []
    assert out["team1"]["totals"] == {"kills": 0, "deaths": 0, "damage": 0}
    assert out["player_count"] == 0
    assert out["match"]["id"] == 11321
