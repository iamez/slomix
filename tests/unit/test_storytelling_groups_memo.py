"""Regression test for _build_player_groups per-instance memoization.

Audit finding F3: Story page fans out gravity/space/enabler/narratives
concurrently, each of which calls `_build_player_groups(sd)` via the
synergy mixin — without a memo, that's 3-4 identical PCS JOIN rounds
scans per request. This test pins the memo behaviour so the same
service instance hits the DB once per (session_date) regardless of how
many callers await the group map.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services.storytelling.service import StorytellingService


def _service_with_stub_db():
    db = AsyncMock()
    # Two rows: one R1 AXIS player + one R1 ALLIES player, simplest case.
    db.fetch_all.side_effect = lambda *a, **kw: _fixture_rows()
    return StorytellingService(db), db


def _fixture_rows():
    # columns: (player_guid, player_name, round_number, team, round_start_unix)
    return [
        ("GUID_A1", "alpha", 1, 1, 1_700_000_000),
        ("GUID_B1", "bravo", 1, 2, 1_700_000_000),
    ]


@pytest.mark.asyncio
async def test_memo_hits_db_once_across_repeated_calls():
    svc, db = _service_with_stub_db()
    sd = date(2026, 4, 21)

    a = await svc._build_player_groups(sd)
    b = await svc._build_player_groups(sd)
    c = await svc._build_player_groups(sd)

    assert a is b is c  # identity match — cached object returned
    assert db.fetch_all.await_count == 1


@pytest.mark.asyncio
async def test_memo_separates_by_session_date():
    svc, db = _service_with_stub_db()
    sd1 = date(2026, 4, 20)
    sd2 = date(2026, 4, 21)

    await svc._build_player_groups(sd1)
    await svc._build_player_groups(sd2)
    await svc._build_player_groups(sd1)  # sd1 cached, no new DB call

    assert db.fetch_all.await_count == 2


@pytest.mark.asyncio
async def test_uncached_helper_still_reachable():
    """The original logic stays exposed for subclasses that bypass the
    cache (e.g. diagnostics). Calling it directly still works and is
    what the memo wraps."""
    svc, db = _service_with_stub_db()
    sd = date(2026, 4, 21)

    first = await svc._build_player_groups_uncached(sd)
    second = await svc._build_player_groups_uncached(sd)

    # Not memoized — two separate DB calls.
    assert db.fetch_all.await_count == 2
    assert first == second  # same structure, not identity
