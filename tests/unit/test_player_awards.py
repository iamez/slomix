"""Unit tests for the player career-awards endpoint (S5 IDENTITETA)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers import players_profile_router as P


@pytest.mark.asyncio
async def test_awards_404_when_player_unknown(monkeypatch):
    monkeypatch.setattr(P, "resolve_player_guid", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as e:
        await P.get_player_awards("ghost", AsyncMock())
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_awards_maps_labels_and_season_names(monkeypatch):
    monkeypatch.setattr(P, "resolve_player_guid", AsyncMock(return_value="D8423F90"))
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        ("2026-Q2", "iron_man", "16 sessions", 16.0),
        ("2026-Q1", "wooden_spoon", "last place", None),  # manual key → title-cased
    ])
    res = await P.get_player_awards("vid", db)
    assert res["status"] == "ok"
    assert res["guid"] == "D8423F90"
    awards = {a["award_key"]: a for a in res["awards"]}
    assert awards["iron_man"]["label"] == "Iron Man"
    assert awards["iron_man"]["value_text"] == "16 sessions"
    assert awards["wooden_spoon"]["label"] == "Wooden Spoon"  # fallback title-case
    # season_name resolved (non-empty) for both
    assert all(a["season_name"] for a in res["awards"])


@pytest.mark.asyncio
async def test_awards_empty_when_none(monkeypatch):
    monkeypatch.setattr(P, "resolve_player_guid", AsyncMock(return_value="ABC12345"))
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[])
    res = await P.get_player_awards("x", db)
    assert res["awards"] == []
