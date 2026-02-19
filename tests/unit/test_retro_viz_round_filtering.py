from __future__ import annotations

from datetime import date

import pytest

from website.backend.routers.api import get_recent_rounds, get_round_viz


class _RecentRoundsDB:
    def __init__(self, rows):
        self.rows = rows
        self.last_query = None
        self.last_params = None

    async def fetch_all(self, query, params):
        self.last_query = query
        self.last_params = params
        return self.rows


class _RoundVizDB:
    def __init__(self, round_row, player_rows):
        self.round_row = round_row
        self.player_rows = player_rows

    async def fetch_one(self, query, params):
        return self.round_row

    async def fetch_all(self, query, params):
        return self.player_rows


@pytest.mark.asyncio
async def test_recent_rounds_filters_out_round_zero_in_sql_and_serializes_round_label():
    db = _RecentRoundsDB(
        rows=[
            (101, "goldrush", date(2026, 2, 17), 2, 18),
        ]
    )

    payload = await get_recent_rounds(limit=50, db=db)

    assert "WHERE r.round_number > 0" in db.last_query
    assert db.last_params == (50,)
    assert payload == [
        {
            "id": 101,
            "map_name": "goldrush",
            "round_date": "2026-02-17",
            "round_number": 2,
            "round_label": "R2",
            "player_count": 18,
        }
    ]


@pytest.mark.asyncio
async def test_round_viz_serializes_match_summary_label_for_round_zero():
    db = _RoundVizDB(
        round_row=(99, "supply", date(2026, 2, 17), 0, 1, 1230),
        player_rows=[
            (
                "Player One",
                "guid-1",
                20,
                11,
                3200,
                2100,
                0,
                0,
                900,
                120,
                2,
                3,
                0,
                45,
                500,
                7,
                71.5,
                185.0,
            )
        ],
    )

    payload = await get_round_viz(round_id=99, db=db)

    assert payload["round_number"] == 0
    assert payload["round_label"] == "Match Summary"
    assert payload["player_count"] == 1
