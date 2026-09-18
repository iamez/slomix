"""Real entry/storage proof on the explicitly isolated runtime test cluster."""

from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.services.endstats_pipeline_mixin import _EndstatsPipelineMixin
from bot.services.webhook_handler_mixin import _WebhookHandlerMixin
from shared.endstats_retry import endstats_filename_gate_query
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401


class EntryBot(_EndstatsPipelineMixin, _WebhookHandlerMixin):
    pass


@pytest.fixture
async def endstats_db(journal_db):  # noqa: F811
    writer, reader = journal_db
    await writer.execute("""
        CREATE TABLE processed_endstats_files (
            id SERIAL PRIMARY KEY, filename TEXT UNIQUE, round_id INTEGER,
            success BOOLEAN, error_message TEXT, processed_at TIMESTAMPTZ
        );
        CREATE TABLE round_awards (
            round_id INTEGER, round_date TEXT, map_name TEXT, round_number INTEGER,
            award_name TEXT, player_name TEXT, player_guid TEXT,
            award_value TEXT, award_value_numeric NUMERIC
        );
        CREATE TABLE round_vs_stats (round_id INTEGER);
        CREATE TABLE player_aliases (alias TEXT, guid TEXT, last_seen TIMESTAMPTZ);
    """)
    return writer, reader


@pytest.mark.parametrize("success,error,retryable", [
    (False, "publish_failed", True), (True, "publish_failed", False),
    (None, "publish_failed", False), (False, None, False),
    (False, "", False), (False, "unknown", False),
    (False, "duplicate_round_skip_existing:other", False),
    (False, "superseded_by_richer_payload:other", False),
    (False, "round_id_unresolved_after_5_attempts", False),
    (False, "publish_retry_exhausted", False),
])
@pytest.mark.parametrize("enabled", [False, True])
async def test_gate_preserves_terminal_and_unknown_states(endstats_db, monkeypatch, success, error, retryable, enabled):
    writer, _ = endstats_db
    monkeypatch.setenv("ENDSTATS_RETRY_ENABLED", str(enabled).lower())
    await writer.execute("INSERT INTO processed_endstats_files(filename,success,error_message) VALUES ('fixture',$1,$2)", success, error)
    blocked = bool(await writer.fetchval(endstats_filename_gate_query(), "fixture"))
    assert blocked is not (enabled and retryable)
    assert await writer.fetchval(endstats_filename_gate_query(), "absent") is None


@pytest.mark.parametrize("permanent", [False, True])
@pytest.mark.parametrize("storage_failure", [False, True])
async def test_polling_retries_committed_publication_failure(endstats_db, monkeypatch, permanent, storage_failure):
    writer, reader = endstats_db
    monkeypatch.setenv("ENDSTATS_RETRY_ENABLED", "true")
    payload = {"metadata": {"date": "2026-09-15", "time": "120000", "map_name": "fixture", "round_number": 1},
               "awards": [{"name": "Fixture award", "player": "fixture", "value": "1", "numeric": 1}], "vs_stats": []}
    monkeypatch.setattr("bot.endstats_parser.parse_endstats_file", lambda path: payload)

    @asynccontextmanager
    async def transaction():
        async with writer.transaction():
            yield writer

    async def fetch_one(query, params=()):
        return await writer.fetchrow(query, *params)

    async def execute(query, params=()):
        return await writer.execute(query, *params)

    bot = object.__new__(EntryBot)
    bot.config = SimpleNamespace(STARTUP_LOOKBACK_HOURS=168)
    bot.bot_startup_time = datetime(2026, 9, 15, 13)  # noqa: DTZ001 -- filename clock is local-naive
    bot.db_adapter = SimpleNamespace(transaction=transaction, fetch_one=fetch_one, execute=execute)
    bot.processed_endstats_files = set()
    bot.endstats_retry_counts = {}
    bot.endstats_retry_tasks = {}
    bot.endstats_retry_max_attempts = 3
    bot.track_error = AsyncMock()
    bot._resolve_endstats_round_id = AsyncMock(return_value=(1, "fixture"))  # noqa: SLF001
    bot._is_endstats_round_already_processed = AsyncMock(return_value=False)  # noqa: SLF001
    bot._is_endstats_round_ready = AsyncMock(return_value=True)  # noqa: SLF001
    bot._select_richest_endstats = lambda data, path, name, *args: (data, path, name)  # noqa: SLF001
    attempts = []

    async def publish(*args):
        # Second connection proves actual storage committed before publication.
        assert await reader.fetchval("SELECT count(*) FROM round_awards") == 1
        assert len(await reader.fetch("SELECT * FROM round_awards")) == 1
        attempts.append(args[0])
        return not permanent and len(attempts) > 1

    bot.round_publisher = SimpleNamespace(publish_endstats=publish)
    filename = "2026-09-15-120000-fixture-round-1-endstats.txt"
    if storage_failure:
        await writer.execute("ALTER TABLE round_awards ADD CONSTRAINT reject_fixture CHECK (award_name <> 'Fixture award')")
        assert await bot._should_process_endstats_file(filename)  # noqa: SLF001
        await bot._process_endstats_file(filename, filename)  # noqa: SLF001
        assert attempts == []
        assert filename not in bot.processed_endstats_files
        assert await reader.fetchval("SELECT count(*) FROM processed_endstats_files") == 0
        assert await reader.fetch("SELECT * FROM round_awards") == []
        bot.track_error.assert_awaited_once()
        bot.track_error.reset_mock()
        await writer.execute("ALTER TABLE round_awards DROP CONSTRAINT reject_fixture")
    assert await bot._should_process_endstats_file(filename)  # noqa: SLF001
    await bot._process_endstats_file(filename, filename)  # noqa: SLF001
    assert await reader.fetchval("SELECT error_message FROM processed_endstats_files") == "publish_failed"
    assert filename not in bot.processed_endstats_files
    expected = 3 if permanent else 2
    for _ in range(expected - 1):
        assert await bot._should_process_endstats_file(filename)  # noqa: SLF001
        await bot._process_endstats_file(filename, filename)  # noqa: SLF001
    assert len(attempts) == expected
    assert await reader.fetchval("SELECT success FROM processed_endstats_files") is (not permanent)
    if permanent:
        assert await reader.fetchval("SELECT error_message FROM processed_endstats_files") == "publish_retry_exhausted"
    bot.processed_endstats_files.clear()  # Persisted success/exhaustion, not RAM, blocks next poll.
    assert not await bot._should_process_endstats_file(filename)  # noqa: SLF001
    await bot._process_endstats_file(filename, filename)  # noqa: SLF001
    assert len(attempts) == expected
    assert await reader.fetchval("SELECT count(*) FROM processed_endstats_files") == 1
    assert len(await reader.fetch("SELECT * FROM processed_endstats_files")) == 1
    bot.track_error.assert_not_awaited()
    print(f"R02c1 runtime proof: {expected} publication attempts; persisted success/exhaustion blocks another poll")
