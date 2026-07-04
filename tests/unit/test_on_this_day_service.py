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
async def test_two_sessions_same_date_render_separately():
    """W1 grain fix: two gaming sessions on one historical date must appear as
    two separate fields (per-gsid rows), not a merged score nobody played."""
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        (datetime.date(2025, 6, 14), 4, "puran", "sWat", 3, 1),
        (datetime.date(2025, 6, 14), 2, "kava", "mix", 0, 2),
    ])
    db.fetch_one = AsyncMock(return_value=None)
    svc = OnThisDayService(bot=None, db_adapter=db, config=_Cfg())
    embed = await svc.build_embed(datetime.date(2026, 6, 14))
    assert embed is not None
    field_text = " ".join(f.name + " " + str(f.value) for f in embed.fields)
    assert "puran 3–1 sWat" in field_text
    assert "kava 0–2 mix" in field_text
    query = db.fetch_all.call_args.args[0]
    assert "GROUP BY gaming_session_id" in query


@pytest.mark.asyncio
async def test_top_fragger_query_excludes_match_summary_rows():
    """round_number=0 rows are cumulative map summaries; counting them roughly
    doubles the kill total (codex P2 round 3, PR #434)."""
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        (datetime.date(2025, 6, 14), 2, "puran", "sWat", 1, 1),
    ])
    db.fetch_one = AsyncMock(return_value=None)
    svc = OnThisDayService(bot=None, db_adapter=db, config=_Cfg())
    await svc.build_embed(datetime.date(2026, 6, 14))
    fragger_query = db.fetch_one.call_args.args[0]
    assert "round_number IN (1, 2)" in fragger_query


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
