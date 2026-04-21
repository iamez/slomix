"""Regression test for _build_player_groups per-instance memoization.

Audit finding F3: Story page fans out gravity/space/enabler/narratives
concurrently, each of which calls `_build_player_groups(sd)` via the
synergy mixin — without a memo, that's 3-4 identical PCS JOIN rounds
scans per request. This test pins the memo behaviour so the same
service instance hits the DB once per (session_date) regardless of how
many callers await the group map.
"""

from __future__ import annotations

import asyncio
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


# ---------------------------------------------------------------------------
# Regression for Copilot review on PR #128: under the proximity audit
# F3 memo the cache-miss path was racy — N concurrent awaiters for the
# same (sd) all checked `sd in cache` before any of them wrote, so the
# underlying PCS scan ran N times despite the memo. The follow-up in
# PR #131 added per-date `asyncio.Lock` so only the first waiter runs
# the scan; the rest pick up the cached value on a double-check.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_memo_is_concurrent_safe():
    """N parallel awaits of `_build_player_groups(sd)` for the same
    session_date collapse to exactly 1 DB scan, even when the calls
    fan out via asyncio.gather (Story page pattern).

    We slow the stub `fetch_all` with a short asyncio.sleep so every
    gathered coroutine has time to queue on the lock before the first
    one resolves — without the lock, all N would see an empty cache
    and each start their own scan."""

    db = AsyncMock()

    async def slow_fetch(*_args, **_kwargs):
        await asyncio.sleep(0.01)
        return _fixture_rows()

    db.fetch_all.side_effect = slow_fetch

    svc = StorytellingService(db)
    sd = date(2026, 4, 21)

    # 8 concurrent callers — representative of the Story page fan-out
    # (gravity + space-created + enabler + player-narratives + …).
    results = await asyncio.gather(*(svc._build_player_groups(sd) for _ in range(8)))

    assert db.fetch_all.await_count == 1
    # All coroutines see the same memoized object.
    first = results[0]
    for r in results[1:]:
        assert r is first
