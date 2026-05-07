"""Tests for RoundCorrelationService.get_status_summary.

This is the data source for the !correlation_status admin command.
Operators rely on it for "what is the bot's correlation health?"
- counts by status (complete / partial / pending / incomplete)
- 10 most recent correlations for spot-checking
- live mode + guardrail diagnostics

Pin both the happy path and the error fallback so a noisy DB doesn't
blank the admin command and force a manual psql session to debug.
"""
from __future__ import annotations

import re
from datetime import datetime

import pytest

from bot.services.round_correlation_service import RoundCorrelationService


class _StatusFakeDb:
    def __init__(self, *, counts_rows=None, recent_rows=None, raises=False):
        self.counts_rows = counts_rows or []
        self.recent_rows = recent_rows or []
        self.raises = raises
        self.recent_query: str | None = None  # captured for query-shape asserts

    async def fetch_all(self, query, params=None):
        if self.raises:
            raise RuntimeError("simulated DB outage")
        q = re.sub(r"\s+", " ", str(query)).strip()
        if "GROUP BY status" in q:
            return self.counts_rows
        if "ORDER BY created_at DESC LIMIT 10" in q:
            self.recent_query = q
            return self.recent_rows
        return []

    async def fetch_one(self, query, params=None):
        return None

    async def execute(self, query, params=None, *extra):
        return "EXECUTE 0"


def _make_svc(db, *, dry_run=False, live_requested=True, guardrail_reason=None):
    svc = RoundCorrelationService(
        db,
        dry_run=dry_run,
        require_schema_check=False,
        write_error_threshold=5,
    )
    svc._initialized = True
    svc.preflight_ok = True
    svc.preflight_checked = True
    svc.live_requested = live_requested
    svc.guardrail_reason = guardrail_reason
    return svc


@pytest.mark.asyncio
async def test_status_summary_aggregates_counts_and_total():
    """Counts come back keyed by status, total is the sum across them."""
    db = _StatusFakeDb(counts_rows=[
        ("complete", 120),
        ("partial", 8),
        ("pending", 3),
    ])
    svc = _make_svc(db)

    result = await svc.get_status_summary()

    assert result["counts"] == {"complete": 120, "partial": 8, "pending": 3}
    assert result["total"] == 131


@pytest.mark.asyncio
async def test_status_summary_preserves_db_recency_order():
    """The result["recent"] must keep the DB-supplied order intact —
    the function relies on SQL's ORDER BY DESC for newest-first.

    Two halves:
    1. Sequence preservation: pass rows newest-first to the fake DB,
       assert they come out newest-first (no in-Python re-sorting that
       could silently break the contract).
    2. Query-shape: capture the SQL and assert it still contains the
       `ORDER BY created_at DESC` + `LIMIT 10` clauses. Without this,
       a future refactor that drops ORDER BY would still pass test #1
       (because the fake DB doesn't sort).
    """
    newer = ("cid-NEW", "2026-04-21-181500", "frostbite", "partial", 50, datetime(2026, 4, 21, 18, 15))
    older = ("cid-OLD", "2026-04-21-180000", "supply", "complete", 100, datetime(2026, 4, 21, 18, 0))
    db = _StatusFakeDb(
        counts_rows=[("complete", 1)],
        # Caller (production SQL) returns newest first → mirror that here
        recent_rows=[newer, older],
    )
    svc = _make_svc(db)

    result = await svc.get_status_summary()

    # 1. Sequence preserved (no in-memory re-sort)
    assert len(result["recent"]) == 2
    assert result["recent"][0][0] == "cid-NEW", "recency order must be preserved"
    assert result["recent"][1][0] == "cid-OLD"

    # 2. Query-shape contract — recency lives in SQL, must stay there
    assert db.recent_query is not None
    assert "ORDER BY created_at DESC" in db.recent_query
    assert "LIMIT 10" in db.recent_query


@pytest.mark.asyncio
async def test_status_summary_exposes_runtime_flags():
    """Mode + guardrail state must be visible to operators."""
    db = _StatusFakeDb(counts_rows=[])
    svc = _make_svc(db, dry_run=True, guardrail_reason="schema_preflight_table_missing")

    result = await svc.get_status_summary()

    assert result["dry_run"] is True
    assert result["live_requested"] is True
    assert result["guardrail_reason"] == "schema_preflight_table_missing"
    assert result["preflight_checked"] is True
    assert result["preflight_ok"] is True
    assert result["write_error_count"] == 0
    assert result["write_error_threshold"] == 5


@pytest.mark.asyncio
async def test_status_summary_fallback_on_db_error():
    """A DB outage must NOT crash the admin command — return zeroed
    counts but keep the runtime-flag block so operator still gets
    actionable info."""
    db = _StatusFakeDb(raises=True)
    svc = _make_svc(db, dry_run=True, guardrail_reason="write_error_threshold_reached")

    result = await svc.get_status_summary()

    assert result["counts"] == {}
    assert result["total"] == 0
    assert result["recent"] == []
    # Runtime flags must still be populated
    assert result["dry_run"] is True
    assert result["guardrail_reason"] == "write_error_threshold_reached"


@pytest.mark.asyncio
async def test_status_summary_empty_db_returns_zero_total():
    db = _StatusFakeDb(counts_rows=[], recent_rows=[])
    svc = _make_svc(db)

    result = await svc.get_status_summary()

    assert result["counts"] == {}
    assert result["total"] == 0
    assert result["recent"] == []
