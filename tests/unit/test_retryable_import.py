"""A temporary transaction failure must remain eligible for the next poll."""
# ruff: noqa: SLF001 -- exercise the import boundary without network/startup.

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shared.import_result import RetryableImportFailure


def test_result_preserves_two_value_tuple_contract():
    result = RetryableImportFailure("transient")
    success, message = result
    assert (success, message) == (False, "transient")
    assert result == (False, "transient")
    assert isinstance(result, tuple) and result.retryable


@pytest.mark.parametrize("retryable", [False, True])
async def test_bot_does_not_terminal_mark_retryable_failure(monkeypatch, retryable):
    import postgresql_database_manager
    from bot.ultimate_bot import UltimateETLegacyBot

    result = RetryableImportFailure("transient") if retryable else (False, "bad header")
    manager = SimpleNamespace(process_file=AsyncMock(return_value=result))
    monkeypatch.setattr(postgresql_database_manager, "PostgreSQLDatabaseManager", lambda: manager)
    bot = UltimateETLegacyBot.__new__(UltimateETLegacyBot)
    bot.config = SimpleNamespace(database_type="postgresql")
    bot.db_adapter = SimpleNamespace(pool=object())
    bot.file_tracker = SimpleNamespace(mark_processed=AsyncMock())
    bot.processed_files = set()
    bot.track_error = AsyncMock()
    for _ in range(2):
        response = await bot.process_gamestats_file("/tmp/fixture.txt", "fixture.txt")
        assert response["success"] is False
    if retryable:
        assert response["retryable"] is True
        bot.file_tracker.mark_processed.assert_not_awaited()
        assert "fixture.txt" not in bot.processed_files
    else:
        assert bot.file_tracker.mark_processed.await_count == 2
        assert "fixture.txt" in bot.processed_files


@pytest.mark.parametrize("result,expected", [
    ({"success": False, "retryable": True}, False),
    ({"success": False}, False), ({"success": True}, True), (None, False),
])
async def test_optional_ssh_monitor_propagates_import_result(result, expected):
    from bot.services.automation.ssh_monitor import SSHMonitor

    monitor = object.__new__(SSHMonitor)
    monitor.bot = SimpleNamespace(process_gamestats_file=AsyncMock(return_value=result))
    assert await monitor._import_file_to_db("/tmp/fixture.txt", "fixture.txt") is expected
