"""Unit tests for /api/skill/movers (S1.2) + multi-metric form expansion."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers.skill_router import get_movers


def _row(guid, name, sid, kills, dpm, deaths=10, obj=0.0, acc=0.0):
    # Matches _form_rows SELECT order:
    # player_guid, player_name, gaming_session_id, kills, deaths, dpm, obj, acc
    return (guid, name, sid, kills, deaths, dpm, obj, acc)


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
    assert res["metric"] == "dpm"
    assert [m["name"] for m in res["movers_up"]] == ["hot"]
    assert res["movers_up"][0]["delta_pct"] == 33.3
    assert [m["name"] for m in res["movers_down"]] == ["cold"]
    assert [m["name"] for m in res["new_players"]] == ["fresh"]
    # series present (oldest→newest incl latest) for the sparkline
    assert res["movers_up"][0]["series"] == [300.0, 400.0]
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


@pytest.mark.asyncio
async def test_movers_metric_kd():
    # K/D metric: kills/deaths per session vs own baseline.
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        _row("AAA", "hot", 124, 20, 100.0, deaths=10),   # latest kd = 2.0
        _row("AAA", "hot", 123, 10, 100.0, deaths=10),   # hist kd = 1.0 -> +100%
    ])
    db.fetch_val = AsyncMock(return_value="2026-06-11")
    res = await get_movers(metric="kd", db=db)
    assert res["metric"] == "kd"
    assert res["movers_up"][0]["name"] == "hot"
    assert res["movers_up"][0]["delta_pct"] == 100.0
    assert res["movers_up"][0]["latest"] == 2.0


@pytest.mark.asyncio
async def test_movers_bad_metric_falls_back_to_dpm():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[])
    res = await get_movers(metric="not-a-metric", db=db)
    assert res["metric"] == "dpm"


@pytest.mark.asyncio
async def test_movers_full_returns_all_up_and_down():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        _row("A", "a", 124, 40, 400.0), _row("A", "a", 123, 20, 300.0),  # +33 up
        _row("B", "b", 124, 40, 410.0), _row("B", "b", 123, 20, 300.0),  # +37 up
        _row("C", "c", 124, 10, 100.0), _row("C", "c", 123, 20, 200.0),  # -50 down
        _row("D", "d", 124, 10, 120.0), _row("D", "d", 123, 20, 200.0),  # -40 down
    ])
    db.fetch_val = AsyncMock(return_value="2026-06-11")
    # top=1 but full=true → all movers returned, not capped
    res = await get_movers(top=1, full=True, db=db)
    assert len(res["movers_up"]) == 2
    assert len(res["movers_down"]) == 2
