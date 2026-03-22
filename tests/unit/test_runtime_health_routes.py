"""
Tests for runtime health API routes.

Covers get_player_round_details and get_awards_leaderboard endpoints.
"""
from __future__ import annotations

import pytest

from website.backend.routers import players_router, records_router


def _normalize_sql(query: str) -> str:
    return " ".join(query.split()).lower()


class _PlayerRoundDetailsDB:
    def __init__(self) -> None:
        self.stats_query = ""
        self.weapon_query = ""

    async def fetch_one(self, query: str, params=()):
        normalized = _normalize_sql(query)
        if "from rounds where id = $1" in normalized:
            return ("supply", 2, "2026-03-05")
        if "from player_comprehensive_stats" in normalized:
            self.stats_query = query
            return (
                "Alpha",
                14,
                7,
                3210,
                2780,
                980,
                3,
                6,
                2,
                1,
                4,
                48.6,
                111,
                0,
                1,
                5,
                2,
                120,
                1,
                0,
                2,
                1,
                3,
                1,
                0,
                2,
                0,
                1.5,
                42,
                8,
            )
        raise AssertionError(f"Unexpected fetch_one query: {normalized}")

    async def fetch_all(self, query: str, params=()):
        normalized = _normalize_sql(query)
        if "from weapon_comprehensive_stats" not in normalized:
            raise AssertionError(f"Unexpected fetch_all query: {normalized}")
        self.weapon_query = query
        return [
            ("MP40", 9, 3, 2, 35, 70, 50.0),
            ("LUGER", 5, 4, 0, 10, 41, 24.4),
        ]


class _AwardsLeaderboardDB:
    def __init__(self) -> None:
        self.primary_query = ""

    async def fetch_all(self, query: str, params=()):
        normalized = _normalize_sql(query)
        if "with alias_map as" in normalized and "from round_awards ra" in normalized:
            self.primary_query = query
            return [("guid-1", "Alpha", 9, "Most Gibs", 4)]
        raise AssertionError(f"Unexpected fetch_all query: {normalized}")


@pytest.mark.asyncio
async def test_get_player_round_details_uses_postgres_columns_and_derives_hits():
    db = _PlayerRoundDetailsDB()

    payload = await players_router.get_player_round_details(
        round_id=10021,
        player_guid="2B5938F5",
        db=db,
    )

    normalized_query = _normalize_sql(db.stats_query)
    assert "bullets_fired" in normalized_query
    assert " time_played_seconds, headshot_kills, headshots, gibs, revives_given, times_revived, accuracy, bullets_fired," in normalized_query

    assert payload["player_name"] == "Alpha"
    assert payload["combat"]["headshot_kills"] == 3
    assert payload["combat"]["headshots"] == 6
    assert payload["combat"]["shots"] == 111
    assert payload["combat"]["hits"] == 45
    assert payload["support"]["kill_assists"] == 8
    assert payload["support"]["revives_given"] == 1
    assert payload["support"]["times_revived"] == 4
    assert payload["sprees"]["mega_kills"] == 0
    assert payload["time"]["dead_minutes"] == 1.5
    assert payload["misc"]["xp"] == 42
    assert payload["misc"]["self_kills"] == 1


@pytest.mark.asyncio
async def test_awards_leaderboard_groups_by_projected_guid_expression(monkeypatch):
    db = _AwardsLeaderboardDB()

    async def _resolve_alias_guid_map(_db, _names):
        return {}

    async def _resolve_name_guid_map(_db, _names):
        return {}

    async def _resolve_display_name(_db, _guid, fallback):
        return fallback

    monkeypatch.setattr(records_router, "resolve_alias_guid_map", _resolve_alias_guid_map)
    monkeypatch.setattr(records_router, "resolve_name_guid_map", _resolve_name_guid_map)
    monkeypatch.setattr(records_router, "resolve_display_name", _resolve_display_name)

    payload = await records_router.get_awards_leaderboard(limit=5, db=db)

    normalized_query = _normalize_sql(db.primary_query)
    # Current query groups by player_key, player_guid, ra.award_name
    assert "group by player_key, player_guid, ra.award_name" in normalized_query
    assert payload["leaderboard"][0]["guid"] == "guid-1"
    assert payload["leaderboard"][0]["award_count"] == 9
    assert payload["leaderboard"][0]["top_award"] == "Most Gibs"
