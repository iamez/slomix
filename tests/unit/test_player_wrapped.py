"""Unit tests for the season Wrapped endpoint (S6 SPOMIN)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers import players_profile_router as P


@pytest.mark.asyncio
async def test_wrapped_empty_when_no_rounds(monkeypatch):
    monkeypatch.setattr(P, "resolve_player_guid", AsyncMock(return_value="ABC12345"))
    monkeypatch.setattr(P, "resolve_display_name", AsyncMock(return_value="vid"))
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=(0, 0, 0, 0, 0, 0))  # totals: 0 rounds
    res = await P.get_player_wrapped("vid", "current", db)
    assert res["cards"] == []
    assert res["player_name"] == "vid"


@pytest.mark.asyncio
async def test_wrapped_builds_cards(monkeypatch):
    monkeypatch.setattr(P, "resolve_player_guid", AsyncMock(return_value="ABC12345"))
    monkeypatch.setattr(P, "resolve_display_name", AsyncMock(return_value="vid"))
    db = AsyncMock()
    db.fetch_one = AsyncMock(side_effect=[
        (262, 2679, 2160, 248, 131, 313),          # totals
        ("te_escape2", 70, 49),                     # signature map
        ("WS_MP40", 1300),                          # top weapon
        (511, "te_escape2", "2026-05-31"),          # best round
        ("endekk", 90, 64),                         # best teammate
    ])
    res = await P.get_player_wrapped("vid", "current", db)
    labels = {c["label"]: c for c in res["cards"]}
    assert labels["Rounds played"]["value"] == "262"
    assert labels["Win rate"]["value"] == "53%"          # 131/248
    assert labels["Signature map"]["value"] == "te_escape2"
    assert labels["Weapon of choice"]["value"] == "WS_MP40"
    assert labels["Best teammate"]["value"] == "endekk"
    assert "DPM" in labels["Best round"]["value"]
    assert len(res["cards"]) == 8


@pytest.mark.asyncio
async def test_wrapped_404_unknown(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(P, "resolve_player_guid", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as e:
        await P.get_player_wrapped("ghost", "current", AsyncMock())
    assert e.value.status_code == 404
