"""Unit tests for the On This Day throwback service (S6 SPOMIN)."""
from __future__ import annotations

import datetime
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from bot.services.on_this_day_service import OnThisDayService


class _Cfg:
    on_this_day_channel_id = 0
    stats_channel_id = 0
    website_public_base = "https://www.slomix.fyi"


@pytest.mark.asyncio
async def test_build_embed_none_when_no_history():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[])
    svc = OnThisDayService(bot=None, db_adapter=db, config=_Cfg())
    assert await svc.build_embed(datetime.date(2026, 6, 14)) is None


@pytest.mark.asyncio
async def test_build_embed_renders_history_and_fragger():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        (datetime.date(2025, 6, 14), 2, "puran", "sWat", 1, 1),
    ])
    db.fetch_one = AsyncMock(return_value=("vid", 88, datetime.date(2025, 6, 14)))
    svc = OnThisDayService(bot=None, db_adapter=db, config=_Cfg())
    embed = await svc.build_embed(datetime.date(2026, 6, 14))
    assert embed is not None
    assert "On this day" in embed.title
    field_text = " ".join(f.name + " " + str(f.value) for f in embed.fields)
    assert "1 year ago" in field_text
    assert "puran 1–1 sWat" in field_text  # team score line
    assert "vid" in field_text and "88 kills" in field_text


@pytest.mark.asyncio
async def test_build_embed_survives_fragger_failure():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        (datetime.date(2024, 6, 14), 3, None, None, 0, 0),
    ])
    db.fetch_one = AsyncMock(side_effect=RuntimeError("boom"))
    svc = OnThisDayService(bot=None, db_adapter=db, config=_Cfg())
    embed = await svc.build_embed(datetime.date(2026, 6, 14))
    assert embed is not None  # history still renders; fragger is best-effort
    assert any("2 years ago" in f.name for f in embed.fields)
