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


@pytest.mark.asyncio
async def test_tonight_builds_strip_tally_and_momentum():
    now = int(datetime.now(timezone.utc).timestamp())
    # 4 rounds: adlernest R1(allies), R2(axis); supply R1(axis), R2(axis)
    tonight_rows = [
        ("etl_adlernest", 1, 0, 1, 2, now - 600),
        ("etl_adlernest", 2, 1, 0, 1, now - 500),
        ("supply", 1, 1, 0, 1, now - 200),
        ("supply", 2, 1, 0, 1, now - 10),   # last → recent → active
    ]
    holdprob_rows = [(120,), (180,), (240,), (300,)]
    db = AsyncMock()
    db.fetch_all = AsyncMock(side_effect=[tonight_rows, holdprob_rows])
    res = await PR.get_tonight(db)

    assert res["active"] is True
    assert res["current_map"] == "supply"
    assert len(res["maps"]) == 4
    assert res["maps"][0]["map"] == "etl_adlernest" and res["maps"][0]["round"] == 1
    t = res["tally"]
    assert t["axis_rounds"] == 3 and t["allies_rounds"] == 1
    assert t["maps_played"] == 2  # two R2 rows
    # momentum: ends with axis dominating (last 3 rounds axis) → axis > 50
    assert res["momentum"][-1]["axis"] > 50
    assert res["hold_probability"] is not None
    assert res["hold_probability"]["map"] == "supply"


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
