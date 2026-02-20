from __future__ import annotations

import pytest

from website.backend.routers import api as api_router


class _TrendDB:
    def __init__(self, daily_rows=None, map_rows=None):
        self.daily_rows = list(daily_rows or [])
        self.map_rows = list(map_rows or [])
        self.calls = []

    async def fetch_all(self, query: str, params=()):
        self.calls.append((query, params))

        if "COUNT(DISTINCT r.id) as round_count" in query:
            return self.daily_rows
        if "SELECT r.map_name, COUNT(*) as play_count" in query:
            return self.map_rows

        raise AssertionError(f"Unexpected query in trends test: {query}")


@pytest.mark.asyncio
async def test_stats_trends_schema_and_map_distribution_normalization():
    db = _TrendDB(
        daily_rows=[("2026-02-14", 4, 16, 120)],
        map_rows=[
            (" maps/etl_supply.bsp ", 4),
            ("etl_supply", 2),
            ("maps\\etl_oasis.pk3", 1),
            ("   ", 9),
            (None, 3),
        ],
    )

    payload = await api_router.get_stats_trends(days=14, db=db)

    assert set(["dates", "rounds", "active_players", "kills", "map_distribution"]).issubset(payload.keys())
    assert isinstance(payload["dates"], list)
    assert len(payload["dates"]) == 15
    assert payload["map_distribution"] == {"etl_supply": 6, "etl_oasis": 1}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "map_rows",
    [
        [],
        [(None, 5), ("", 7), ("   ", 3)],
    ],
)
async def test_stats_trends_returns_empty_map_distribution_when_rows_are_empty_or_blank(map_rows):
    db = _TrendDB(daily_rows=[], map_rows=map_rows)

    payload = await api_router.get_stats_trends(days=30, db=db)

    assert payload["map_distribution"] == {}
    assert len(payload["dates"]) == 31
