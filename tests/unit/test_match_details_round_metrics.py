from __future__ import annotations

import pytest

from website.backend.routers import api as api_router


def _normalize_sql(query: str) -> str:
    return " ".join(query.split()).lower()


class _MatchDetailsDB:
    def __init__(self) -> None:
        self.match_query = ""

    async def fetch_one(self, query: str, params=()):
        normalized = _normalize_sql(query)
        if "from rounds" in normalized and "where id = $1" in normalized:
            return (10024, "supply", 1, "2026-03-05", 1, "09:58", "Allies win", 95, "10:00")
        if "from lua_round_teams" in normalized:
            return (598,)
        raise AssertionError(f"Unexpected fetch_one query: {normalized}")

    async def fetch_all(self, query: str, params=()):
        normalized = _normalize_sql(query)
        if "from information_schema.columns" in normalized:
            return [("time_played_percent",)]
        if "from player_comprehensive_stats" in normalized:
            self.match_query = query
            return [
                (
                    "carniee",
                    18,
                    17,
                    4075,
                    3724,
                    491,
                    1,
                    100,
                    36,
                    5,
                    34.8,
                    4,
                    0,
                    0,
                    0,
                    7,
                    120,
                    3.6,
                    159,
                    1,
                    0,
                    0,
                    0,
                    0,
                    "0A26D447",
                    12,
                    5,
                    51.4,
                    82.1,
                )
            ]
        raise AssertionError(f"Unexpected fetch_all query: {normalized}")


@pytest.mark.asyncio
async def test_get_match_details_returns_round_efficiency_and_headshot_pct(monkeypatch):
    db = _MatchDetailsDB()
    monkeypatch.setattr(api_router, "_PLAYER_STATS_COLUMNS_CACHE", None)

    payload = await api_router.get_match_details("10024", db=db)

    normalized_query = _normalize_sql(db.match_query)
    assert "kill_assists" in normalized_query
    assert "headshot_kills" in normalized_query
    assert "efficiency" in normalized_query

    player = payload["team1"]["players"][0]
    assert player["name"] == "carniee"
    assert player["kill_assists"] == 12
    assert player["efficiency"] == 51.4
    assert player["headshot_kills"] == 5
    assert player["headshot_pct"] == 27.8
    assert player["accuracy"] == 34.8
    assert player["played_pct_lua"] == 82.1
    assert player["time_dead_minutes"] == 3.6
    assert player["denied_playtime"] == 159


def test_classify_playstyle_uses_actual_survival_rate():
    scores = api_router.classify_playstyle(
        stats={
            "rounds_played": 5,
            "deaths": 30,
            "revives": 1,
            "gibs": 2,
            "damage_given": 5000,
            "damage_received": 4000,
        },
        dpm=240.0,
        kd=1.0,
        accuracy=38.5,
        survival_rate=68.2,
    )

    assert scores["survivability"] == 68.2
    assert scores["aggression"] == 50.0
    assert scores["precision"] == 77.0
