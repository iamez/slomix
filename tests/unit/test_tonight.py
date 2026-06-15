"""Unit tests for the Tonight live hub endpoints (S7 LIVE)."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers import players_router as PR


@pytest.mark.asyncio
async def test_tonight_inactive_when_no_rows():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[])
    res = await PR.get_tonight(db)
    assert res["active"] is False
    assert res["maps"] == []


def _cols(map_name, rnum, winner, axis_p, allies_p, *, axis_sc, allies_sc,
          start, end, cap, gsid=None):
    """Build a row matching the tonight SQL column order."""
    return (map_name, rnum, winner, 0, axis_sc, allies_sc, axis_p, allies_p,
            start, end, cap, gsid)


@pytest.mark.asyncio
async def test_tonight_resolves_logical_teams_through_side_swap():
    """The core fix: score by LOGICAL TEAM, not Axis/Allies. In stopwatch the
    same team swaps sides every round, so a team that wins on Axis (R1) and on
    Allies (R2) must be credited as ONE team — never split across the side
    labels. Team A = whoever opened the night on Axis."""
    now = int(datetime.now(timezone.utc).timestamp())
    A = [{"guid": "AAA1", "name": "alice"}, {"guid": "AAA2", "name": "bob"}]
    B = [{"guid": "BBB1", "name": "carl"}, {"guid": "BBB2", "name": "dave"}]
    # Team A wins all four rounds despite swapping sides each round.
    # Map 1 (odd): R1 A=Axis(wins→1), R2 A=Allies(wins→2)
    # Map 2 (even): R1 A=Allies(wins→2), R2 A=Axis(wins→1)
    tonight_rows = [
        _cols("etl_adlernest", 1, 1, A, B, axis_sc=1, allies_sc=0, start=now - 940, end=now - 640, cap=now - 600),
        _cols("etl_adlernest", 2, 2, B, A, axis_sc=0, allies_sc=1, start=now - 590, end=now - 300, cap=now - 500),
        _cols("supply", 1, 2, B, A, axis_sc=0, allies_sc=1, start=now - 290, end=now - 40, cap=now - 200),
        _cols("supply", 2, 1, A, B, axis_sc=1, allies_sc=0, start=now - 30, end=now - 5, cap=now - 10),
    ]
    holdprob_rows = [(120,), (180,), (240,), (300,)]
    db = AsyncMock()
    db.fetch_all = AsyncMock(side_effect=[tonight_rows, holdprob_rows])
    res = await PR.get_tonight(db)

    assert res["active"] is True
    assert res["current_map"] == "supply"
    # Rosters are clean + non-overlapping despite the swaps.
    assert res["teams"]["a"]["roster"] == ["alice", "bob"]
    assert res["teams"]["b"]["roster"] == ["carl", "dave"]
    # Team A swept: 2 maps, 4 rounds; Team B nothing — NOT 2 axis / 2 allies.
    s = res["score"]
    assert s["a_maps"] == 2 and s["b_maps"] == 0
    assert s["a_rounds"] == 4 and s["b_rounds"] == 0
    assert s["maps_completed"] == 2
    # Two completed maps, both won by team A (2 points each).
    assert len(res["maps"]) == 2
    assert all(m["winner"] == "a" and m["a_points"] == 2 for m in res["maps"])
    # Momentum ends with team A dominating.
    assert res["momentum"][-1]["a"] > 50
    assert res["hold_probability"]["map"] == "supply"
    # Current map complete (R1+R2 both in).
    assert res["current"]["round"] == 2 and res["current"]["r2_pending"] is False


@pytest.mark.asyncio
async def test_tonight_current_map_r2_chase():
    """When only R1 of the current map has landed, surface the R2 time-to-beat."""
    now = int(datetime.now(timezone.utc).timestamp())
    A = [{"guid": "AAA1", "name": "alice"}]
    B = [{"guid": "BBB1", "name": "carl"}]
    rows = [
        # complete map 1
        _cols("supply", 1, 1, A, B, axis_sc=1, allies_sc=0, start=now - 700, end=now - 400, cap=now - 600),
        _cols("supply", 2, 1, B, A, axis_sc=1, allies_sc=0, start=now - 390, end=now - 110, cap=now - 300),
        # map 2: only R1 played so far → R2 pending, attack must beat R1's 255s
        _cols("radar", 1, 1, A, B, axis_sc=1, allies_sc=0, start=now - 300, end=now - 45, cap=now - 20),
    ]
    db = AsyncMock()
    db.fetch_all = AsyncMock(side_effect=[rows, [(120,), (180,), (240,)]])
    res = await PR.get_tonight(db)
    cur = res["current"]
    assert cur["map"] == "radar" and cur["round"] == 1
    assert cur["r2_pending"] is True
    assert cur["beat_seconds"] == 255  # end-start of the radar R1


@pytest.mark.asyncio
async def test_hold_probability_curve_is_monotonic():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[(60,), (120,), (120,), (240,)])
    res = await PR.get_hold_probability("supply", db)
    pts = res["curve"]
    assert pts and pts[0]["p"] == 0.0  # at t=0 nothing completed
    ps = [p["p"] for p in pts]
    assert ps == sorted(ps)            # CDF: non-decreasing
    assert pts[-1]["p"] == 100.0       # all completed by the longest time


@pytest.mark.asyncio
async def test_hold_probability_empty_when_too_few():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[(60,), (120,)])  # < 3 samples
    res = await PR.get_hold_probability("rarely_played", db)
    assert res["curve"] == []
