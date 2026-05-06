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

    async def fetch_all(self, query, params=None):
        if self.raises:
            raise RuntimeError("simulated DB outage")
        q = re.sub(r"\s+", " ", str(query)).strip()
        if "GROUP BY status" in q:
            return self.counts_rows
        if "ORDER BY created_at DESC LIMIT 10" in q:
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
async def test_status_summary_includes_recent_correlations():
    db = _StatusFakeDb(
        counts_rows=[("complete", 1)],
        recent_rows=[
            ("cid-A", "2026-04-21-180000", "supply", "complete", 100, datetime(2026, 4, 21, 18)),
            ("cid-B", "2026-04-21-181500", "frostbite", "partial", 50, datetime(2026, 4, 21, 18, 15)),
        ],
    )
    svc = _make_svc(db)

    result = await svc.get_status_summary()

    assert len(result["recent"]) == 2
    # Order is whatever the DB returns; we don't enforce sort here
    cids = [r[0] for r in result["recent"]]
    assert "cid-A" in cids


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
