"""Tests for FileTracker class methods — dedup + integrity verification.

This is the multi-layer dedup gate that decides whether endstats_monitor
should download + process a stats file. A regression silently:

- `should_process_file` skip-very-old branch silently re-imports old
  files after lookback drift.
- `should_process_file` returns True on DB error → caller does NOT
  process — would re-process on every poll → DB hammered.
  ACTUALLY: production returns True on error (idempotent ON CONFLICT
  catches duplicates), pin observed semantics.
- `_is_in_processed_files_table` returns False on exception →
  retry-loop bug from the deep-RCA audit (filed 2026-03-26): files
  marked failed get retried forever.
  ACTUALLY: file_tracker.py was fixed — it now respects success=FALSE,
  pin the exact query so the fix doesn't regress.
- `mark_processed` doesn't compute hash when file_path is None →
  pin so callers passing None still record the row (otherwise the
  in-memory cache would grow without persistence).
- `verify_file_integrity` returns True for missing-hash row →
  pin so legacy imports without hashes don't false-alarm as
  corrupted.

Pin every dedup-layer branch + the integrity-verification edges.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.automation.file_tracker import FileTracker

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    a = AsyncMock()
    a.fetch_one = AsyncMock(return_value=None)
    a.execute = AsyncMock(return_value=None)
    return a


@pytest.fixture
def startup_time():
    return datetime(2026, 5, 7, 12, 0, 0)


@pytest.fixture
def tracker(db, startup_time):
    """Build a FileTracker with default 168h lookback config."""
    config = SimpleNamespace(STARTUP_LOOKBACK_HOURS=168)
    processed_files: set[str] = set()
    return FileTracker(db, config, startup_time, processed_files)


# Helper: build a stats filename at a given datetime
def _make_filename(dt: datetime, map_name: str = "oasis", round_n: int = 1) -> str:
    return f"{dt.strftime('%Y-%m-%d-%H%M%S')}-{map_name}-round-{round_n}.txt"


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_stores_passed_components(db, startup_time):
    config = SimpleNamespace()
    files: set[str] = set()
    t = FileTracker(db, config, startup_time, files)
    assert t.db_adapter is db
    assert t.config is config
    assert t.bot_startup_time == startup_time
    assert t.processed_files is files  # NOT a copy — caller's set


def test_init_processed_files_is_shared_reference(db, startup_time):
    """`processed_files` is the bot's set — pin so adds in tracker
    flow back to caller's in-memory cache."""
    config = SimpleNamespace()
    bot_files: set[str] = set()
    t = FileTracker(db, config, startup_time, bot_files)
    bot_files.add("foo.txt")
    assert "foo.txt" in t.processed_files


# ---------------------------------------------------------------------------
# should_process_file — file age (lookback) check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_should_process_skips_very_old_file(tracker, startup_time):
    """File created >168h before startup → skip (NOT process). Pin
    the lookback window."""
    old_dt = startup_time - timedelta(hours=200)
    filename = _make_filename(old_dt)
    out = await tracker.should_process_file(filename)
    assert out is False
    # Marked as processed in memory + via DB
    assert filename in tracker.processed_files


@pytest.mark.asyncio
async def test_should_process_accepts_file_within_lookback(tracker, db, startup_time):
    """File created within 168h before startup → continues to other
    dedup layers (not auto-skipped on age)."""
    recent_dt = startup_time - timedelta(hours=24)
    filename = _make_filename(recent_dt)
    # No DB matches → should process
    db.fetch_one = AsyncMock(return_value=None)
    out = await tracker.should_process_file(filename)
    assert out is True


@pytest.mark.asyncio
async def test_should_process_accepts_file_after_startup(tracker, db, startup_time):
    """File created after bot startup → process."""
    future_dt = startup_time + timedelta(minutes=10)
    filename = _make_filename(future_dt)
    db.fetch_one = AsyncMock(return_value=None)
    out = await tracker.should_process_file(filename)
    assert out is True


@pytest.mark.asyncio
async def test_should_process_at_exact_lookback_boundary_processes(tracker, db, startup_time):
    """File created exactly at the cutoff → still within window
    (`<` for cutoff, NOT `<=`). Pin observed boundary."""
    boundary_dt = startup_time - timedelta(hours=168)
    filename = _make_filename(boundary_dt)
    db.fetch_one = AsyncMock(return_value=None)
    out = await tracker.should_process_file(filename)
    # boundary_dt < cutoff_time? cutoff = startup - 168h = boundary_dt
    # boundary_dt < boundary_dt is FALSE → process
    assert out is True


@pytest.mark.asyncio
async def test_should_process_ignore_startup_time_skips_age_check(tracker, startup_time):
    """ignore_startup_time=True bypasses the age gate — pin so
    manual !import on a 6-month-old file works."""
    very_old_dt = startup_time - timedelta(days=180)
    filename = _make_filename(very_old_dt)
    out = await tracker.should_process_file(
        filename, ignore_startup_time=True
    )
    # Falls through to other layers; with empty DB → True
    assert out is True


@pytest.mark.asyncio
async def test_should_process_unparseable_filename_falls_through(tracker, db):
    """If filename doesn't match YYYY-MM-DD-HHMMSS-... → continue
    to other dedup layers (warning logged, not crash)."""
    filename = "garbage_filename.txt"
    db.fetch_one = AsyncMock(return_value=None)
    out = await tracker.should_process_file(filename)
    # No DB matches → True
    assert out is True


# ---------------------------------------------------------------------------
# should_process_file — in-memory cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_should_process_returns_false_when_in_memory(tracker, startup_time):
    """Filename already in processed_files set → False (no DB hit
    needed)."""
    recent = startup_time - timedelta(hours=10)
    filename = _make_filename(recent)
    tracker.processed_files.add(filename)
    out = await tracker.should_process_file(filename)
    assert out is False


@pytest.mark.asyncio
async def test_should_process_check_db_only_skips_in_memory(tracker, db, startup_time):
    """check_db_only=True → in-memory cache is BYPASSED (used by
    sync to find genuinely-new-to-DB files even if cached)."""
    recent = startup_time - timedelta(hours=10)
    filename = _make_filename(recent)
    tracker.processed_files.add(filename)
    db.fetch_one = AsyncMock(return_value=None)  # not in DB
    out = await tracker.should_process_file(filename, check_db_only=True)
    assert out is True


# ---------------------------------------------------------------------------
# should_process_file — DB error fail-open
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_should_process_returns_true_on_db_exception(tracker, db, startup_time):
    """DB error during dedup checks → return True (process). Pin
    observed fail-open semantics — import is idempotent (ON CONFLICT)
    so processing on error is safer than re-trying forever."""
    recent = startup_time - timedelta(hours=10)
    filename = _make_filename(recent)
    db.fetch_one = AsyncMock(side_effect=RuntimeError("DB down"))
    out = await tracker.should_process_file(filename)
    assert out is True


# ---------------------------------------------------------------------------
# _is_in_processed_files_table
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_in_processed_files_returns_true_when_row_exists(tracker, db):
    """Row found → True."""
    db.fetch_one = AsyncMock(return_value=(1,))
    out = await tracker._is_in_processed_files_table("foo.txt")
    assert out is True


@pytest.mark.asyncio
async def test_is_in_processed_files_returns_false_when_no_row(tracker, db):
    db.fetch_one = AsyncMock(return_value=None)
    out = await tracker._is_in_processed_files_table("foo.txt")
    assert out is False


@pytest.mark.asyncio
async def test_is_in_processed_files_returns_false_on_exception(tracker, db):
    """DB error → False (assume unprocessed → caller will try DB
    again on next poll). Pin defensive default."""
    db.fetch_one = AsyncMock(side_effect=RuntimeError("DB down"))
    out = await tracker._is_in_processed_files_table("foo.txt")
    assert out is False


@pytest.mark.asyncio
async def test_is_in_processed_files_query_does_not_filter_by_success(tracker, db):
    """Query selects on filename ONLY — both successful AND failed
    entries return True. Pin the deep-RCA audit fix from 2026-03-26:
    file_tracker now respects success=FALSE entries (was causing
    infinite retry loops)."""
    db.fetch_one = AsyncMock(return_value=(1,))
    await tracker._is_in_processed_files_table("foo.txt")
    args, _ = db.fetch_one.await_args
    sql = args[0]
    assert "FROM processed_files" in sql
    assert "WHERE filename" in sql
    # Must NOT filter by success (so failed entries also short-circuit)
    assert "success" not in sql.lower() or "success = TRUE" not in sql.lower()


# ---------------------------------------------------------------------------
# mark_processed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_processed_inserts_row(tracker, db):
    await tracker.mark_processed("foo.txt", success=True)
    db.execute.assert_awaited_once()
    args, _ = db.execute.await_args
    sql, params = args[0], args[1]
    assert "INSERT INTO processed_files" in sql
    assert params[0] == "foo.txt"


@pytest.mark.asyncio
async def test_mark_processed_uses_upsert(tracker, db):
    """Uses ON CONFLICT DO UPDATE — pin so a re-mark replaces old
    row (e.g., success=False → success=True after retry)."""
    await tracker.mark_processed("foo.txt", success=True)
    args, _ = db.execute.await_args
    sql = args[0]
    assert "ON CONFLICT" in sql.upper()
    assert "DO UPDATE" in sql.upper()


@pytest.mark.asyncio
async def test_mark_processed_with_file_path_computes_hash(tracker, db, tmp_path):
    """When file_path provided AND file exists → hash computed."""
    f = tmp_path / "foo.txt"
    f.write_bytes(b"hello world")
    expected_hash = hashlib.sha256(b"hello world").hexdigest()

    await tracker.mark_processed("foo.txt", success=True, file_path=str(f))
    args, _ = db.execute.await_args
    params = args[1]
    # file_hash is param[1]
    assert params[1] == expected_hash


@pytest.mark.asyncio
async def test_mark_processed_with_missing_file_uses_none_hash(tracker, db):
    """file_path provided but file doesn't exist → hash is None
    (no crash, just empty hash). Pin defensive behaviour."""
    await tracker.mark_processed(
        "foo.txt", success=True, file_path="/nonexistent/path.txt"
    )
    args, _ = db.execute.await_args
    params = args[1]
    assert params[1] is None


@pytest.mark.asyncio
async def test_mark_processed_includes_error_message_on_failure(tracker, db):
    await tracker.mark_processed(
        "foo.txt", success=False, error_msg="Parser exploded"
    )
    args, _ = db.execute.await_args
    params = args[1]
    # success at index 2, error_msg at index 3
    assert params[2] is False
    assert params[3] == "Parser exploded"


@pytest.mark.asyncio
async def test_mark_processed_swallows_db_error(tracker, db):
    """DB execute fails → log error but do NOT raise. Pin so a
    transient DB hiccup doesn't crash endstats_monitor."""
    db.execute = AsyncMock(side_effect=RuntimeError("DB down"))
    # Should NOT raise
    await tracker.mark_processed("foo.txt", success=True)


# ---------------------------------------------------------------------------
# verify_file_integrity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_returns_false_when_file_missing(tracker, db):
    """Missing file → (False, "not found")."""
    ok, msg = await tracker.verify_file_integrity("foo.txt", "/nonexistent")
    assert ok is False
    assert "not found" in msg.lower()


@pytest.mark.asyncio
async def test_verify_returns_true_with_no_stored_hash(tracker, db, tmp_path):
    """Row found but stored hash is NULL → (True, "no stored hash"
    message). Pin so legacy imports without hashes don't false-alarm
    as corrupted."""
    f = tmp_path / "foo.txt"
    f.write_bytes(b"content")
    db.fetch_one = AsyncMock(return_value=(None,))  # NULL hash
    ok, msg = await tracker.verify_file_integrity("foo.txt", str(f))
    assert ok is True
    assert "no stored hash" in msg.lower()


@pytest.mark.asyncio
async def test_verify_returns_true_when_no_row_at_all(tracker, db, tmp_path):
    """No processed_files row → (True, "no stored hash"). Pin so a
    missing-row case behaves identically to NULL-hash."""
    f = tmp_path / "foo.txt"
    f.write_bytes(b"content")
    db.fetch_one = AsyncMock(return_value=None)
    ok, msg = await tracker.verify_file_integrity("foo.txt", str(f))
    assert ok is True


@pytest.mark.asyncio
async def test_verify_returns_true_on_hash_match(tracker, db, tmp_path):
    """Stored hash == current hash → (True, "verified" message)."""
    f = tmp_path / "foo.txt"
    payload = b"content"
    f.write_bytes(payload)
    correct_hash = hashlib.sha256(payload).hexdigest()
    db.fetch_one = AsyncMock(return_value=(correct_hash,))
    ok, msg = await tracker.verify_file_integrity("foo.txt", str(f))
    assert ok is True
    assert "verified" in msg.lower()


@pytest.mark.asyncio
async def test_verify_returns_false_on_hash_mismatch(tracker, db, tmp_path):
    """Stored hash != current → (False, "Hash mismatch"). Pin the
    fail-loud contract for tampered/corrupted files."""
    f = tmp_path / "foo.txt"
    f.write_bytes(b"current content")
    db.fetch_one = AsyncMock(return_value=("0" * 64,))  # bogus stored hash
    ok, msg = await tracker.verify_file_integrity("foo.txt", str(f))
    assert ok is False
    assert "mismatch" in msg.lower()


@pytest.mark.asyncio
async def test_verify_returns_false_on_db_exception(tracker, db, tmp_path):
    """DB error → (False, "Verification error: ..."). Pin so an
    unverifiable file is treated as suspect (not silently passed)."""
    f = tmp_path / "foo.txt"
    f.write_bytes(b"x")
    db.fetch_one = AsyncMock(side_effect=RuntimeError("connection lost"))
    ok, msg = await tracker.verify_file_integrity("foo.txt", str(f))
    assert ok is False
    assert "verification error" in msg.lower()
