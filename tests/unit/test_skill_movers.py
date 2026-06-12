"""Unit tests for /api/skill/movers (S1.2)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers.skill_router import get_movers


def _row(guid, name, sid, kills, dpm):
    return (guid, name, sid, kills, dpm)


@pytest.mark.asyncio
async def test_movers_vs_own_baseline_with_dedup_and_new():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        # latest session 124
        _row("AAA", "hot", 124, 30, 400.0),
        _row("BBB", "cold", 124, 10, 200.0),
        _row("CCC", "fresh", 124, 15, 300.0),   # no history -> new
        # history
        _row("AAA", "hot", 123, 20, 300.0),     # +33%
        _row("BBB", "cold", 123, 25, 320.0),    # -37.5%
    ])
    db.fetch_val = AsyncMock(return_value="2026-06-11")

    res = await get_movers(db=db)

    assert res["session_id"] == 124
    assert [m["name"] for m in res["movers_up"]] == ["hot"]
    assert res["movers_up"][0]["delta_pct"] == 33.3
    assert [m["name"] for m in res["movers_down"]] == ["cold"]
    assert [m["name"] for m in res["new_players"]] == ["fresh"]
    # nobody appears in both lists
    up = {m["guid"] for m in res["movers_up"]}
    down = {m["guid"] for m in res["movers_down"]}
    assert not (up & down)


@pytest.mark.asyncio
async def test_movers_empty_db():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[])
    res = await get_movers(db=db)
    assert res["session_id"] is None and res["movers_up"] == []
