"""Unit tests for the Life Cards endpoint (Good Night plan rank 9).

The kills-per-life ranking lives in SQL; these cover the Python transform —
colour stripping, life-seconds rounding, narrative construction, and the
date-guard — with a fake DB so no Postgres is needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers.storytelling_router import get_best_lives


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows
        self.calls = 0

    async def fetch_all(self, query, params=()):
        self.calls += 1
        return self._rows


def _row(**kw):
    base = {"guid": "ABC12345", "name": "^1.lgz", "map_name": "etl_sp_delivery",
            "round_number": 2, "life_ms": 59000, "kills": 8}
    base.update(kw)
    return base


@pytest.mark.asyncio
async def test_builds_life_cards():
    db = _FakeDB([_row(), _row(name="qmr", kills=7, life_ms=158000,
                                map_name="sw_goldrush_te", guid="DEF")])
    out = await get_best_lives(request=None, session_date="2026-07-13", limit=5, db=db)
    assert out["status"] == "ok"
    assert out["total"] == 2
    first = out["lives"][0]
    assert first["name"] == ".lgz"          # ET colour codes stripped
    assert first["kills"] == 8
    assert first["life_seconds"] == 59        # 59000ms -> 59s
    assert first["guid"] == "ABC12345"
    assert "8 kills in one life (59s)" in first["narrative"]
    assert "etl sp delivery" in first["narrative"]  # underscores humanised


@pytest.mark.asyncio
async def test_empty_session():
    db = _FakeDB([])
    out = await get_best_lives(request=None, session_date="2026-07-13", limit=5, db=db)
    assert out["total"] == 0
    assert out["lives"] == []


@pytest.mark.asyncio
async def test_rounds_life_seconds():
    db = _FakeDB([_row(life_ms=59600)])  # 59.6s -> rounds to 60
    out = await get_best_lives(request=None, session_date="2026-07-13", limit=5, db=db)
    assert out["lives"][0]["life_seconds"] == 60


@pytest.mark.asyncio
async def test_bad_date_rejected():
    db = _FakeDB([])
    with pytest.raises(Exception) as exc:  # HTTPException from _parse_date
        await get_best_lives(request=None, session_date="not-a-date", limit=5, db=db)
    assert getattr(exc.value, "status_code", None) == 400
    assert db.calls == 0  # never reached the query


@pytest.mark.asyncio
async def test_missing_name_falls_back_to_guid():
    db = _FakeDB([_row(name=None, guid="DEADBEEF00")])
    out = await get_best_lives(request=None, session_date="2026-07-13", limit=5, db=db)
    assert out["lives"][0]["name"] == "DEADBEEF"  # guid[:8]
