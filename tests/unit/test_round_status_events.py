"""Contracts for the opt-in restart-status producer."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.round_status_events import mark_round_restart, status_events_enabled


@pytest.mark.parametrize("global_flag,local_flag,expected", [
    (None, None, False), ("false", "true", False), ("true", None, False),
    ("true", "false", False), ("true", " TRUE ", True), ("true", "1", False),
])
def test_status_requires_both_flags(monkeypatch, global_flag, local_flag, expected):
    for key, value in (("EVENT_STREAM_ENABLED", global_flag), ("ROUND_STATUS_EVENTS_ENABLED", local_flag)):
        monkeypatch.delenv(key, raising=False)
        if value is not None:
            monkeypatch.setenv(key, value)
    assert status_events_enabled() is expected


async def test_transaction_required_before_any_write():
    conn = SimpleNamespace(is_in_transaction=lambda: False, fetchrow=AsyncMock())
    with pytest.raises(RuntimeError, match="canonical import transaction"):
        await mark_round_restart(conn, round_id=1, status="cancelled", caused_by_round_id=2)
    conn.fetchrow.assert_not_awaited()


@pytest.mark.parametrize("status,cause", [("completed", 2), ("cancelled", 1)])
async def test_invalid_transition_rejected(status, cause):
    conn = SimpleNamespace(is_in_transaction=lambda: True, fetchrow=AsyncMock())
    with pytest.raises(ValueError):
        await mark_round_restart(conn, round_id=1, status=status, caused_by_round_id=cause)
    conn.fetchrow.assert_not_awaited()


@pytest.mark.parametrize("enabled", [False, True])
async def test_detector_failure_propagates_only_when_enabled(monkeypatch, enabled):
    import postgresql_database_manager as module

    monkeypatch.setattr(module, "status_events_enabled", lambda: enabled)
    conn = SimpleNamespace(fetch=AsyncMock(side_effect=RuntimeError("injected detection failure")))
    call = module.PostgreSQLDatabaseManager._detect_and_mark_restarts(  # noqa: SLF001
        MagicMock(), conn, 2, 42, "fixture", 1, "2026-09-14", "120200",
    )
    if enabled:
        with pytest.raises(RuntimeError, match="injected detection failure"):
            await call
    else:
        await call


def test_bootstrap_and_release_include_status_migration():
    root = Path(__file__).resolve().parents[2]
    name = "085_runtime_status_events.sql"
    assert (root / "migrations" / name).read_text().strip() in (root / "tools/schema_postgresql.sql").read_text()
    assert name in (root / "scripts/release_configs/v1.45.0.sh").read_text()


async def test_enabled_detector_preserves_complete_match(monkeypatch):
    import postgresql_database_manager as module

    monkeypatch.setattr(module, "status_events_enabled", lambda: True)
    emitter = AsyncMock()
    monkeypatch.setattr(module, "mark_round_restart", emitter)
    conn = SimpleNamespace(fetch=AsyncMock(return_value=[{
        "id": 1, "round_date": "2026-09-14", "round_time": "120000", "match_id": "paired",
    }]), fetchval=AsyncMock(return_value=1), execute=AsyncMock())
    manager = object.__new__(module.PostgreSQLDatabaseManager)
    await manager._detect_and_mark_restarts(conn, 2, 42, "fixture", 1, "2026-09-14", "120200")  # noqa: SLF001
    emitter.assert_not_awaited()
    conn.execute.assert_not_awaited()


async def test_create_round_returns_failure_when_detector_raises():
    from postgresql_database_manager import PostgreSQLDatabaseManager

    manager = object.__new__(PostgreSQLDatabaseManager)
    manager.config = SimpleNamespace(excluded_maps=set())
    manager._get_or_create_gaming_session_id = AsyncMock(return_value=42)  # noqa: SLF001
    manager._detect_and_mark_restarts = AsyncMock(side_effect=RuntimeError("journal rejected"))  # noqa: SLF001
    conn = SimpleNamespace(fetchval=AsyncMock(return_value=2))
    result = await manager._create_round_postgresql(  # noqa: SLF001
        conn, {"players": [], "map_name": "fixture"}, "2026-09-14", "120200", "fixture-round-1.txt",
    )
    assert result is None  # process_file must reject this inside its transaction
    manager._detect_and_mark_restarts.assert_awaited_once()  # noqa: SLF001
