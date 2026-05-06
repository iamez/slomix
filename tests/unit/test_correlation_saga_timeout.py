"""Phase 6 (saga timeout) regression tests for RoundCorrelationService.

Saga timeout marks pending correlations as 'incomplete' after 6 hours so
operators see actionable status instead of an unbounded pending pile.
This module pins the contract that:

- The UPDATE fires unconditionally each sweep cycle (idempotent — only
  rows older than 6h are touched).
- The log message reflects the actual update count (not the row count
  string format peculiarity of asyncpg).
- A failing saga UPDATE doesn't block the late-merge sweep that follows.

The 6-hour threshold lives in SQL (`INTERVAL '6 hours'`); these tests
cover behaviour, not the threshold value itself.
"""
from __future__ import annotations

import pytest

from bot.services.round_correlation_service import RoundCorrelationService


class _SweepFakeDb:
    """Just enough fake DB for `_sweep_once`.

    asyncpg's `execute()` returns the command tag string ("UPDATE 5",
    "UPDATE 0", etc.). We mirror that so the parsing logic in
    `_sweep_once` stays exercised.
    """

    def __init__(self, *, saga_tag="UPDATE 0", saga_raises=False, orphan_rows=None):
        self.saga_tag = saga_tag
        self.saga_raises = saga_raises
        self.orphan_rows = orphan_rows or []
        self.executed: list[tuple[str, object]] = []
        self.fetched: list[tuple[str, object]] = []

    async def execute(self, query, params=None, *extra):
        q = str(query)
        self.executed.append((q, params))
        if "SET status = 'incomplete'" in q:
            if self.saga_raises:
                raise RuntimeError("simulated saga UPDATE failure")
            return self.saga_tag
        return "UPDATE 0"

    async def fetch_all(self, query, params=None):
        q = str(query)
        self.fetched.append((q, params))
        if "WHERE status = 'pending'" in q and "r1_round_id IS NULL" in q:
            return self.orphan_rows
        return []

    async def fetch_one(self, query, params=None):
        return None


def _make_live_service(db):
    svc = RoundCorrelationService(
        db,
        dry_run=False,
        require_schema_check=False,
        write_error_threshold=5,
    )
    # Skip preflight — set live state directly to keep the test minimal.
    svc._initialized = True
    svc.preflight_ok = True
    return svc


@pytest.mark.asyncio
async def test_saga_timeout_update_fires_every_sweep(caplog):
    """Idempotent UPDATE runs every cycle; SQL filter handles the row count."""
    db = _SweepFakeDb(saga_tag="UPDATE 3")
    svc = _make_live_service(db)

    with caplog.at_level("WARNING"):
        await svc._sweep_once()

    saga_executes = [q for q, _ in db.executed if "SET status = 'incomplete'" in q]
    assert len(saga_executes) == 1
    assert "Saga timeout: marked 3 pending" in caplog.text


@pytest.mark.asyncio
async def test_saga_timeout_zero_rows_logs_nothing(caplog):
    """When no rows aged past 6h, we don't spam logs."""
    db = _SweepFakeDb(saga_tag="UPDATE 0")
    svc = _make_live_service(db)

    with caplog.at_level("WARNING"):
        await svc._sweep_once()

    assert "Saga timeout" not in caplog.text


@pytest.mark.asyncio
async def test_saga_timeout_failure_doesnt_break_sweep(caplog):
    """If saga UPDATE raises, late-merge fetch_all still runs."""
    db = _SweepFakeDb(saga_raises=True)
    svc = _make_live_service(db)

    with caplog.at_level("WARNING"):
        await svc._sweep_once()

    # Late-merge fetch ran despite the saga failure
    assert any("WHERE status = 'pending'" in q for q, _ in db.fetched)
    assert "saga timeout step failed" in caplog.text


@pytest.mark.asyncio
async def test_sweep_skipped_when_dry_run():
    """Dry-run mode short-circuits — no DB writes at all."""
    db = _SweepFakeDb(saga_tag="UPDATE 99")
    svc = RoundCorrelationService(
        db, dry_run=True, require_schema_check=False, write_error_threshold=5,
    )
    svc._initialized = True

    await svc._sweep_once()

    # No saga execute, no late-merge fetch
    assert not any("SET status = 'incomplete'" in q for q, _ in db.executed)
    assert not db.fetched


@pytest.mark.asyncio
async def test_close_reports_no_running_task_when_disabled():
    """close() returns False (nothing cancelled) when sweep was never started."""
    db = _SweepFakeDb()
    svc = _make_live_service(db)
    # Sweep never started → _sweep_task stays None
    assert svc._sweep_task is None
    cancelled = await svc.close()
    assert cancelled is False


@pytest.mark.asyncio
async def test_close_is_idempotent():
    """Calling close() twice is safe and second call is a no-op."""
    db = _SweepFakeDb()
    svc = _make_live_service(db)
    assert await svc.close() is False
    assert await svc.close() is False
