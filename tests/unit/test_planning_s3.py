"""Unit tests for S3 planning additions (greedy balance, ping guards)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers import planning as pl
from website.backend.routers.planning import _greedy_balance


def test_greedy_balance_minimizes_gap():
    a, b, gap = _greedy_balance([(1, 1.4), (2, 1.3), (3, 0.6), (4, 0.5)])
    # 1.4+0.5 == 1.3+0.6 -> perfect balance
    assert gap == 0.0
    assert sorted(a + b) == [1, 2, 3, 4]
    assert set(a).isdisjoint(b)


def test_greedy_balance_odd_count():
    a, b, gap = _greedy_balance([(1, 1.0), (2, 0.9), (3, 0.8)])
    assert len(a) + len(b) == 3
    assert abs(len(a) - len(b)) == 1  # 2 vs 1


def test_greedy_balance_single():
    a, b, gap = _greedy_balance([(7, 1.0)])
    assert a == [7] and b == []


@pytest.mark.asyncio
async def test_ping_requires_thread():
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=None)  # no planning session today
    req = MagicMock()
    req.headers = {"x-requested-with": "XMLHttpRequest"}
    req.session = {"user": {"id": "1"}}
    with pytest.raises(HTTPException) as e:
        await pl.ping_need_more(req, db=db)
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_balanced_teams_needs_two(monkeypatch):
    monkeypatch.setattr(pl, "_participants_for_date", AsyncMock(return_value=[
        {"user_id": 1, "display_name": "solo", "status": "LOOKING"},
    ]))
    req = MagicMock()
    req.session = {"user": {"id": "1"}}
    res = await pl.suggest_balanced_teams(req, db=AsyncMock())
    assert res["side_a"] == [] and "at least 2" in res["message"]


@pytest.mark.asyncio
async def test_balanced_teams_uses_ratings(monkeypatch):
    monkeypatch.setattr(pl, "_participants_for_date", AsyncMock(return_value=[
        {"user_id": 1, "display_name": "ace", "status": "LOOKING"},
        {"user_id": 2, "display_name": "mid", "status": "AVAILABLE"},
        {"user_id": 3, "display_name": "low", "status": "LOOKING"},
        {"user_id": 4, "display_name": "newb", "status": "AVAILABLE"},
    ]))
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[(1, 1.4), (2, 1.3), (3, 0.6), (4, 0.5)])
    req = MagicMock()
    req.session = {"user": {"id": "1"}}
    res = await pl.suggest_balanced_teams(req, db=db)
    assert res["rating_gap"] == 0.0
    assert sorted(res["side_a"] + res["side_b"]) == [1, 2, 3, 4]
    assert res["rated_count"] == 4
