"""Player-card composite endpoint (SUPER LIVE 2.0 Val C).

Contract tests with a routed fake adapter: successful payload shape,
unknown-player 404, no-recent-rounds 404, small-sample percentile
withholding — plus the pure _percentile helper.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from website.backend.routers.players_profile_router import (
    _CARD_MIN_SUBJECT_ROUNDS,
    _percentile,
    get_player_card,
)


def test_percentile_basics():
    pool = [100.0, 200.0, 300.0, 400.0]
    assert _percentile(pool, 400.0) == 100
    assert _percentile(pool, 250.0) == 50
    assert _percentile(pool, 50.0) == 0
    assert _percentile([], 100.0) is None


def _pool_row(guid, rounds, kills=100, deaths=80, damage=30000,
              seconds=6000, revives=10, hs=20, dead_s=1200):
    return (guid, rounds, kills, deaths, damage, seconds, revives, hs, dead_s)


class _Db:
    """Routes queries by fragment, mirroring the endpoint's call order."""

    def __init__(self, *, guid="AAAA1111", subject_rounds=40):
        self.guid = guid
        self.subject_rounds = subject_rounds

    async def fetch_one(self, query, params=()):
        if "player_identity_links" in query or "player_guid" in query and "LIMIT 1" in query and "player_comprehensive_stats" not in query:
            return None
        if "player_skill_ratings" in query:
            return (0.75, "veteran", 100)
        if "COUNT(DISTINCT r.gaming_session_id)" in query:
            return (5000, 42)
        return None

    async def fetch_all(self, query, params=()):
        if "HAVING COUNT(*)" in query:
            return [
                _pool_row(self.guid, self.subject_rounds),
                _pool_row("BBBB2222", 60, kills=200, damage=50000),
                _pool_row("CCCC3333", 45, kills=50, damage=20000),
            ]
        if "gaming_session_id" in query and "LIMIT 10" in query:
            return [(148, 30000, 6000), (147, 28000, 6000)]
        return []


@pytest.fixture()
def resolve(monkeypatch):
    import website.backend.routers.players_profile_router as mod

    async def fake_resolve(db, identifier):
        return None if identifier == "ghost" else "AAAA1111"

    async def fake_name(db, guid, fallback):
        return "vid"
    monkeypatch.setattr(mod, "resolve_player_guid", fake_resolve)
    monkeypatch.setattr(mod, "resolve_display_name", fake_name)


@pytest.mark.asyncio
async def test_card_payload_contract(resolve):
    card = await get_player_card("vid", db=_Db())
    assert card["status"] == "ok"
    assert card["rating"] == {"value": 0.75, "tier": "veteran",
                              "games_rated": 100, "trend": None}
    assert card["form"]["rounds"] == 40
    assert card["small_sample"] is False
    assert all(v is not None for v in card["percentiles"].values())
    assert isinstance(card["archetype"], str) and card["archetype"]
    assert card["career"] == {"kills": 5000, "sessions": 42}
    assert len(card["sparkline_dpm"]) == 2


@pytest.mark.asyncio
async def test_unknown_player_is_404(resolve):
    with pytest.raises(HTTPException) as exc:
        await get_player_card("ghost", db=_Db())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_no_recent_rounds_is_404(resolve):
    class _Empty(_Db):
        async def fetch_all(self, query, params=()):
            if "HAVING COUNT(*)" in query:
                return [_pool_row("BBBB2222", 60)]  # subject absent
            return []
    with pytest.raises(HTTPException) as exc:
        await get_player_card("vid", db=_Empty())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_small_sample_withholds_percentiles(resolve):
    card = await get_player_card(
        "vid", db=_Db(subject_rounds=_CARD_MIN_SUBJECT_ROUNDS - 1))
    assert card["small_sample"] is True
    assert all(v is None for v in card["percentiles"].values())
    assert card["form"]["rounds"] == _CARD_MIN_SUBJECT_ROUNDS - 1
