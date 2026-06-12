"""Unit tests for /stats/session/{id}/verdicts (S1.4)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers.sessions_router import get_session_verdicts


def _row(guid, name, sid, kills, dpm):
    return (guid, name, sid, kills, dpm)


@pytest.mark.asyncio
async def test_verdict_percentile_and_labels():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        # current session 50
        _row("AAA", "ace", 50, 30, 500.0),
        _row("BBB", "rookie", 50, 5, 200.0),
        # AAA history: 4 sessions, tonight beats all -> 100th pct = Great
        _row("AAA", "ace", 49, 20, 300.0),
        _row("AAA", "ace", 48, 22, 350.0),
        _row("AAA", "ace", 47, 18, 280.0),
        _row("AAA", "ace", 46, 25, 400.0),
        # BBB history: only 2 sessions -> first_night (needs >=3)
        _row("BBB", "rookie", 49, 10, 250.0),
        _row("BBB", "rookie", 48, 12, 260.0),
    ])
    res = await get_session_verdicts(50, db=db)

    by = {p["guid"]: p for p in res["players"]}
    assert by["AAA"]["percentile"] == 100 and by["AAA"]["label"] == "Great"
    assert by["AAA"]["avg_dpm"] == 332.5
    assert by["BBB"]["first_night"] is True and by["BBB"]["label"] == "New"
    # sorted: rated before unrated
    assert res["players"][0]["guid"] == "AAA"


@pytest.mark.asyncio
async def test_verdict_label_bands():
    db = AsyncMock()
    # 10 history sessions with dpm 100..1000; tonight 450 -> 4/10 below = 40th pct = Average
    hist = [_row("AAA", "p", 40 - i, 10, 100.0 * (i + 1)) for i in range(10)]
    db.fetch_all = AsyncMock(return_value=[_row("AAA", "p", 50, 10, 450.0), *hist])
    res = await get_session_verdicts(50, db=db)
    p = res["players"][0]
    assert p["percentile"] == 40 and p["label"] == "Average"


@pytest.mark.asyncio
async def test_verdict_empty():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[])
    res = await get_session_verdicts(99, db=db)
    assert res["players"] == []
