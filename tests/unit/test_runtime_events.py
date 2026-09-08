"""Journal contract and canonical importer wiring without a database."""
# ruff: noqa: SLF001 -- exercise canonical importer internals without live I/O.

from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.runtime_events import emit_round_stats_imported, event_stream_enabled


def connection(round_number=1):
    conn = MagicMock()
    conn.is_in_transaction.return_value = True
    conn.fetchrow = AsyncMock(return_value={
        "round_number": round_number, "gaming_session_id": 42,
    })
    conn.fetchval = AsyncMock(return_value=17)
    conn.execute = AsyncMock()
    return conn


async def emit(conn, **overrides):
    args = dict(enabled=True, round_id=3, source_filename="fixture-round-1.txt",
                source_payload_sha256="a" * 64, validation_passed=True)
    args.update(overrides)
    return await emit_round_stats_imported(conn, **args)


@pytest.mark.parametrize("value,expected", [
    (None, False), ("false", False), ("true", True), (" TRUE ", True),
    ("1", False), ("yes", False), ("", False),
])
def test_explicit_opt_in(monkeypatch, value, expected):
    monkeypatch.delenv("EVENT_STREAM_ENABLED", raising=False)
    if value is not None:
        monkeypatch.setenv("EVENT_STREAM_ENABLED", value)
    assert event_stream_enabled() is expected


async def test_disabled_needs_no_connection_or_migration():
    assert await emit(None, enabled=False) is None


async def test_requires_existing_transaction():
    conn = connection()
    conn.is_in_transaction.return_value = False
    with pytest.raises(RuntimeError, match="canonical import transaction"):
        await emit(conn)
    conn.fetchrow.assert_not_awaited()


@pytest.mark.parametrize("round_number", [0, None, 3])
async def test_excludes_non_halves(round_number):
    conn = connection(round_number)
    assert await emit(conn) is None
    conn.fetchval.assert_not_awaited()
    conn.execute.assert_not_awaited()


@pytest.mark.parametrize("round_number", [1, 2])
async def test_metadata_and_id_only_notification(round_number):
    conn = connection(round_number)
    assert await emit(conn, validation_passed=False) == 17
    assert conn.fetchval.call_args.args[1:] == (
        3, round_number, 42, "fixture-round-1.txt", "a" * 64, False,
    )
    conn.execute.assert_awaited_once_with("SELECT pg_notify('round_events', $1)", "17")


async def test_duplicate_does_not_notify():
    conn = connection()
    conn.fetchval.return_value = None
    assert await emit(conn) is None
    conn.execute.assert_not_awaited()


async def test_missing_round_is_not_silent_success():
    conn = connection()
    conn.fetchrow.return_value = None
    with pytest.raises(ValueError, match="missing round"):
        await emit(conn)


@pytest.mark.parametrize("operation", ["fetchval", "execute"])
async def test_event_errors_propagate(operation):
    conn = connection()
    getattr(conn, operation).side_effect = RuntimeError("journal unavailable")
    with pytest.raises(RuntimeError, match="journal unavailable"):
        await emit(conn)


@pytest.mark.parametrize("failure", [None, "event", "commit"])
async def test_canonical_import_transaction(monkeypatch, failure):
    import postgresql_database_manager as module

    manager = object.__new__(module.PostgreSQLDatabaseManager)
    manager.event_stream_enabled = True
    manager.stats = dict.fromkeys([
        "files_processed", "files_skipped", "files_failed", "rounds_created",
        "players_inserted", "weapons_inserted",
    ], 0)
    manager.parser = MagicMock()
    manager.parser.parse_stats_file.return_value = {"players": [], "round_num": 2}
    manager._compute_file_hashes = MagicMock(return_value=("b" * 64, "a" * 64))
    manager._extract_date_time_from_filename = MagicMock(return_value=("2026-09-08", "120000"))
    for name, result in [
        ("is_file_processed", False), ("find_processed_by_hash", None),
        ("_create_round_postgresql", 3), ("_insert_player_stats", 0),
        ("_insert_weapon_stats", 0), ("_validate_round_data", (True, "ok")),
    ]:
        setattr(manager, name, AsyncMock(return_value=result))
    state = []
    event_fails = failure is not None
    conn = connection()

    @asynccontextmanager
    async def transaction():
        state.append("begin")
        try:
            yield
            if failure == "commit":
                raise RuntimeError("journal unavailable")
        except Exception:
            state.append("rollback")
            raise
        else:
            state.append("commit")

    @asynccontextmanager
    async def acquire():
        yield conn

    async def marker(*args, **kwargs):
        assert state[-1] == ("rollback" if event_fails else "commit")
        assert kwargs["success"] is not event_fails

    async def emitter(actual_conn, **kwargs):
        assert actual_conn is conn and state == ["begin"]
        manager._validate_round_data.assert_awaited_once()
        assert kwargs["enabled"] is True
        assert kwargs["round_id"] == 3
        if failure == "event":
            raise RuntimeError("journal unavailable")

    manager.mark_file_processed = AsyncMock(side_effect=marker)
    conn.transaction = transaction
    manager.pool = MagicMock()
    manager.pool.acquire = acquire
    monkeypatch.setattr(module, "emit_round_stats_imported", emitter)
    success, message = await manager.process_file(Path("fixture-round-2.txt"))
    assert success is not event_fails
    assert state == ["begin", "rollback" if event_fails else "commit"]
    if event_fails:
        assert message == "journal unavailable"
        assert manager.stats["files_processed"] == 0
    manager.mark_file_processed.assert_awaited_once()
