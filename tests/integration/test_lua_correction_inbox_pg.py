"""Synthetic input retention proofs; no live intake or repair worker."""
# ruff: noqa: SLF001 -- exercise real private intake boundaries with fixture-only state

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, mock_open

import pytest

from bot.services.lua_correction_inbox import (
    normalize_correction_input,
    retain_lua_correction,
    retain_lua_correction_if_enabled,
)
from bot.services.stats_ready_mixin import _StatsReadyMixin
from bot.services.webhook_round_metadata_service import WebhookRoundMetadataService
from bot.ultimate_bot import UltimateETLegacyBot
from tests.integration.test_lua_override_boundary_pg import adapter_for, metadata
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401


@pytest.fixture
async def inbox_db(journal_db):  # noqa: F811
    writer, reader = journal_db
    sql = Path(__file__).resolve().parents[2] / "migrations/088_lua_correction_inputs.sql"
    await writer.execute(sql.read_text())
    return writer, reader


async def test_retained_after_new_adapter_and_duplicate_does_not_overwrite(inbox_db):
    writer, reader = inbox_db
    payload = metadata() | {"map_name": " FIXTURE ", "axis_players": ["private"], "token": "discard"}
    first = await retain_lua_correction(adapter_for(writer), "fixture-server", payload)
    row = await reader.fetchrow("SELECT * FROM lua_correction_inputs WHERE id=$1", first)
    assert json.loads(row["payload"]) == metadata()
    again = await retain_lua_correction(adapter_for(reader), "fixture-server", metadata())
    assert again == first
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_inputs") == 1
    assert len(await reader.fetch("SELECT * FROM lua_correction_inputs")) == 1
    assert await reader.fetchval("SELECT received_at FROM lua_correction_inputs") == row["received_at"]


async def test_distinct_revisions_and_sources_are_retained(inbox_db):
    writer, reader = inbox_db
    ids = [await retain_lua_correction(adapter_for(writer), source, payload) for source, payload in (
        ("one", metadata()), ("one", metadata() | {"actual_duration_seconds": 700}), ("two", metadata()),
    )]
    assert len(set(ids)) == 3
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_inputs") == 3


async def test_outer_rollback_leaves_no_receipt(inbox_db):
    writer, reader = inbox_db
    adapter = adapter_for(writer)
    with pytest.raises(RuntimeError, match="fixture abort"):
        async with adapter.transaction():
            await retain_lua_correction(adapter, "one", metadata())
            assert await reader.fetchval("SELECT count(*) FROM lua_correction_inputs") == 0
            raise RuntimeError("fixture abort")
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_inputs") == 0


async def test_concurrent_duplicate_waits_for_commit(inbox_db):
    writer, reader = inbox_db
    adapter = adapter_for(writer)
    task = None
    try:
        async with adapter.transaction():
            first = await retain_lua_correction(adapter, "one", metadata())
            task = asyncio.create_task(retain_lua_correction(adapter_for(reader), "one", metadata()))
            for _ in range(100):
                wait_type = await writer.fetchval(
                    "SELECT wait_event_type FROM pg_stat_activity WHERE pid=$1", reader.get_server_pid(),
                )
                if wait_type == "Lock":
                    break
                await asyncio.sleep(0.01)
            assert wait_type == "Lock"
            assert not task.done()
        assert await asyncio.wait_for(task, 2) == first
        assert await reader.fetchval("SELECT count(*) FROM lua_correction_inputs") == 1
    finally:
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_digest_conflict_refuses_receipt(inbox_db):
    writer, _ = inbox_db
    adapter = adapter_for(writer)
    await retain_lua_correction(adapter, "one", metadata())
    # Simulate corrupted storage; never silently ACK a mismatched receipt.
    await writer.execute("UPDATE lua_correction_inputs SET payload='{}'::jsonb")
    with pytest.raises(ValueError, match="digest conflict"):
        await retain_lua_correction(adapter, "one", metadata())


@pytest.mark.parametrize("raw_reason,expected", [("timelimit", "NORMAL"), ("surrender", "SURRENDER")])
async def test_real_producer_normalized_payload_is_retained(inbox_db, raw_reason, expected):
    writer, reader = inbox_db
    payload = WebhookRoundMetadataService().build_round_metadata_from_map({
        "map": "fixture", "round": 1, "winner": 2,
        "lua_roundstart": 1700000000, "lua_roundend": 1700000600,
        "lua_playtime": "600 sec", "lua_endreason": raw_reason,
    })
    row_id = await retain_lua_correction(adapter_for(writer), "one", payload)
    stored = json.loads(await reader.fetchval("SELECT payload FROM lua_correction_inputs WHERE id=$1", row_id))
    assert stored["end_reason"] == expected
    assert stored["actual_duration_seconds"] == 600
    assert "end_reason_raw" not in stored


@pytest.mark.parametrize("raw", [{}, {"lua_playtime": "bad", "lua_pauses": "bad"}])
async def test_producer_missing_or_invalid_measurements_do_not_become_zero_corrections(inbox_db, raw):
    writer, reader = inbox_db
    payload = WebhookRoundMetadataService().build_round_metadata_from_map({
        "map": "fixture", "round": 1, "lua_roundstart": 1700000000, "winner": 2, **raw,
    })
    assert payload["actual_duration_seconds"] == 0  # Legacy presentation unchanged.
    row_id = await retain_lua_correction(adapter_for(writer), "one", payload)
    stored = json.loads(await reader.fetchval("SELECT payload FROM lua_correction_inputs WHERE id=$1", row_id))
    assert stored == {"map_name": "fixture", "round_number": 1, "round_start_unix": 1700000000, "winner_team": 2}


def test_explicit_zero_measurements_are_retained_but_zero_end_is_not():
    payload = WebhookRoundMetadataService().build_round_metadata_from_map({
        "map": "fixture", "round": 1, "lua_roundstart": 1700000000,
        "lua_playtime": "0 sec", "lua_pauses": "0 (0 sec)",
    })
    stored = normalize_correction_input(payload)
    assert stored["actual_duration_seconds"] == 0
    assert stored["total_pause_seconds"] == 0
    assert stored["pause_count"] == 0
    assert "round_end_unix" not in stored
    assert "round_end_unix" not in normalize_correction_input(metadata() | {"round_end_unix": 0})


def test_missing_producer_map_rejected():
    payload = WebhookRoundMetadataService().build_round_metadata_from_map({
        "round": 1, "lua_roundstart": 1700000000,
    })
    with pytest.raises(ValueError, match="map"):
        normalize_correction_input(payload)


@pytest.mark.parametrize("raw_reason", [None, "", "unknown", "garbage"])
def test_fallback_end_reason_is_not_a_measurement(raw_reason):
    payload = WebhookRoundMetadataService().build_round_metadata_from_map({
        "map": "fixture", "round": 1, "lua_roundstart": 1700000000, "lua_endreason": raw_reason,
    })
    assert payload["end_reason"] == "NORMAL"
    assert "end_reason" not in normalize_correction_input(payload)


@pytest.mark.parametrize("key,value", [
    ("round_start_unix", 0), ("round_start_unix", True), ("round_number", 0),
    ("round_number", 1.5), ("actual_duration_seconds", float("nan")),
    ("actual_duration_seconds", -1), ("actual_duration_seconds", 2**31),
    ("actual_duration_seconds", "600"), ("pause_count", None),
    ("winner_team", 3), ("round_end_unix", 1), ("map_name", "../fixture"),
    ("end_reason", "private text with spaces"), ("round_end_unix", False),
    ("map_name", " UNKNOWN "),
])
async def test_invalid_input_fails_before_database(key, value):
    with pytest.raises(ValueError):
        await retain_lua_correction(None, "one", metadata() | {key: value})


def test_partial_payload_and_integral_values():
    payload = {"map_name": "fixture", "round_number": 1.0, "round_start_unix": 1700000000.0}
    assert normalize_correction_input(payload) == {
        "map_name": "fixture", "round_number": 1, "round_start_unix": 1700000000,
    }


@pytest.mark.parametrize("source", [None, "", "../server", "server token", "x" * 65])
async def test_invalid_source_rejected_before_database(source):
    with pytest.raises(ValueError, match="source identity"):
        await retain_lua_correction(None, source, metadata())


async def test_integral_float_and_integer_share_receipt(inbox_db):
    writer, reader = inbox_db
    first = await retain_lua_correction(adapter_for(writer), "one", metadata())
    second = await retain_lua_correction(adapter_for(reader), "one", metadata() | {
        "round_number": 1.0, "round_start_unix": 1700000000.0, "actual_duration_seconds": 600.0,
    })
    assert first == second


def test_bootstrap_and_release_registration():
    root = Path(__file__).resolve().parents[2]
    sql = (root / "migrations/088_lua_correction_inputs.sql").read_text().strip()
    assert sql in (root / "tools/schema_postgresql.sql").read_text()
    assert '"088_lua_correction_inputs.sql"' in (root / "scripts/release_configs/v1.45.0.sh").read_text()


def intake_bot(adapter):
    service = WebhookRoundMetadataService()
    raw = {"map": "fixture", "round": 1, "lua_roundstart": 1700000000, "lua_playtime": "600 sec"}
    return SimpleNamespace(
        db_adapter=adapter,
        _fields_to_metadata_map=lambda fields: raw,
        _build_round_metadata_from_map=service.build_round_metadata_from_map,
        _parse_spawn_stats_from_metadata=lambda fields: [],
        _resolve_team_display_names=lambda primary, players: "fixture",
        _queue_pending_metadata=Mock(),
        webhook_event_queue=SimpleNamespace(enqueue=Mock(return_value=(False, "queue_full"))),
        track_error=AsyncMock(),
        _store_lua_round_teams=AsyncMock(side_effect=RuntimeError("fixture later failure")),
    )


@pytest.mark.parametrize("enabled", [False, True])
async def test_stats_ready_retains_before_queue_refusal(inbox_db, monkeypatch, enabled):
    writer, reader = inbox_db
    monkeypatch.setenv("LUA_CORRECTION_INBOX_ENABLED", str(enabled).lower())
    monkeypatch.setenv("LUA_CORRECTION_SOURCE_KEY", "fixture-server")
    bot = intake_bot(adapter_for(writer))
    message = SimpleNamespace(embeds=[SimpleNamespace(fields=[], footer=None)])
    await _StatsReadyMixin._process_stats_ready_webhook(bot, message)
    bot._queue_pending_metadata.assert_called_once()
    bot.webhook_event_queue.enqueue.assert_called_once()
    bot.track_error.assert_not_awaited()
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_inputs") == int(enabled)


async def test_stats_ready_storage_failure_prevents_volatile_dispatch(inbox_db, monkeypatch):
    writer, _ = inbox_db
    monkeypatch.setenv("LUA_CORRECTION_INBOX_ENABLED", "true")
    monkeypatch.setenv("LUA_CORRECTION_SOURCE_KEY", "fixture-server")
    await writer.execute("ALTER TABLE lua_correction_inputs ADD CONSTRAINT fixture_no_input CHECK(false)")
    bot = intake_bot(adapter_for(writer))
    await _StatsReadyMixin._process_stats_ready_webhook(
        bot, SimpleNamespace(embeds=[SimpleNamespace(fields=[], footer=None)]),
    )
    bot._queue_pending_metadata.assert_not_called()
    bot.webhook_event_queue.enqueue.assert_not_called()
    bot.track_error.assert_awaited_once()


async def test_stats_ready_receipt_survives_queue_exception(inbox_db, monkeypatch):
    writer, reader = inbox_db
    monkeypatch.setenv("LUA_CORRECTION_INBOX_ENABLED", "true")
    monkeypatch.setenv("LUA_CORRECTION_SOURCE_KEY", "fixture-server")
    bot = intake_bot(adapter_for(writer))
    bot.webhook_event_queue.enqueue.side_effect = RuntimeError("fixture queue exception")
    await _StatsReadyMixin._process_stats_ready_webhook(
        bot, SimpleNamespace(embeds=[SimpleNamespace(fields=[], footer=None)]),
    )
    bot.track_error.assert_awaited_once()
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_inputs") == 1


async def test_gametime_retained_before_team_storage_failure(inbox_db, monkeypatch):
    writer, reader = inbox_db
    monkeypatch.setenv("LUA_CORRECTION_INBOX_ENABLED", "true")
    monkeypatch.setenv("LUA_CORRECTION_SOURCE_KEY", "fixture-server")
    bot = intake_bot(adapter_for(writer))
    file_data = json.dumps({"payload": {"embeds": [{"fields": []}]}})
    monkeypatch.setattr("builtins.open", mock_open(read_data=file_data))
    with pytest.raises(RuntimeError, match="fixture later failure"):
        await UltimateETLegacyBot._process_gametimes_file(bot, "fixture.json", "fixture.json")
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_inputs") == 1
    bot._store_lua_round_teams.assert_awaited_once()
    bot._queue_pending_metadata.assert_not_called()


async def test_disabled_intake_needs_no_adapter_or_metadata(monkeypatch):
    monkeypatch.delenv("LUA_CORRECTION_INBOX_ENABLED", raising=False)
    assert await retain_lua_correction_if_enabled(None, None) is None


async def test_enabled_intake_requires_configured_source(monkeypatch):
    monkeypatch.setenv("LUA_CORRECTION_INBOX_ENABLED", "true")
    monkeypatch.delenv("LUA_CORRECTION_SOURCE_KEY", raising=False)
    with pytest.raises(ValueError, match="source identity"):
        await retain_lua_correction_if_enabled(None, metadata())


async def test_invalid_gametime_does_not_starve_later_valid_file(inbox_db, monkeypatch):
    writer, reader = inbox_db
    monkeypatch.setenv("LUA_CORRECTION_INBOX_ENABLED", "true")
    monkeypatch.setenv("LUA_CORRECTION_SOURCE_KEY", "fixture-server")
    bot = intake_bot(adapter_for(writer))
    bot.config = SimpleNamespace(
        gametimes_enabled=True, ssh_host="fixture", ssh_port=22, ssh_user="fixture",
        ssh_key_path="fixture", gametimes_remote_path="fixture", gametimes_local_path="fixture",
        gametimes_startup_lookback_hours=0,
    )
    bot.ssh_enabled = True
    bot.processed_gametimes_files = set()
    bot._extract_gametime_timestamp = lambda name: 0
    bot._mark_gametime_processed = Mock()
    bot._fields_to_metadata_map = lambda fields: fields
    bot._store_lua_round_teams = AsyncMock(return_value=42)
    bot._fetch_latest_stats_file = AsyncMock()
    bot._process_gametimes_file = lambda path, name: UltimateETLegacyBot._process_gametimes_file(bot, path, name)
    names = ["gametime-1.json", "gametime-2.json"]
    monkeypatch.setattr("bot.ultimate_bot.SSHHandler.list_remote_files", AsyncMock(return_value=names))
    monkeypatch.setattr("bot.ultimate_bot.SSHHandler.download_file", AsyncMock(side_effect=names))
    documents = {name: json.dumps({"payload": {"embeds": [{"fields": {
        "map": "fixture", "round": 1, "lua_roundstart": start, "lua_playtime": "600 sec",
    }}]}}) for name, start in zip(names, [0, 1700000000])}
    monkeypatch.setattr("builtins.open", lambda path, **kwargs: mock_open(read_data=documents[path])())
    await UltimateETLegacyBot._process_remote_gametimes_files(bot)
    bot._mark_gametime_processed.assert_called_once_with(names[1])
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_inputs") == 1
