"""Tests for RoundCorrelationService._recalculate_completeness.

The completeness percentage feeds:
- The /diagnostics dashboard (operators trust the % to spot regressions)
- The status='complete' flag that downstream KIS/momentum/BOX consume
- The Phase 6 saga timeout filter (stale 'pending' rows aged 6h)

If the weighting drifts silently, every consumer is wrong. Lock the
contract here.
"""
from __future__ import annotations

import pytest

from bot.services.round_correlation_service import RoundCorrelationService


class _CompletenessFakeDb:
    def __init__(self, flags_row):
        self.flags_row = flags_row
        self.executed: list[tuple[str, tuple]] = []

    async def fetch_one(self, query, params=None):
        if "FROM round_correlations" in str(query):
            return self.flags_row
        return None

    async def fetch_all(self, query, params=None):
        return []

    async def execute(self, query, params=None, *extra):
        self.executed.append((str(query), params))
        return "UPDATE 1"


def _flags(**kw):
    """10-tuple in column order:
       has_r1_stats, has_r2_stats, has_r1_lua, has_r2_lua,
       has_r1_gt, has_r2_gt, has_r1_es, has_r2_es,
       has_r1_prox, has_r2_prox
    """
    keys = [
        "has_r1_stats", "has_r2_stats",
        "has_r1_lua", "has_r2_lua",
        "has_r1_gt", "has_r2_gt",
        "has_r1_es", "has_r2_es",
        "has_r1_prox", "has_r2_prox",
    ]
    return tuple(kw.get(k, False) for k in keys)


def _make_svc(db):
    svc = RoundCorrelationService(
        db, dry_run=False, require_schema_check=False, write_error_threshold=5,
    )
    svc._initialized = True
    svc.preflight_ok = True
    return svc


def _extract_update_pct_status(executed):
    """Find the status/completeness UPDATE row and return (status, pct)."""
    for q, p in executed:
        if "completeness_pct" in q and "UPDATE round_correlations" in q:
            # params order matches SQL: (status, pct, ...) or (status, pct, completed_at, ...)
            return p[0], p[1]
    return None, None


@pytest.mark.asyncio
async def test_full_data_is_100_complete():
    """Every flag set → 25+25+10+10+5+5+10+10+5+5 = 110 → capped to 100."""
    db = _CompletenessFakeDb(_flags(
        has_r1_stats=True, has_r2_stats=True,
        has_r1_lua=True, has_r2_lua=True,
        has_r1_gt=True, has_r2_gt=True,
        has_r1_es=True, has_r2_es=True,
        has_r1_prox=True, has_r2_prox=True,
    ))
    svc = _make_svc(db)
    await svc._recalculate_completeness("cid-1")
    status, pct = _extract_update_pct_status(db.executed)
    assert status == "complete"
    assert pct == 100


@pytest.mark.asyncio
async def test_only_stats_50_pct_complete():
    """R1+R2 stats only = 50 % and status='complete' (stats is the
    completion-defining axis)."""
    db = _CompletenessFakeDb(_flags(has_r1_stats=True, has_r2_stats=True))
    svc = _make_svc(db)
    await svc._recalculate_completeness("cid-1")
    status, pct = _extract_update_pct_status(db.executed)
    assert status == "complete"
    assert pct == 50


@pytest.mark.asyncio
async def test_only_r1_stats_is_partial_25_pct():
    db = _CompletenessFakeDb(_flags(has_r1_stats=True))
    svc = _make_svc(db)
    await svc._recalculate_completeness("cid-1")
    status, pct = _extract_update_pct_status(db.executed)
    assert status == "partial"
    assert pct == 25


@pytest.mark.asyncio
async def test_only_lua_no_stats_is_pending():
    """Lua data without any stats → status='pending' even though pct > 0.

    This is the load-bearing case for the Phase 6 saga timeout: pending
    rows older than 6h are marked 'incomplete' regardless of pct.
    """
    db = _CompletenessFakeDb(_flags(has_r1_lua=True, has_r2_lua=True))
    svc = _make_svc(db)
    await svc._recalculate_completeness("cid-1")
    status, pct = _extract_update_pct_status(db.executed)
    assert status == "pending"
    assert pct == 20  # 10 + 10


@pytest.mark.asyncio
async def test_no_flags_set_is_zero_pct_pending():
    db = _CompletenessFakeDb(_flags())
    svc = _make_svc(db)
    await svc._recalculate_completeness("cid-1")
    status, pct = _extract_update_pct_status(db.executed)
    assert status == "pending"
    assert pct == 0


@pytest.mark.asyncio
async def test_complete_status_writes_completed_at():
    """When transitioning to 'complete', completed_at is populated."""
    db = _CompletenessFakeDb(_flags(has_r1_stats=True, has_r2_stats=True))
    svc = _make_svc(db)
    await svc._recalculate_completeness("cid-1")
    update_calls = [(q, p) for q, p in db.executed if "completeness_pct" in q]
    assert update_calls
    q, p = update_calls[0]
    assert "completed_at" in q
    # completed_at is a datetime in params (3rd entry)
    assert p[2] is not None


@pytest.mark.asyncio
async def test_partial_status_does_not_write_completed_at():
    """Partial → completed_at intentionally omitted from UPDATE."""
    db = _CompletenessFakeDb(_flags(has_r1_stats=True))
    svc = _make_svc(db)
    await svc._recalculate_completeness("cid-1")
    update_calls = [(q, p) for q, p in db.executed if "completeness_pct" in q]
    assert update_calls
    q, _ = update_calls[0]
    assert "completed_at" not in q


@pytest.mark.asyncio
async def test_missing_correlation_row_is_noop():
    """If the row was deleted between scheduler and recalc, we no-op."""
    db = _CompletenessFakeDb(flags_row=None)
    svc = _make_svc(db)
    await svc._recalculate_completeness("does-not-exist")
    assert db.executed == []


@pytest.mark.asyncio
async def test_endstats_alone_uses_correct_weights():
    """Endstats are 10% each (R1 + R2 = 20%). Pin the weighting."""
    db = _CompletenessFakeDb(_flags(has_r1_es=True, has_r2_es=True))
    svc = _make_svc(db)
    await svc._recalculate_completeness("cid-1")
    _, pct = _extract_update_pct_status(db.executed)
    assert pct == 20  # 10 + 10


@pytest.mark.asyncio
async def test_proximity_alone_uses_correct_weights():
    """Proximity flags are 5% each (R1 + R2 = 10%). Pin the weighting."""
    db = _CompletenessFakeDb(_flags(has_r1_prox=True, has_r2_prox=True))
    svc = _make_svc(db)
    await svc._recalculate_completeness("cid-1")
    _, pct = _extract_update_pct_status(db.executed)
    assert pct == 10  # 5 + 5
