"""Unit tests for weekly challenges (S3-B)."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers.challenges_router import (
    _week_start,
    get_current_challenge,
    upsert_challenge,
)


def _req():
    r = MagicMock()
    r.headers = {"x-requested-with": "XMLHttpRequest"}
    return r


def test_week_start_is_monday():
    # 2026-06-13 is a Saturday -> Monday is 2026-06-08
    assert _week_start(date(2026, 6, 13)) == date(2026, 6, 8)
    assert _week_start(date(2026, 6, 8)) == date(2026, 6, 8)  # Monday stays


@pytest.mark.asyncio
async def test_current_challenge_none():
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=None)
    res = await get_current_challenge(db=db)
    assert res["challenge"] is None


@pytest.mark.asyncio
async def test_upsert_normalizes_week_and_passes_monday():
    db = AsyncMock()
    res = await upsert_challenge(
        _req(),
        {"title": "Knife only", "description": "most knife kills", "week_start_date": "2026-06-13"},
        user={"id": "7"}, db=db,
    )
    assert res["week_start_date"] == "2026-06-08"  # Saturday -> Monday
    # the INSERT bound the Monday date + creator id
    args = db.execute.call_args[0][1]
    assert args[0] == date(2026, 6, 8) and args[3] == 7


@pytest.mark.asyncio
async def test_upsert_requires_csrf():
    req = _req()
    req.headers = {}
    with pytest.raises(HTTPException) as e:
        await upsert_challenge(req, {"title": "x"}, user={"id": "7"}, db=AsyncMock())
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_upsert_validates_title():
    with pytest.raises(HTTPException):
        await upsert_challenge(_req(), {"title": ""}, user={"id": "7"}, db=AsyncMock())
    with pytest.raises(HTTPException):
        await upsert_challenge(_req(), {"title": "x" * 81}, user={"id": "7"}, db=AsyncMock())
