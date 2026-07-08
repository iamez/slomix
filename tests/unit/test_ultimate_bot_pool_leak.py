"""process_gamestats_file's fallback DB-manager pool must never leak.

When the bot has no existing db_adapter.pool to reuse, it creates its own
PostgreSQLDatabaseManager, connects, then migrates before writing. If
migrate_schema() raises, the pool it just opened must still be closed —
previously disconnect() was only reached on the happy path (codex
follow-up audit finding).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from bot.ultimate_bot import UltimateETLegacyBot


def _bare_bot():
    bot = UltimateETLegacyBot.__new__(UltimateETLegacyBot)

    class Cfg:
        database_type = "postgresql"

    bot.config = Cfg()
    bot.track_error = AsyncMock()
    # no db_adapter attribute at all -> hasattr(self, 'db_adapter') is False
    # -> created_own_pool must be True (the fallback-pool scenario)
    return bot


class FakeManager:
    disconnect_calls = 0

    def __init__(self, *a, **kw):
        pass

    async def connect(self):
        return None

    async def migrate_schema(self):
        raise RuntimeError("simulated migration failure")

    async def disconnect(self):
        FakeManager.disconnect_calls += 1

    async def process_file(self, *a, **kw):
        raise AssertionError("must not reach process_file if migrate_schema raised")


@pytest.mark.asyncio
async def test_migrate_failure_still_disconnects_own_pool():
    FakeManager.disconnect_calls = 0
    bot = _bare_bot()

    with patch("postgresql_database_manager.PostgreSQLDatabaseManager", FakeManager):
        result = await bot.process_gamestats_file("/tmp/fake.txt", "fake.txt")

    assert FakeManager.disconnect_calls == 1
    assert result["success"] is False
    assert "simulated migration failure" in result["error"]
