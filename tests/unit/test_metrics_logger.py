"""Tests for MetricsLogger __init__ + get_summary + in-memory logging.

This logger powers the bot's `!metrics` admin command and the health
report. A regression silently:

- Drops in-memory ring buffer cap (1000 events / 500 errors / 1000
  metrics) → memory leak on long-running bot.
- Mis-counts event/error types → operator triage broken.
- get_summary picks wrong "most common" → wrong rootcause shown.

DB calls are stubbed with AsyncMock so we test the in-memory side
effects only.
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from bot.services.automation.metrics_logger import MetricsLogger


@pytest.fixture
def logger_(tmp_path):
    """Build a logger with tmp paths so we don't pollute the repo."""
    return MetricsLogger(
        db_path=str(tmp_path / "metrics.db"),
        log_dir=str(tmp_path / "logs"),
    )


# ---------------------------------------------------------------------------
# __init__ — directory creation + defaults
# ---------------------------------------------------------------------------


def test_init_creates_log_directory(tmp_path):
    """Constructor creates log_dir so first log doesn't crash."""
    log_dir = tmp_path / "metrics_logs"
    MetricsLogger(db_path=str(tmp_path / "x.db"), log_dir=str(log_dir))
    assert log_dir.exists()


def test_init_creates_db_dir(tmp_path):
    """Parent directory of the DB path is created (so the SQLite file
    can be opened lazily later)."""
    db_path = tmp_path / "nested" / "deeper" / "metrics.db"
    MetricsLogger(db_path=str(db_path), log_dir=str(tmp_path / "logs"))
    assert db_path.parent.exists()


def test_init_starts_with_empty_in_memory_buffers(logger_):
    """Fresh instance has empty events/errors/performance lists."""
    assert logger_.events == []
    assert logger_.errors == []
    assert logger_.performance == []


def test_init_starts_with_empty_counters(logger_):
    """Counters are empty defaultdicts → unknown key returns 0."""
    assert dict(logger_.event_counts) == {}
    assert dict(logger_.error_counts) == {}
    assert logger_.event_counts["never-seen"] == 0  # defaultdict returns 0


def test_init_records_start_time(logger_):
    """start_time is set at construction → uptime calc reference."""
    assert logger_.start_time is not None


def test_init_records_uninitialised(logger_):
    """DB lazy init flag starts False — first log call triggers init."""
    assert logger_._is_initialized is False
    assert logger_._db_connection is None


def test_init_uses_db_path_when_provided(tmp_path):
    """Explicit db_path takes precedence over log_dir/metrics.db default."""
    explicit = str(tmp_path / "explicit.db")
    m = MetricsLogger(db_path=explicit, log_dir=str(tmp_path / "logs"))
    assert m.metrics_db_path == explicit


def test_init_falls_back_to_log_dir_default_when_db_path_empty(tmp_path):
    """Empty db_path → falls back to log_dir/metrics.db."""
    log_dir = str(tmp_path / "logs")
    m = MetricsLogger(db_path="", log_dir=log_dir)
    assert m.metrics_db_path == f"{log_dir}/metrics.db"


# ---------------------------------------------------------------------------
# log_event — in-memory side effects
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_event_appends_to_memory(logger_):
    with patch.object(logger_, "_execute_write", AsyncMock()):
        await logger_.log_event("file_processed", {"file": "x.txt"})
    assert len(logger_.events) == 1
    assert logger_.events[0]["type"] == "file_processed"


@pytest.mark.asyncio
async def test_log_event_increments_counter(logger_):
    """event_counts[type] += 1 each call."""
    with patch.object(logger_, "_execute_write", AsyncMock()):
        await logger_.log_event("ssh_check")
        await logger_.log_event("ssh_check")
        await logger_.log_event("file_processed")
    assert logger_.event_counts["ssh_check"] == 2
    assert logger_.event_counts["file_processed"] == 1


@pytest.mark.asyncio
async def test_log_event_caps_in_memory_buffer_at_1000(logger_):
    """Pin the 1000-event cap — without it, a 24/7 bot leaks memory."""
    with patch.object(logger_, "_execute_write", AsyncMock()):
        for _ in range(1500):
            await logger_.log_event("test")
    assert len(logger_.events) == 1000


@pytest.mark.asyncio
async def test_log_event_drops_oldest_when_capping(logger_):
    """When cap hits, OLDEST events drop off (FIFO)."""
    with patch.object(logger_, "_execute_write", AsyncMock()):
        for i in range(1100):
            await logger_.log_event("test", {"idx": i})
    # First event should be idx=100 (first 100 dropped)
    assert logger_.events[0]["data"]["idx"] == 100
    assert logger_.events[-1]["data"]["idx"] == 1099


@pytest.mark.asyncio
async def test_log_event_failure_does_not_crash(logger_):
    """DB write fails → exception swallowed (logged only). Pin so a
    full DB doesn't crash the bot's main task loop."""
    with patch.object(
        logger_, "_execute_write", AsyncMock(side_effect=RuntimeError("disk full"))
    ):
        # Should NOT raise
        await logger_.log_event("test")


# ---------------------------------------------------------------------------
# log_error — in-memory side effects
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_error_caps_at_500(logger_):
    """Errors capped at 500 in memory (smaller than events — pin the
    half-cap so error storms don't OOM the bot)."""
    with patch.object(logger_, "_execute_write", AsyncMock()):
        for _ in range(700):
            await logger_.log_error("ssh", "boom")
    assert len(logger_.errors) == 500


@pytest.mark.asyncio
async def test_log_error_increments_counter(logger_):
    with patch.object(logger_, "_execute_write", AsyncMock()):
        await logger_.log_error("ssh_connection", "boom")
        await logger_.log_error("ssh_connection", "boom2")
        await logger_.log_error("database", "down")
    assert logger_.error_counts["ssh_connection"] == 2
    assert logger_.error_counts["database"] == 1


@pytest.mark.asyncio
async def test_log_error_db_failure_does_not_crash(logger_):
    """Same fail-safe contract as log_event."""
    with patch.object(
        logger_, "_execute_write", AsyncMock(side_effect=RuntimeError("oops"))
    ):
        await logger_.log_error("test", "msg")  # no raise


# ---------------------------------------------------------------------------
# log_performance — in-memory cap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_performance_caps_at_1000(logger_):
    with patch.object(logger_, "_execute_write", AsyncMock()):
        for i in range(1200):
            await logger_.log_performance("metric", float(i))
    assert len(logger_.performance) == 1000


@pytest.mark.asyncio
async def test_log_performance_default_unit_is_ms(logger_):
    with patch.object(logger_, "_execute_write", AsyncMock()):
        await logger_.log_performance("ssh_time", 250.0)
    assert logger_.performance[0]["unit"] == "ms"


@pytest.mark.asyncio
async def test_log_performance_custom_unit(logger_):
    with patch.object(logger_, "_execute_write", AsyncMock()):
        await logger_.log_performance("file_size", 1024.0, unit="bytes")
    assert logger_.performance[0]["unit"] == "bytes"


# ---------------------------------------------------------------------------
# get_summary — in-memory snapshot
# ---------------------------------------------------------------------------


def test_summary_returns_zero_for_empty_state(logger_):
    """Fresh logger → all-zero counts, None for most_common."""
    out = logger_.get_summary()
    assert out["total_events"] == 0
    assert out["total_errors"] == 0
    assert out["event_types"] == 0
    assert out["error_types"] == 0
    assert out["most_common_event"] is None
    assert out["most_common_error"] is None


def test_summary_includes_uptime_seconds(logger_):
    """uptime_seconds is an int. Pin so a regression that returns
    timedelta would crash the JSON-serialising callers."""
    out = logger_.get_summary()
    assert isinstance(out["uptime_seconds"], int)
    assert out["uptime_seconds"] >= 0


def test_summary_uptime_formatted_drops_microseconds(logger_):
    """uptime_formatted strips microseconds (split('.')[0])."""
    out = logger_.get_summary()
    assert "." not in out["uptime_formatted"]


def test_summary_picks_most_common_event(logger_):
    """When multiple event types, max-count wins."""
    logger_.event_counts["a"] = 5
    logger_.event_counts["b"] = 10
    logger_.event_counts["c"] = 3
    out = logger_.get_summary()
    assert out["most_common_event"] == "b"


def test_summary_picks_most_common_error(logger_):
    logger_.error_counts["ssh"] = 12
    logger_.error_counts["db"] = 7
    out = logger_.get_summary()
    assert out["most_common_error"] == "ssh"


def test_summary_handles_tied_counts(logger_):
    """When two types tie for max, ANY of them is acceptable — but the
    function must not crash. Pin observed behaviour: max() returns the
    first one with that value."""
    logger_.event_counts["a"] = 5
    logger_.event_counts["b"] = 5
    out = logger_.get_summary()
    assert out["most_common_event"] in ("a", "b")


def test_summary_event_types_counts_distinct_keys(logger_):
    """event_types = number of distinct event_type values, NOT total events."""
    logger_.event_counts["x"] = 100
    logger_.event_counts["y"] = 1
    logger_.event_counts["z"] = 1
    out = logger_.get_summary()
    assert out["event_types"] == 3


def test_summary_uses_in_memory_event_list_for_total(logger_):
    """total_events comes from len(self.events), NOT sum of counters
    (matters because events are capped at 1000 but counters never)."""
    logger_.events = [{}] * 50
    logger_.event_counts["a"] = 200  # would mismatch if counters used
    out = logger_.get_summary()
    assert out["total_events"] == 50


def test_summary_uptime_grows_over_time(logger_, monkeypatch):
    """As time advances, uptime_seconds increases."""
    from datetime import datetime as real_dt

    fixed_now = logger_.start_time + timedelta(seconds=120)

    class _FrozenDT:
        @classmethod
        def now(cls):
            return fixed_now

    monkeypatch.setattr(
        "bot.services.automation.metrics_logger.datetime", _FrozenDT,
    )
    out = logger_.get_summary()
    assert out["uptime_seconds"] == 120
    # Suppress unused import warning
    _ = real_dt
