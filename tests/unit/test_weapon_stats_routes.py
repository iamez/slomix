from __future__ import annotations

import pytest

from website.backend.routers import api as api_router


class _FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.last_query = ""
        self.last_params = ()

    async def fetch_all(self, query: str, params=()):
        self.last_query = query
        self.last_params = params
        return self.rows


@pytest.mark.asyncio
async def test_get_weapon_stats_returns_cleaned_rows():
    db = _FakeDB(
        [
            ("WS_MP40", 120, 32, 550, 300, 54.6),
            ("WS_THOMPSON", 90, 21, 400, 210, 52.5),
        ]
    )

    payload = await api_router.get_weapon_stats(period="all", limit=20, db=db)

    assert isinstance(payload, list)
    assert len(payload) == 2
    assert payload[0]["name"] == "Mp40"
    assert payload[0]["weapon_key"] == "mp40"
    assert payload[0]["kills"] == 120
    assert payload[0]["headshots"] == 32
    assert payload[0]["accuracy"] == 54.6


@pytest.mark.asyncio
async def test_get_weapon_hall_of_fame_normalizes_ws_prefixed_weapons(monkeypatch):
    db = _FakeDB(
        [
            ("mp40", "WS_MP40", "guid-1", "PlayerOne", 245, 60, 900, 500, 55.5),
        ]
    )

    async def _resolve_display_name(_db, _guid, fallback):
        return fallback

    monkeypatch.setattr(api_router, "resolve_display_name", _resolve_display_name)

    payload = await api_router.get_weapon_hall_of_fame(period="all", db=db)

    assert "leaders" in payload
    assert "mp40" in payload["leaders"]
    assert payload["leaders"]["mp40"]["weapon"] == "Mp40"
    assert "REPLACE(REPLACE(LOWER(weapon_name), 'ws_', ''), ' ', '')" in db.last_query


@pytest.mark.asyncio
async def test_get_weapon_stats_by_player_groups_by_guid_and_limits():
    db = _FakeDB(
        [
            ("guid-1", "Alpha", "WS_MP40", 100, 25, 400, 220, 55.0),
            ("guid-1", "Alpha", "WS_THOMPSON", 80, 18, 350, 190, 54.2),
            ("guid-2", "Bravo", "WS_LUGER", 30, 9, 140, 70, 50.0),
        ]
    )

    payload = await api_router.get_weapon_stats_by_player(
        period="all",
        player_limit=1,
        weapon_limit=1,
        db=db,
    )

    assert payload["player_count"] == 1
    assert len(payload["players"]) == 1
    top_player = payload["players"][0]
    assert top_player["player_guid"] == "guid-1"
    assert top_player["total_kills"] == 180
    assert len(top_player["weapons"]) == 1
    assert top_player["weapons"][0]["weapon_key"] == "mp40"
