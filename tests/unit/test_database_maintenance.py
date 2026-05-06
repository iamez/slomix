"""Tests for DatabaseMaintenance — backup retention + log cleanup + stats.

This service runs scheduled backups and log rotation. A regression
silently:

- Backup retention drops too many backups → no recovery point.
- Log cleanup removes wrong files (recent ones) → operator loses
  forensic trail.
- get_stats reports stale data → admin command shows misleading
  status.

Pin the contract for `_cleanup_old_backups`, `cleanup_old_logs`, and
`get_stats` (the testable methods that don't require a real Discord
bot or PostgreSQL connection).
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from bot.services.automation.database_maintenance import DatabaseMaintenance


@pytest.fixture
def maintenance(tmp_path, monkeypatch):
    """Build a DatabaseMaintenance with tmp dirs for backup/log."""
    monkeypatch.chdir(tmp_path)
    bot = MagicMock()
    m = DatabaseMaintenance(bot=bot, db_path=None, admin_channel_id=42)
    # Override default dirs with tmp paths so the test is hermetic
    m.backup_dir = str(tmp_path / "backups")
    m.log_dir = str(tmp_path / "logs")
    os.makedirs(m.backup_dir, exist_ok=True)
    return m


def _touch_with_mtime(path: str, mtime: float):
    """Create file and set its mtime."""
    with open(path, "w") as f:
        f.write("")
    os.utime(path, (mtime, mtime))


# ---------------------------------------------------------------------------
# __init__ — defaults + state
# ---------------------------------------------------------------------------


def test_init_uses_default_backup_retention(tmp_path, monkeypatch):
    """Default retention is 7. Pin so a deploy with no override
    doesn't accidentally drop to 1 (single point of failure)."""
    monkeypatch.chdir(tmp_path)
    m = DatabaseMaintenance(bot=MagicMock(), db_path=None, admin_channel_id=42)
    assert m.backup_retention == 7


def test_init_uses_default_log_retention_days(tmp_path, monkeypatch):
    """30-day default for log retention."""
    monkeypatch.chdir(tmp_path)
    m = DatabaseMaintenance(bot=MagicMock(), db_path=None, admin_channel_id=42)
    assert m.log_retention_days == 30


def test_init_starts_with_no_recent_runs(tmp_path, monkeypatch):
    """All last_* fields None until first run. Pin so get_stats
    correctly reports "never run" for fresh deployments."""
    monkeypatch.chdir(tmp_path)
    m = DatabaseMaintenance(bot=MagicMock(), db_path=None, admin_channel_id=42)
    assert m.last_backup is None
    assert m.last_vacuum is None
    assert m.last_cleanup is None


def test_init_creates_backup_dir(tmp_path, monkeypatch):
    """Constructor must create backup_dir so the first backup doesn't
    crash on missing path."""
    monkeypatch.chdir(tmp_path)
    DatabaseMaintenance(bot=MagicMock(), db_path=None, admin_channel_id=42)
    assert os.path.exists("logs/backups")


# ---------------------------------------------------------------------------
# _cleanup_old_backups — retention enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_keeps_only_retention_count(maintenance):
    """With retention=3 and 10 backup files → only 3 newest survive."""
    maintenance.backup_retention = 3
    base = time.time()
    for i in range(10):
        _touch_with_mtime(
            os.path.join(maintenance.backup_dir, f"backup_{i}.sql"),
            base + i,  # increasing mtime → file 9 is newest
        )

    await maintenance._cleanup_old_backups()

    remaining = sorted(os.listdir(maintenance.backup_dir))
    assert len(remaining) == 3
    # Newest 3 (indexes 7, 8, 9) survive
    assert remaining == ["backup_7.sql", "backup_8.sql", "backup_9.sql"]


@pytest.mark.asyncio
async def test_cleanup_keeps_all_when_under_retention(maintenance):
    """3 backups + retention=7 → all kept."""
    maintenance.backup_retention = 7
    base = time.time()
    for i in range(3):
        _touch_with_mtime(
            os.path.join(maintenance.backup_dir, f"backup_{i}.sql"),
            base + i,
        )

    await maintenance._cleanup_old_backups()
    assert len(os.listdir(maintenance.backup_dir)) == 3


@pytest.mark.asyncio
async def test_cleanup_only_targets_files_with_backup_in_name(maintenance):
    """Files without "backup" in name are NOT touched. Pin so an
    unrelated `notes.txt` in the backup dir doesn't get deleted."""
    maintenance.backup_retention = 1
    _touch_with_mtime(
        os.path.join(maintenance.backup_dir, "backup_old.sql"),
        time.time() - 1000,
    )
    _touch_with_mtime(
        os.path.join(maintenance.backup_dir, "backup_new.sql"),
        time.time(),
    )
    _touch_with_mtime(
        os.path.join(maintenance.backup_dir, "notes.txt"),
        time.time(),
    )
    _touch_with_mtime(
        os.path.join(maintenance.backup_dir, "README.md"),
        time.time(),
    )

    await maintenance._cleanup_old_backups()

    files = set(os.listdir(maintenance.backup_dir))
    assert "notes.txt" in files  # untouched
    assert "README.md" in files  # untouched
    assert "backup_new.sql" in files  # newest backup kept
    assert "backup_old.sql" not in files  # old backup deleted


@pytest.mark.asyncio
async def test_cleanup_handles_empty_dir(maintenance):
    """Empty backup dir → no error (try/except guard)."""
    await maintenance._cleanup_old_backups()
    assert os.listdir(maintenance.backup_dir) == []


@pytest.mark.asyncio
async def test_cleanup_picks_newest_by_mtime_not_filename(maintenance):
    """File with old name but new mtime is kept; new name old mtime
    deleted. Pin so a renamed-but-touched backup is preserved."""
    maintenance.backup_retention = 1
    # Filename suggests "old" but mtime is recent
    _touch_with_mtime(
        os.path.join(maintenance.backup_dir, "backup_old_name.sql"),
        time.time(),  # NEWEST
    )
    _touch_with_mtime(
        os.path.join(maintenance.backup_dir, "backup_zzz_name.sql"),
        time.time() - 5000,  # OLDEST
    )

    await maintenance._cleanup_old_backups()
    remaining = os.listdir(maintenance.backup_dir)
    assert remaining == ["backup_old_name.sql"]


# ---------------------------------------------------------------------------
# cleanup_old_logs — age-based cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_logs_returns_zero_when_dir_missing(maintenance, tmp_path):
    """Missing log dir → return 0 (NOT raise FileNotFoundError)."""
    # Point log_dir at a path that genuinely doesn't exist
    maintenance.log_dir = str(tmp_path / "nonexistent_logs")
    assert not os.path.exists(maintenance.log_dir)
    out = await maintenance.cleanup_old_logs()
    assert out == 0


@pytest.mark.asyncio
async def test_cleanup_logs_removes_old_files(maintenance):
    os.makedirs(maintenance.log_dir, exist_ok=True)
    maintenance.log_retention_days = 30
    cutoff_seconds = 31 * 86400  # 31 days ago
    _touch_with_mtime(
        os.path.join(maintenance.log_dir, "old.log"),
        time.time() - cutoff_seconds,
    )
    _touch_with_mtime(
        os.path.join(maintenance.log_dir, "fresh.log"),
        time.time(),
    )

    out = await maintenance.cleanup_old_logs()
    assert out == 1
    files = os.listdir(maintenance.log_dir)
    assert "fresh.log" in files
    assert "old.log" not in files


@pytest.mark.asyncio
async def test_cleanup_logs_keeps_files_at_retention_boundary(maintenance):
    """Exactly N days old → kept (uses strict <). Pin so flapping at
    midnight doesn't oscillate file deletion."""
    os.makedirs(maintenance.log_dir, exist_ok=True)
    maintenance.log_retention_days = 30
    # File EXACTLY 30 days old (cutoff)
    _touch_with_mtime(
        os.path.join(maintenance.log_dir, "boundary.log"),
        time.time() - (30 * 86400 - 60),  # just under 30 days
    )
    out = await maintenance.cleanup_old_logs()
    assert out == 0
    assert "boundary.log" in os.listdir(maintenance.log_dir)


@pytest.mark.asyncio
async def test_cleanup_logs_skips_subdirectories(maintenance):
    """Only files removed; subdirs (e.g., logs/archives/) untouched.
    Pin so subdirectory structure isn't accidentally rm-rf'd."""
    os.makedirs(os.path.join(maintenance.log_dir, "subdir"), exist_ok=True)
    out = await maintenance.cleanup_old_logs()
    assert out == 0
    assert os.path.isdir(os.path.join(maintenance.log_dir, "subdir"))


@pytest.mark.asyncio
async def test_cleanup_logs_updates_last_cleanup_when_files_removed(maintenance):
    os.makedirs(maintenance.log_dir, exist_ok=True)
    _touch_with_mtime(
        os.path.join(maintenance.log_dir, "old.log"),
        time.time() - (40 * 86400),
    )
    assert maintenance.last_cleanup is None
    await maintenance.cleanup_old_logs()
    assert maintenance.last_cleanup is not None


@pytest.mark.asyncio
async def test_cleanup_logs_no_update_when_nothing_to_clean(maintenance):
    """0 files removed → last_cleanup stays None. Pin so the
    "last cleanup" timestamp accurately reflects when work happened."""
    os.makedirs(maintenance.log_dir, exist_ok=True)
    _touch_with_mtime(
        os.path.join(maintenance.log_dir, "fresh.log"),
        time.time(),
    )
    await maintenance.cleanup_old_logs()
    assert maintenance.last_cleanup is None


@pytest.mark.asyncio
async def test_cleanup_logs_returns_zero_on_exception(maintenance, monkeypatch):
    """OS error → returns 0 (NOT raise). Pin fail-safe."""
    os.makedirs(maintenance.log_dir, exist_ok=True)
    def _boom(*a, **k):
        raise OSError("permission denied")
    monkeypatch.setattr(os, "listdir", _boom)
    out = await maintenance.cleanup_old_logs()
    assert out == 0


# ---------------------------------------------------------------------------
# get_stats — admin status report
# ---------------------------------------------------------------------------


def test_get_stats_returns_none_for_unrun_operations(maintenance):
    """Fresh state → all None for last_*."""
    out = maintenance.get_stats()
    assert out["last_backup"] is None
    assert out["last_vacuum"] is None
    assert out["last_cleanup"] is None


def test_get_stats_returns_iso_strings_for_run_operations(maintenance):
    """Datetime fields → ISO format string in output. Pin so the
    admin embed doesn't get raw datetime reprs."""
    maintenance.last_backup = datetime(2026, 4, 21, 12, 0, 0)
    out = maintenance.get_stats()
    assert out["last_backup"] == "2026-04-21T12:00:00"


def test_get_stats_counts_backup_files(maintenance):
    """Count includes only files with "backup" in name. Pin so a
    `notes.txt` doesn't inflate the count."""
    base = time.time()
    for i in range(5):
        _touch_with_mtime(
            os.path.join(maintenance.backup_dir, f"backup_{i}.sql"),
            base + i,
        )
    _touch_with_mtime(os.path.join(maintenance.backup_dir, "README.md"), base)

    out = maintenance.get_stats()
    assert out["backup_count"] == 5  # README excluded


def test_get_stats_returns_zero_count_when_dir_missing(maintenance):
    """If backup_dir vanished mid-session, count → 0 (NOT crash)."""
    import shutil
    shutil.rmtree(maintenance.backup_dir)
    out = maintenance.get_stats()
    assert out["backup_count"] == 0


def test_get_stats_includes_all_four_keys(maintenance):
    """Schema contract: dict has these exact keys for the admin embed
    template. A regression that drops a key crashes the embed builder."""
    out = maintenance.get_stats()
    assert set(out.keys()) == {
        "last_backup", "last_vacuum", "last_cleanup", "backup_count",
    }
