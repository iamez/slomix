"""Tests for FileRepository — processed-file data access layer.

Used at bot startup to populate the in-memory dedup cache. A regression
in either method:

- Returns wrong filenames → bot re-imports already-processed files →
  duplicate rounds in DB / inflated leaderboards.
- Swallows wrong exceptions → bot crashes during startup or skips
  the dedup cache entirely.
- Wrong WHERE clause (success/timestamp) → re-imports files that
  failed parsing the first time.

Pin the contract for both methods.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from bot.repositories.file_repository import FileRepository


class _FakeDb:
    """Captures the last query + params and returns canned rows."""
    def __init__(self, rows=None, raise_on_fetch=None):
        self.rows = rows or []
        self.raise_on_fetch = raise_on_fetch
        self.last_query = None
        self.last_params = None
        self.calls = 0

    async def fetch_all(self, query, params=None):
        self.calls += 1
        self.last_query = query
        self.last_params = params
        if self.raise_on_fetch:
            raise self.raise_on_fetch
        return self.rows


@pytest.fixture
def repo_factory():
    def _make(rows=None, raise_on_fetch=None):
        db = _FakeDb(rows=rows, raise_on_fetch=raise_on_fetch)
        return FileRepository(db_adapter=db, config=None), db
    return _make


# ---------------------------------------------------------------------------
# get_processed_filenames — full startup load
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_processed_returns_set_of_filenames(repo_factory):
    repo, _ = repo_factory(rows=[("a.txt",), ("b.txt",), ("c.txt",)])
    out = await repo.get_processed_filenames()
    assert out == {"a.txt", "b.txt", "c.txt"}
    assert isinstance(out, set)


@pytest.mark.asyncio
async def test_get_processed_returns_empty_set_when_no_rows(repo_factory):
    """Empty DB → empty set (NOT None). Pin so a regression that
    returned None would crash callers doing `name in cache`."""
    repo, _ = repo_factory(rows=[])
    out = await repo.get_processed_filenames()
    assert out == set()


@pytest.mark.asyncio
async def test_get_processed_filters_by_success_true(repo_factory):
    """Critical: must filter `WHERE success = true`. A regression that
    drops the filter would re-process FAILED files on every restart."""
    repo, db = repo_factory()
    await repo.get_processed_filenames()
    assert "WHERE success = true" in db.last_query


@pytest.mark.asyncio
async def test_get_processed_uses_correct_table(repo_factory):
    """Must query `processed_files` table, not any sibling like
    `processed_endstats_files`."""
    repo, db = repo_factory()
    await repo.get_processed_filenames()
    assert "FROM processed_files" in db.last_query


@pytest.mark.asyncio
async def test_get_processed_passes_no_params(repo_factory):
    """Static query — no params should be passed."""
    repo, db = repo_factory()
    await repo.get_processed_filenames()
    assert db.last_params is None


@pytest.mark.asyncio
async def test_get_processed_returns_empty_set_on_db_error(repo_factory):
    """DB exception → empty set (NOT raise). Pin fail-safe so a single
    DB hiccup at startup doesn't crash the bot."""
    repo, _ = repo_factory(raise_on_fetch=RuntimeError("connection lost"))
    out = await repo.get_processed_filenames()
    assert out == set()


@pytest.mark.asyncio
async def test_get_processed_deduplicates_via_set(repo_factory):
    """Duplicate rows in DB (shouldn't happen but…) → deduplicated by
    the set construction. Pin so a future "return list" change is loud."""
    repo, _ = repo_factory(rows=[("a.txt",), ("a.txt",), ("b.txt",)])
    out = await repo.get_processed_filenames()
    assert out == {"a.txt", "b.txt"}


# ---------------------------------------------------------------------------
# get_newly_processed_filenames — incremental delta
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_newly_processed_returns_filenames(repo_factory):
    repo, _ = repo_factory(rows=[("new1.txt",), ("new2.txt",)])
    out = await repo.get_newly_processed_filenames(datetime(2026, 1, 1))
    assert out == {"new1.txt", "new2.txt"}


@pytest.mark.asyncio
async def test_newly_processed_returns_empty_set_when_no_rows(repo_factory):
    repo, _ = repo_factory(rows=[])
    out = await repo.get_newly_processed_filenames(datetime(2026, 1, 1))
    assert out == set()


@pytest.mark.asyncio
async def test_newly_processed_filters_by_success_and_timestamp(repo_factory):
    """Must filter BOTH `success = true` AND `processed_at > $1` —
    a regression dropping either condition silently re-imports failed
    files OR full-scans the table on every cycle (perf regression)."""
    repo, db = repo_factory()
    await repo.get_newly_processed_filenames(datetime(2026, 1, 1))
    assert "success = true" in db.last_query
    assert "processed_at > $1" in db.last_query


@pytest.mark.asyncio
async def test_newly_processed_passes_since_as_param(repo_factory):
    """The `since` datetime must be passed to the DB as a query param
    (parameterised, not interpolated). asyncpg binds native datetime."""
    since = datetime(2026, 4, 21, 12, 0, 0)
    repo, db = repo_factory()
    await repo.get_newly_processed_filenames(since)
    assert db.last_params == (since,)


@pytest.mark.asyncio
async def test_newly_processed_returns_empty_set_on_db_error(repo_factory):
    """Same fail-safe contract as the full load."""
    repo, _ = repo_factory(raise_on_fetch=RuntimeError("timeout"))
    out = await repo.get_newly_processed_filenames(datetime(2026, 1, 1))
    assert out == set()


@pytest.mark.asyncio
async def test_newly_processed_deduplicates(repo_factory):
    repo, _ = repo_factory(rows=[("a.txt",), ("a.txt",), ("b.txt",)])
    out = await repo.get_newly_processed_filenames(datetime(2026, 1, 1))
    assert out == {"a.txt", "b.txt"}


@pytest.mark.asyncio
async def test_newly_processed_does_one_db_call(repo_factory):
    """Must NOT scan the table twice (no fallback queries)."""
    repo, db = repo_factory(rows=[("x.txt",)])
    await repo.get_newly_processed_filenames(datetime(2026, 1, 1))
    assert db.calls == 1


@pytest.mark.asyncio
async def test_newly_processed_returns_set_type(repo_factory):
    """Pin set type — caller does set-difference with the in-memory
    cache. A list return would change behaviour."""
    repo, _ = repo_factory(rows=[("x.txt",)])
    out = await repo.get_newly_processed_filenames(datetime(2026, 1, 1))
    assert isinstance(out, set)


# ---------------------------------------------------------------------------
# init wiring
# ---------------------------------------------------------------------------


def test_init_stores_db_adapter_and_config():
    """Repository keeps refs to its dependencies."""
    db = AsyncMock()
    cfg = object()
    repo = FileRepository(db_adapter=db, config=cfg)
    assert repo.db_adapter is db
    assert repo.config is cfg
