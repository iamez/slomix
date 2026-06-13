"""Unit tests for season awards computation (S4-B)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services import season_awards_service as S
from website.backend.services.season_awards_service import (
    _compute_iron_man,
    _compute_most_improved,
    _compute_mvp,
    _compute_oracle,
    compute_and_store,
)


@pytest.mark.asyncio
async def test_mvp_none_without_sessions():
    assert await _compute_mvp(AsyncMock(), []) is None


@pytest.mark.asyncio
async def test_mvp_picks_top_voted():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[("GUID_A", 5)])
    db.fetch_one = AsyncMock(return_value=("Alice",))
    res = await _compute_mvp(db, [1, 2, 3])
    assert res["award_key"] == "mvp"
    assert res["player_guid"] == "GUID_A"
    assert res["player_name"] == "Alice"
    assert res["value_num"] == 5


@pytest.mark.asyncio
async def test_iron_man_most_sessions():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[("GUID_B", "Bob", 12)])
    res = await _compute_iron_man(db, "2026-04-01", "2026-06-30")
    assert res["award_key"] == "iron_man"
    assert res["value_num"] == 12
    assert "12 sessions" in res["value_text"]


@pytest.mark.asyncio
async def test_most_improved_picks_largest_positive_delta():
    db = AsyncMock()
    # GUID_C: 100 -> 200 (delta +100); GUID_D: 150 -> 160 (+10); GUID_E: 1 session (skip)
    db.fetch_all = AsyncMock(return_value=[
        ("GUID_C", "Cara", 1, 100.0),
        ("GUID_C", "Cara", 2, 200.0),
        ("GUID_D", "Dave", 1, 150.0),
        ("GUID_D", "Dave", 2, 160.0),
        ("GUID_E", "Eve", 1, 300.0),
    ])
    res = await _compute_most_improved(db, "2026-04-01", "2026-06-30")
    assert res["player_guid"] == "GUID_C"
    assert res["value_num"] == 100.0
    assert "207" not in res["value_text"]  # uses real values


@pytest.mark.asyncio
async def test_most_improved_skips_when_no_gain():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        ("GUID_X", "X", 1, 200.0),
        ("GUID_X", "X", 2, 100.0),  # regressed
    ])
    assert await _compute_most_improved(db, "2026-04-01", "2026-06-30") is None


@pytest.mark.asyncio
async def test_most_improved_requires_two_sessions():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[("GUID_Y", "Y", 1, 250.0)])
    assert await _compute_most_improved(db, "2026-04-01", "2026-06-30") is None


@pytest.mark.asyncio
async def test_oracle_maps_winner_to_linked_player():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[(555, 90)])  # user 555 net +90
    db.fetch_one = AsyncMock(return_value=("GUID_Z", "Zoe"))
    res = await _compute_oracle(db, [1, 2])
    assert res["award_key"] == "oracle"
    assert res["player_guid"] == "GUID_Z"
    assert res["value_num"] == 90


@pytest.mark.asyncio
async def test_oracle_skips_unlinked_or_nonpositive():
    db = AsyncMock()
    # negative net -> skip
    db.fetch_all = AsyncMock(return_value=[(555, -10)])
    assert await _compute_oracle(db, [1]) is None
    # positive but no link -> skip
    db.fetch_all = AsyncMock(return_value=[(555, 50)])
    db.fetch_one = AsyncMock(return_value=None)
    assert await _compute_oracle(db, [1]) is None


@pytest.mark.asyncio
async def test_compute_and_store_deletes_then_inserts(monkeypatch):
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[(7,)])  # one season session id

    async def _fake_iron(_db, _s, _e):
        return {"award_key": "iron_man", "player_guid": "G", "player_name": "N",
                "value_text": "3 sessions", "value_num": 3, "source": {"sessions": 3}}

    monkeypatch.setattr(S, "_compute_mvp", AsyncMock(return_value=None))
    monkeypatch.setattr(S, "_compute_iron_man", _fake_iron)
    monkeypatch.setattr(S, "_compute_most_improved", AsyncMock(return_value=None))
    monkeypatch.setattr(S, "_compute_oracle", AsyncMock(return_value=None))

    res = await compute_and_store(db, "2026-Q2", 42)
    assert res["season_id"] == "2026-Q2"
    assert len(res["awards"]) == 1
    statements = [c.args[0] for c in db.execute.await_args_list]
    assert any("DELETE FROM season_awards" in s for s in statements)
    assert any("INSERT INTO season_awards" in s for s in statements)
