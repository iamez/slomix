"""KIS cache-check must be scoped by formula_version, not just presence.

compute_session_kis() previously treated "any row exists for this
session_date" as fully computed and served it forever — after changing
KIS multipliers/logic, sessions already scored under the OLD formula kept
stale scores silently. Regression test for the fix (codex, PR #478
follow-up audit finding #9, migration 060).
"""
from __future__ import annotations

from datetime import date

import pytest

from website.backend.services.storytelling.kis import FORMULA_VERSION
from website.backend.services.storytelling.service import StorytellingService

SD = date(2026, 7, 8)


class _FakeDB:
    def __init__(self, existing_version: str | None):
        self._existing_version = existing_version
        self.count_query_params: tuple | None = None

    async def fetch_one(self, query, params=None):
        if "COUNT(*) FROM storytelling_kill_impact" in query:
            self.count_query_params = params
            if self._existing_version is None:
                return (0,)
            # simulate the DB only counting rows matching the queried
            # formula_version (params[1]) — a real WHERE clause would do
            # this filtering itself; the fake mirrors that behavior.
            requested_version = params[1] if params and len(params) > 1 else None
            return (5,) if requested_version == self._existing_version else (0,)
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

    # the cache-check query must pass FORMULA_VERSION as a bind param
    assert db.count_query_params is not None
    assert db.count_query_params[1] == FORMULA_VERSION
    # stale-version rows don't count as cached -> falls through to a real
    # recompute attempt (no kills in this fake -> "no_data", not "cached")
    assert result["status"] != "cached"


@pytest.mark.asyncio
async def test_cache_check_hits_when_version_matches():
    db = _FakeDB(existing_version=FORMULA_VERSION)
    result = await StorytellingService(db=db).compute_session_kis(SD)

    assert result == {"status": "cached", "kills_scored": 5}
