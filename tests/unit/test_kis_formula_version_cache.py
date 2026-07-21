"""KIS cache-check must be scoped by formula_version AND freshness.

compute_session_kis() must serve the cache only when it is both:
- current-formula: rows scored under an OLD formula_version don't count as
  cached, so a version bump triggers recompute (codex PR #478 finding #9,
  migration 060); and
- fresh: if any KIS input (proximity context) landed AFTER the cached rows
  were written — a late re-import with the SAME formula_version — the cache
  is stale and must be recomputed rather than served forever (2026-07-09
  freshness fix; the class of staleness found across ~⅓ of prod sessions).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from website.backend.routers.storytelling_router import get_kis_formula
from website.backend.services.storytelling.kis import FORMULA_VERSION
from website.backend.services.storytelling.service import StorytellingService

SD = date(2026, 7, 8)
CACHE_TS = datetime(2026, 7, 9, 12, 0, 0)
OLDER = CACHE_TS - timedelta(hours=1)
NEWER = CACHE_TS + timedelta(hours=1)


class _FakeDB:
    """Models the two cache-check reads: the count+timestamp of the cached
    KIS rows, and the newest context (KIS input) timestamp."""

    def __init__(self, existing_version: str | None, *,
                 kis_ts: datetime | None = CACHE_TS,
                 ctx_ts: datetime | None = OLDER):
        self._existing_version = existing_version
        self._kis_ts = kis_ts
        self._ctx_ts = ctx_ts
        self.count_query_params: tuple | None = None
        self.freshness_checked = False

    async def fetch_one(self, query, params=None):
        if "storytelling_kill_impact" in query and "COUNT(*)" in query and "GREATEST" not in query:
            self.count_query_params = params
            if self._existing_version is None:
                return (0, None)
            requested_version = params[1] if params and len(params) > 1 else None
            if requested_version == self._existing_version:
                return (5, self._kis_ts)
            return (0, None)
        if "GREATEST" in query:
            self.freshness_checked = True
            return (self._ctx_ts,)
        return None

    async def fetch_all(self, query, params=None):
        return []

    async def execute(self, query, params=None):
        return None

    async def executemany(self, query, params_list):
        return None


@pytest.mark.asyncio
async def test_cache_check_filters_by_current_formula_version():
    """Rows exist, but under an OLD version — must NOT be served as cached."""
    db = _FakeDB(existing_version="kis-v1-old")
    result = await StorytellingService(db=db).compute_session_kis(SD)

    assert db.count_query_params is not None
    assert db.count_query_params[1] == FORMULA_VERSION
    assert result["status"] != "cached"


@pytest.mark.asyncio
async def test_cache_hit_when_context_older_than_cache():
    """Current formula AND context older than cache → served as cached."""
    db = _FakeDB(existing_version=FORMULA_VERSION, kis_ts=CACHE_TS, ctx_ts=OLDER)
    result = await StorytellingService(db=db).compute_session_kis(SD)

    assert db.freshness_checked is True  # freshness query actually ran
    assert result == {"status": "cached", "kills_scored": 5}


@pytest.mark.asyncio
async def test_cache_stale_when_context_newer_than_cache():
    """Context landed AFTER the cache (late re-import, same formula) → the
    cache is stale and must fall through to a recompute, not be served."""
    db = _FakeDB(existing_version=FORMULA_VERSION, kis_ts=CACHE_TS, ctx_ts=NEWER)
    result = await StorytellingService(db=db).compute_session_kis(SD)

    assert db.freshness_checked is True
    # no kills in this fake -> recompute path returns "no_data", not "cached"
    assert result["status"] != "cached"


@pytest.mark.asyncio
async def test_fresh_check_handles_null_context_ts():
    """No context timestamp (GREATEST → NULL) → nothing landed after the
    cache, so it's still fresh and served as cached."""
    db = _FakeDB(existing_version=FORMULA_VERSION, kis_ts=CACHE_TS, ctx_ts=None)
    result = await StorytellingService(db=db).compute_session_kis(SD)

    assert result == {"status": "cached", "kills_scored": 5}


@pytest.mark.asyncio
async def test_missing_cache_timestamp_forces_recompute():
    """Rows counted but no cache timestamp (can't prove freshness) → recompute
    rather than risk serving stale scores."""
    db = _FakeDB(existing_version=FORMULA_VERSION, kis_ts=None, ctx_ts=OLDER)
    result = await StorytellingService(db=db).compute_session_kis(SD)

    assert result["status"] != "cached"


@pytest.mark.asyncio
async def test_public_formula_endpoint_reports_same_version_used_for_cache():
    """`/storytelling/formula` (transparency endpoint) must report the SAME
    `version` string as `FORMULA_VERSION` — the identifier actually stored
    in `storytelling_kill_impact.formula_version` and compared for cache
    invalidation. Before Codex SS-E this was a disconnected hardcoded
    "1.0" that could drift from what was actually computed."""
    result = await get_kis_formula()

    assert result["version"] == FORMULA_VERSION
