"""Tests for the correlation service ingest entry points.

Each "on_*_imported" method represents one of the five sources that
feed round_correlations (per the module docstring). They share three
contracts that must hold:

1. Round numbers outside (0, 1, 2) are silently ignored.
2. round_number=0 (match summary) → only attempts to link to an
   existing correlation; never creates one.
3. dry-run mode short-circuits the DB write path.

Pin those so a future refactor doesn't accidentally start creating
correlations from summary events or expand the accepted round-number
range.
"""
from __future__ import annotations

import re

import pytest

from bot.services.round_correlation_service import RoundCorrelationService


class _IngestFakeDb:
    """Captures executed queries so tests can assert which writes happened."""

    def __init__(self):
        self.executed: list[tuple[str, object]] = []
        self.fetch_one_responses: dict[str, object] = {}

    async def execute(self, query, params=None, *extra):
        q = re.sub(r"\s+", " ", str(query)).strip()
        self.executed.append((q, params))
        return "EXECUTE 1"

    async def fetch_one(self, query, params=None):
        q = re.sub(r"\s+", " ", str(query)).strip()
        for sub, resp in self.fetch_one_responses.items():
            if sub in q:
                return resp() if callable(resp) else resp
        return None

    async def fetch_all(self, query, params=None):
        return []


def _make_live_service(db, *, dry_run=False):
    svc = RoundCorrelationService(
        db,
        dry_run=dry_run,
        require_schema_check=False,
        write_error_threshold=5,
    )
    svc._initialized = True
    svc.preflight_ok = True
    return svc


def _writes_to(executed, table_or_clause):
    return [q for q, _ in executed if table_or_clause in q]


# ---------------------------------------------------------------------------
# on_round_imported: round_number guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_rn", [-1, 3, 5, 99, None])
async def test_on_round_imported_ignores_out_of_range_round_number(bad_rn):
    """round_number must be in {0, 1, 2}; anything else is silently dropped."""
    db = _IngestFakeDb()
    svc = _make_live_service(db)

    await svc.on_round_imported(
        match_id="2026-04-21-180000",
        round_number=bad_rn,
        round_id=42,
        map_name="supply",
    )

    assert db.executed == []


@pytest.mark.asyncio
async def test_on_round_imported_summary_only_links_existing_row():
    """round_number=0 → ONLY UPDATE existing correlation; never INSERT."""
    db = _IngestFakeDb()
    svc = _make_live_service(db)

    await svc.on_round_imported(
        match_id="2026-04-21-180000",
        round_number=0,
        round_id=999,
        map_name="supply",
    )

    inserts = _writes_to(db.executed, "INSERT INTO round_correlations")
    summary_updates = _writes_to(db.executed, "SET summary_round_id =")
    assert inserts == [], "summary path must not create new correlations"
    assert len(summary_updates) == 1


@pytest.mark.asyncio
async def test_on_round_imported_dry_run_writes_nothing_for_r1():
    """dry-run gate must short-circuit before any DB work for R1/R2."""
    db = _IngestFakeDb()
    svc = _make_live_service(db, dry_run=True)

    await svc.on_round_imported(
        match_id="2026-04-21-180000",
        round_number=1,
        round_id=42,
        map_name="supply",
    )

    assert db.executed == []


@pytest.mark.asyncio
async def test_on_round_imported_dry_run_blocks_summary_too():
    db = _IngestFakeDb()
    svc = _make_live_service(db, dry_run=True)

    await svc.on_round_imported(
        match_id="2026-04-21-180000",
        round_number=0,
        round_id=999,
        map_name="supply",
    )

    assert db.executed == []


# ---------------------------------------------------------------------------
# on_lua_teams_stored / on_endstats_processed / on_proximity_imported
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_rn", [-1, 3, 99])
async def test_on_lua_teams_stored_ignores_bad_round_number(bad_rn):
    db = _IngestFakeDb()
    svc = _make_live_service(db)

    await svc.on_lua_teams_stored(
        match_id="2026-04-21-180000",
        round_number=bad_rn,
        lua_teams_id=42,
        map_name="supply",
    )

    assert db.executed == []


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_rn", [-1, 3, 99])
async def test_on_proximity_imported_ignores_bad_round_number(bad_rn):
    db = _IngestFakeDb()
    svc = _make_live_service(db)

    await svc.on_proximity_imported(
        match_id="2026-04-21-180000",
        round_number=bad_rn,
        map_name="supply",
    )

    assert db.executed == []


@pytest.mark.asyncio
async def test_on_endstats_processed_ignores_bad_round_number():
    db = _IngestFakeDb()
    svc = _make_live_service(db)

    await svc.on_endstats_processed(
        match_id="2026-04-21-180000",
        round_number=99,
        map_name="supply",
    )

    assert db.executed == []


# ---------------------------------------------------------------------------
# _link_summary: error path doesn't crash
# ---------------------------------------------------------------------------


class _RaisingDb:
    async def execute(self, query, params=None, *extra):
        raise RuntimeError("simulated execute failure")

    async def fetch_one(self, query, params=None):
        return None

    async def fetch_all(self, query, params=None):
        return []


@pytest.mark.asyncio
async def test_link_summary_swallows_db_error_via_record_write_failure():
    """Any DB error during summary linking is logged + accounted for in
    write_error_count, never re-raised. Crashing here would abort the
    surrounding stats import."""
    db = _RaisingDb()
    svc = _make_live_service(db)

    # Should NOT raise
    await svc._link_summary("2026-04-21-180000", round_id=42)

    # Failure was recorded
    assert svc.write_error_count == 1
