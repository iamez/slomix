"""Tests for MonitoringService — config defaults + cleanup safety.

This service records game-server status (UDP poll) and voice activity
into history tables every ~5 minutes. A regression silently:

- `__init__` retention drift → records pile up unboundedly (DB bloat)
  or get aggressively pruned (lose historical charts).
- `__init__` interval defaults silently shrink → service hammers the
  game server with UDP requests every second.
- `_cleanup_table` accepts an arbitrary table name → an attacker who
  can influence the table arg could DELETE FROM ANY table → DATA
  LOSS. The allowlist (_MONITORING_TABLES) is the security boundary.
- `_is_insufficient_privilege_error` regex misses postgres' actual
  error class name → cleanup silently retries forever instead of
  gracefully bailing.
- `stop()` doesn't await task cancellations → tasks linger after
  bot shutdown → CancelledError logged on next bot start.

Pin the security-critical allowlist + every config default.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.services.monitoring_service import MonitoringService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    a = AsyncMock()
    a.fetch_one = AsyncMock(return_value=None)
    a.fetch_all = AsyncMock(return_value=[])
    a.execute = AsyncMock(return_value=None)
    return a


@pytest.fixture
def bot():
    return MagicMock()


def _service(bot, db, **cfg):
    """Build a MonitoringService with config overrides."""
    config = SimpleNamespace(**cfg)
    return MonitoringService(bot, db, config)


# ---------------------------------------------------------------------------
# __init__ — config defaults
# ---------------------------------------------------------------------------


def test_init_default_server_host_is_production(bot, db):
    """Default server_host = `puran.hehe.si` (the production VPS).
    Pin so a bot-config-less deploy still polls the right server."""
    s = _service(bot, db)
    assert s.server_host == "puran.hehe.si"


def test_init_default_server_port(bot, db):
    """Default port 27960 — the canonical ET:Legacy port."""
    s = _service(bot, db)
    assert s.server_port == 27960


def test_init_default_intervals_are_5_minutes(bot, db):
    """Both server and voice loops default to 300s (5 min). Pin so
    a refactor that drops to 30s doesn't DDoS the game server."""
    s = _service(bot, db)
    assert s.server_interval == 300
    assert s.voice_interval == 300


def test_init_default_retention_is_30_days(bot, db):
    """30-day retention default. Pin so the website's historical
    chart window doesn't silently shrink to 1 day."""
    s = _service(bot, db)
    assert s.retention_days == 30


def test_init_overrides_apply(bot, db):
    """Custom config values flow through correctly."""
    s = _service(
        bot, db,
        server_host="alt.example.com",
        server_port=27999,
        monitoring_server_interval_seconds=60,
        monitoring_voice_interval_seconds=120,
        monitoring_retention_days=90,
    )
    assert s.server_host == "alt.example.com"
    assert s.server_port == 27999
    assert s.server_interval == 60
    assert s.voice_interval == 120
    assert s.retention_days == 90


def test_init_starts_with_no_running_tasks(bot, db):
    """All task references start as None — pin so `start()` knows
    nothing is running yet (idempotent start path)."""
    s = _service(bot, db)
    assert s.server_task is None
    assert s.voice_task is None
    assert s.cleanup_task is None


def test_init_db_user_starts_none(bot, db):
    """_db_user is lazy-loaded; starts None until queried."""
    s = _service(bot, db)
    assert s._db_user is None


def test_init_coerces_string_port_to_int(bot, db):
    """Config sometimes passes string from .env — pin int() coercion
    so a "27960" string doesn't crash UDP socket creation."""
    s = _service(bot, db, server_port="27960")
    assert s.server_port == 27960
    assert isinstance(s.server_port, int)


def test_init_coerces_retention_string_to_int(bot, db):
    """Same for retention_days."""
    s = _service(bot, db, monitoring_retention_days="14")
    assert s.retention_days == 14


# ---------------------------------------------------------------------------
# _MONITORING_TABLES allowlist — security boundary
# ---------------------------------------------------------------------------


def test_monitoring_tables_allowlist_contents():
    """The allowlist defines which tables `_cleanup_table` can DELETE FROM.
    Pin every entry so an unintended addition (e.g., player tables)
    is a deliberate decision, not a typo."""
    expected = {
        "server_status_history",
        "voice_status_history",
        "voice_members",
        "live_status",
    }
    assert expected == MonitoringService._MONITORING_TABLES


def test_monitoring_tables_is_frozen():
    """Allowlist is a frozenset — pin so a runtime .add() can't
    weaponise the cleanup path."""
    assert isinstance(MonitoringService._MONITORING_TABLES, frozenset)


def test_monitoring_tables_does_not_include_player_or_round_tables():
    """Defensive check: critical tables (which CANNOT be in the
    allowlist) are still absent. Pin so a future expansion that
    accidentally adds e.g. `rounds` is loud."""
    forbidden = {"rounds", "player_comprehensive_stats", "player_links",
                 "session_teams", "lua_round_teams", "round_correlations"}
    assert MonitoringService._MONITORING_TABLES.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# _cleanup_table — allowlist enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_table_refuses_unlisted_table(bot, db):
    """An attacker-influenced table name → refused (NO db.execute).
    Pin the security boundary."""
    from datetime import datetime
    s = _service(bot, db)
    await s._cleanup_table("rounds; DROP TABLE players;--", datetime.utcnow())
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_cleanup_table_refuses_legitimate_but_unlisted(bot, db):
    """Even legitimate non-monitoring tables refused. Pin so the
    allowlist isn't bypassed for "trusted" callers."""
    from datetime import datetime
    s = _service(bot, db)
    await s._cleanup_table("player_comprehensive_stats", datetime.utcnow())
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_cleanup_table_executes_for_listed_table(bot, db):
    """Listed table → DELETE fires."""
    from datetime import datetime
    s = _service(bot, db)
    cutoff = datetime(2026, 4, 1)
    await s._cleanup_table("server_status_history", cutoff)
    db.execute.assert_awaited_once()
    args, _ = db.execute.await_args
    sql, params = args[0], args[1]
    assert "DELETE FROM server_status_history" in sql
    assert params == (cutoff,)


@pytest.mark.asyncio
async def test_cleanup_table_swallows_privilege_error_gracefully(bot, db):
    """If the DB user lacks DELETE privilege, the cleanup silently
    skips (logs a warning but doesn't crash). Pin so a misconfigured
    DB user doesn't break the cleanup loop forever."""
    from datetime import datetime
    db.execute = AsyncMock(side_effect=Exception("permission denied"))
    s = _service(bot, db)
    # Should NOT raise
    await s._cleanup_table("server_status_history", datetime.utcnow())


@pytest.mark.asyncio
async def test_cleanup_table_logs_other_errors_without_raising(bot, db):
    """Non-privilege errors are also caught — pin so cleanup loop
    keeps running after a transient DB hiccup."""
    from datetime import datetime
    db.execute = AsyncMock(side_effect=RuntimeError("connection lost"))
    s = _service(bot, db)
    await s._cleanup_table("server_status_history", datetime.utcnow())
    # No raise


# ---------------------------------------------------------------------------
# _is_insufficient_privilege_error — postgres error classification
# ---------------------------------------------------------------------------


def test_is_privilege_error_matches_class_name():
    """asyncpg uses class `InsufficientPrivilegeError` — pin
    case-insensitive match."""
    class InsufficientPrivilegeError(Exception):
        pass
    err = InsufficientPrivilegeError("nope")
    assert MonitoringService._is_insufficient_privilege_error(err) is True


def test_is_privilege_error_matches_must_be_owner_message():
    err = Exception("ERROR:  must be owner of table foo")
    assert MonitoringService._is_insufficient_privilege_error(err) is True


def test_is_privilege_error_matches_permission_denied_message():
    err = Exception("permission denied for table foo")
    assert MonitoringService._is_insufficient_privilege_error(err) is True


def test_is_privilege_error_case_insensitive():
    """Various casings of the error message all match."""
    assert MonitoringService._is_insufficient_privilege_error(
        Exception("PERMISSION DENIED")
    ) is True
    assert MonitoringService._is_insufficient_privilege_error(
        Exception("Must Be Owner Of Table xyz")
    ) is True


def test_is_privilege_error_returns_false_for_unrelated():
    """Non-privilege errors → False (so the caller logs them as real
    errors instead of silently swallowing)."""
    assert MonitoringService._is_insufficient_privilege_error(
        Exception("connection refused")
    ) is False
    assert MonitoringService._is_insufficient_privilege_error(
        ValueError("bad value")
    ) is False
    assert MonitoringService._is_insufficient_privilege_error(
        TimeoutError("slow query")
    ) is False


# ---------------------------------------------------------------------------
# stop() — task lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_cancels_all_tasks(bot, db):
    """Stop awaits cancellation of all 3 task references. Pin so a
    bot reload doesn't leak the tasks."""
    import asyncio
    s = _service(bot, db)

    async def _waiter():
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            raise

    s.server_task = asyncio.create_task(_waiter())
    s.voice_task = asyncio.create_task(_waiter())
    s.cleanup_task = asyncio.create_task(_waiter())

    await s.stop()

    assert s.server_task.cancelled()
    assert s.voice_task.cancelled()
    assert s.cleanup_task.cancelled()


@pytest.mark.asyncio
async def test_stop_handles_missing_tasks_gracefully(bot, db):
    """If tasks were never started → stop is a no-op (NOT a crash)."""
    s = _service(bot, db)
    # All None — should not raise
    await s.stop()
