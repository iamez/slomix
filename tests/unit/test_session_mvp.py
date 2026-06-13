"""Unit tests for session MVP voting (S3-A)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers import sessions_router as sr


def _req(user_id="42"):
    r = MagicMock()
    r.session = {"user": {"id": user_id}} if user_id else {}
    r.headers = {"x-requested-with": "XMLHttpRequest"}
    return r


POOL = [
    {"guid": "AAAA0001", "name": "ace", "kills": 40, "dpm": 400.0},
    {"guid": "BBBB0002", "name": "anchor", "kills": 12, "dpm": 180.0},
    {"guid": "CCCC0003", "name": "lurker", "kills": 8, "dpm": 150.0},
]


@pytest.mark.asyncio
async def test_mvp_get_tally_and_most_underrated(monkeypatch):
    db = AsyncMock()
    # tally: lurker has the most votes despite low kills
    monkeypatch.setattr(sr, "_session_player_pool", AsyncMock(return_value=POOL))
    monkeypatch.setattr(sr, "_mvp_tally", AsyncMock(return_value={"CCCC0003": 3, "AAAA0001": 1}))
    # KIS rank: ace #0 (top), lurker #2 (bottom) -> lurker is "underrated"
    db.fetch_val = AsyncMock(return_value="2026-06-11")
    db.fetch_all = AsyncMock(return_value=[("AAAA0001", 90.0), ("BBBB0002", 50.0), ("CCCC0003", 10.0)])
    db.fetch_one = AsyncMock(return_value=None)

    res = await sr.get_session_mvp(_req(), 50, db=db)

    assert res["total_votes"] == 4
    # candidates sorted by votes desc -> lurker first
    assert res["candidates"][0]["guid"] == "CCCC0003"
    assert res["candidates"][0]["vote_pct"] == 75.0
    assert res["most_underrated_guid"] == "CCCC0003"  # many votes, bottom KIS


@pytest.mark.asyncio
async def test_mvp_get_empty_pool(monkeypatch):
    monkeypatch.setattr(sr, "_session_player_pool", AsyncMock(return_value=[]))
    res = await sr.get_session_mvp(_req(), 99, db=AsyncMock())
    assert res["candidates"] == []


@pytest.mark.asyncio
async def test_mvp_post_rejects_non_participant(monkeypatch):
    monkeypatch.setattr(sr, "_session_player_pool", AsyncMock(return_value=POOL))
    with pytest.raises(HTTPException) as e:
        await sr.post_session_mvp(
            _req(), 50, {"nominated_guid": "ZZZZ9999"},
            user={"id": "42"}, db=AsyncMock(),
        )
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_mvp_post_requires_csrf(monkeypatch):
    monkeypatch.setattr(sr, "_session_player_pool", AsyncMock(return_value=POOL))
    req = _req()
    req.headers = {}  # no X-Requested-With
    with pytest.raises(HTTPException) as e:
        await sr.post_session_mvp(req, 50, {"nominated_guid": "AAAA0001"},
                                  user={"id": "42"}, db=AsyncMock())
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_mvp_post_one_changeable_vote(monkeypatch):
    monkeypatch.setattr(sr, "_session_player_pool", AsyncMock(return_value=POOL))
    monkeypatch.setattr(sr, "_mvp_tally", AsyncMock(return_value={"AAAA0001": 1}))
    db = AsyncMock()
    res = await sr.post_session_mvp(
        _req(), 50, {"nominated_guid": "AAAA0001"}, user={"id": "42"}, db=db,
    )
    # single atomic upsert (no delete-then-insert race window)
    assert db.execute.call_count == 1
    sql = db.execute.call_args[0][0]
    assert sql.strip().upper().startswith("INSERT") and "ON CONFLICT" in sql.upper()
    assert res["my_vote"] == "AAAA0001"


@pytest.mark.asyncio
async def test_mvp_post_missing_nominee(monkeypatch):
    monkeypatch.setattr(sr, "_session_player_pool", AsyncMock(return_value=POOL))
    with pytest.raises(HTTPException) as e:
        await sr.post_session_mvp(_req(), 50, {}, user={"id": "42"}, db=AsyncMock())
    assert e.value.status_code == 400
