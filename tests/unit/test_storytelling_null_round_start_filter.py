"""Regression guards for the NULL round_start_unix bucket-corruption fix.

If a row in combat_engagement / player_track / proximity_kill_outcome has
NULL or 0 `round_start_unix`, grouping by that key conflates rows from
DIFFERENT rounds into bucket=0 and corrupts temporal/spatial analysis.
The fix is a SQL predicate (`round_start_unix IS NOT NULL AND > 0`) on
the queries inside the three affected `_AdvancedMetricsMixin` methods.

These tests pin the SQL filter so a future refactor that drops the
predicate fails loudly here instead of silently degrading metric quality.

See PR #210 (compute_space_created) and PR #228 (compute_enabler +
compute_lurker_profile) for the bug history.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services.storytelling_service import StorytellingService


def _captured_queries(svc: StorytellingService) -> list[str]:
    """Return the list of SQL strings that fetch_all was called with."""
    return [call.args[0] for call in svc.db.fetch_all.await_args_list]


def _has_filter(sql: str) -> bool:
    """Both halves of the round_start_unix guard must appear in the query."""
    return (
        "round_start_unix IS NOT NULL" in sql
        and "round_start_unix > 0" in sql
    )


@pytest.mark.asyncio
async def test_compute_space_created_filters_null_round_start() -> None:
    svc = StorytellingService(db=AsyncMock())
    # First fetch returns the kill rows; we make it empty so the function
    # short-circuits after the SQL is captured.
    svc.db.fetch_all = AsyncMock(return_value=[])

    await svc.compute_space_created("2026-05-01")

    assert any(_has_filter(q) for q in _captured_queries(svc)), (
        "compute_space_created must filter NULL/0 round_start_unix "
        "(see PR #210)"
    )


@pytest.mark.asyncio
async def test_compute_enabler_filters_null_round_start() -> None:
    svc = StorytellingService(db=AsyncMock())
    svc.db.fetch_all = AsyncMock(return_value=[])

    await svc.compute_enabler("2026-05-01")

    assert any(_has_filter(q) for q in _captured_queries(svc)), (
        "compute_enabler must filter NULL/0 round_start_unix (see PR #228)"
    )


@pytest.mark.asyncio
async def test_compute_lurker_profile_filters_null_round_start() -> None:
    svc = StorytellingService(db=AsyncMock())
    svc.db.fetch_all = AsyncMock(return_value=[])

    await svc.compute_lurker_profile("2026-05-01")

    assert any(_has_filter(q) for q in _captured_queries(svc)), (
        "compute_lurker_profile must filter NULL/0 round_start_unix "
        "(see PR #228)"
    )
