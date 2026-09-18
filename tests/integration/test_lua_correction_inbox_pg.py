"""Synthetic input retention proofs; no live intake or repair worker."""

import asyncio
import json
from pathlib import Path

import pytest

from bot.services.lua_correction_inbox import normalize_correction_input, retain_lua_correction
from bot.services.webhook_round_metadata_service import WebhookRoundMetadataService
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
