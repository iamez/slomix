"""Unit tests for the startup migration-drift guard (shared/migration_status.py).

Prevention for the 2026-07-24 schema drift: a git-checkout deploy applies no
migrations, and the gap only surfaced as an UndefinedColumn 500 at request time.
The guard reads schema_migrations vs migrations/*.sql at startup and warns.
"""
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from shared.migration_status import (  # noqa: E402
    _discover,
    get_pending_migrations,
    warn_if_pending_migrations,
)


def _fake_db(recorded_filenames):
    """A db whose fetch_all returns (filename,) rows for the given names."""
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[(f,) for f in recorded_filenames])
    return db


@pytest.mark.asyncio
async def test_pending_is_disk_minus_recorded():
    """A discovered file not recorded (applied or failed) is pending."""
    files = _discover()
    assert files, "expected migrations/*.sql to be discoverable"
    missing = files[-1]
    db = _fake_db(files[:-1])  # everything recorded except the last
    pending = await get_pending_migrations(db)
    assert pending == [missing]


@pytest.mark.asyncio
async def test_no_pending_when_all_recorded():
    db = _fake_db(_discover())
    assert await get_pending_migrations(db) == []


@pytest.mark.asyncio
async def test_only_successful_rows_count_as_applied():
    """A failed migration (success=FALSE) must be surfaced as pending, not
    hidden behind an 'up to date' report (Codex #545). The applied query must
    filter on success = TRUE so failed rows never fall into the applied set."""
    files = _discover()
    db = _fake_db(files)  # the query WHERE success=TRUE returns only applied rows
    await get_pending_migrations(db)
    sql = db.fetch_all.call_args.args[0]
    assert "success = TRUE" in sql
    # A file recorded ONLY as failed (i.e. absent from the success set) is pending.
    failed_only = _fake_db(files[:-1])  # last file not in the success set
    assert files[-1] in await get_pending_migrations(failed_only)


@pytest.mark.asyncio
async def test_warn_logs_error_and_returns_pending(caplog):
    files = _discover()
    db = _fake_db(files[:-1])
    with caplog.at_level(logging.ERROR):
        pending = await warn_if_pending_migrations(db, logging.getLogger("t"), "web")
    assert pending == [files[-1]]
    assert any("PENDING DB MIGRATION" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_guard_never_raises_on_db_failure(caplog):
    """A missing schema_migrations table (fresh DB) must not block startup, and
    the guard must NOT fail silently — it warns that it could not run (Copilot #545)."""
    db = AsyncMock()
    db.fetch_all = AsyncMock(side_effect=RuntimeError("relation does not exist"))
    with caplog.at_level(logging.WARNING):
        result = await warn_if_pending_migrations(db, logging.getLogger("t"), "bot")
    assert result == []  # non-fatal
    assert any("could NOT run" in r.message for r in caplog.records)
