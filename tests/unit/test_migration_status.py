"""Unit tests for the startup migration-drift guard (shared/migration_status.py).

Prevention for the 2026-07-24 schema drift: a git-checkout deploy applies no
migrations, and the gap only surfaced as an UndefinedColumn 500 at request time.
The guard reads schema_migrations vs migrations/*.sql at startup and warns on
pending / failed / checksum-mismatch / missing-file / empty-dir drift.
"""
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from shared import migration_status  # noqa: E402
from shared.migration_status import (  # noqa: E402
    _discover_paths,
    get_migration_drift,
    get_pending_migrations,
    warn_if_pending_migrations,
)


def _fake_db(applied=None, failed=None):
    """A db whose fetch_all returns (filename, checksum, success) rows.

    applied: list of names (checksum None) or {name: checksum} → success=TRUE.
    failed:  list of names → success=FALSE.
    """
    rows = []
    if isinstance(applied, dict):
        rows += [(f, c, True) for f, c in applied.items()]
    elif applied:
        rows += [(f, None, True) for f in applied]
    if failed:
        rows += [(f, None, False) for f in failed]
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=rows)
    return db


def _names():
    return sorted(_discover_paths())


@pytest.mark.asyncio
async def test_pending_is_disk_minus_recorded():
    names = _names()
    assert names, "expected migrations/*.sql to be discoverable"
    db = _fake_db(names[:-1])  # everything applied except the last
    assert await get_pending_migrations(db) == [names[-1]]


@pytest.mark.asyncio
async def test_no_pending_when_all_recorded():
    assert await get_pending_migrations(_fake_db(_names())) == []


@pytest.mark.asyncio
async def test_failed_row_is_not_applied_and_not_pending(caplog):
    """A failed ledger row (success=FALSE) is neither applied nor 'pending'
    (never-attempted) — it is surfaced in its own `failed` bucket (Codex #545)."""
    names = _names()
    db = _fake_db(applied=names[:-1], failed=[names[-1]])
    drift = await get_migration_drift(db)
    assert drift["pending"] == []          # it WAS attempted
    assert drift["failed"] == [names[-1]]  # ...and it failed
    with caplog.at_level(logging.ERROR):
        await warn_if_pending_migrations(_fake_db(applied=names[:-1], failed=[names[-1]]),
                                         logging.getLogger("t"), "web")
    assert any("failed" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_checksum_mismatch_surfaced(caplog):
    """An applied migration whose file was edited (stored checksum != on-disk)
    is flagged, not silently reported clean (Codex #545)."""
    names = _names()
    recorded = dict.fromkeys(names, "applied-ok")
    recorded[names[0]] = "0" * 64  # wrong stored checksum → mismatch on disk
    drift = await get_migration_drift(_fake_db(recorded))
    assert drift["pending"] == []
    assert names[0] in drift["checksum_mismatch"]
    with caplog.at_level(logging.ERROR):
        await warn_if_pending_migrations(_fake_db(recorded), logging.getLogger("t"), "web")
    assert any("checksum-mismatch" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_missing_ledger_file_surfaced(caplog):
    """A ledger row (applied) whose .sql is gone from disk is flagged (#545)."""
    recorded = dict.fromkeys(_names(), "ok")
    recorded["999_ghost_migration.sql"] = "ok"  # applied but not on disk
    drift = await get_migration_drift(_fake_db(recorded))
    assert drift["missing_file"] == ["999_ghost_migration.sql"]
    with caplog.at_level(logging.ERROR):
        await warn_if_pending_migrations(_fake_db(recorded), logging.getLogger("t"), "web")
    assert any("missing-file" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_empty_discovery_warns_not_clean(caplog, monkeypatch):
    """No discoverable migration files (e.g. Docker strips *.sql) must warn,
    NOT read as 'up to date' (Codex #545)."""
    monkeypatch.setattr(migration_status, "_discover_paths", lambda: {})
    with caplog.at_level(logging.WARNING):
        result = await warn_if_pending_migrations(_fake_db([]), logging.getLogger("t"), "web")
    assert result == []
    assert any("no migration files discoverable" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_warn_logs_error_and_returns_pending(caplog):
    names = _names()
    db = _fake_db(names[:-1])
    with caplog.at_level(logging.ERROR):
        pending = await warn_if_pending_migrations(db, logging.getLogger("t"), "web")
    assert pending == [names[-1]]
    assert any("MIGRATION DRIFT" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_guard_never_raises_on_db_failure(caplog):
    """A missing schema_migrations table (fresh DB) must not block startup, and
    the guard must NOT fail silently — it warns that it could not run (#545)."""
    db = AsyncMock()
    db.fetch_all = AsyncMock(side_effect=RuntimeError("relation does not exist"))
    with caplog.at_level(logging.WARNING):
        result = await warn_if_pending_migrations(db, logging.getLogger("t"), "bot")
    assert result == []  # non-fatal
    assert any("could NOT run" in r.message for r in caplog.records)
