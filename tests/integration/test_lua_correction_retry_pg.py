"""Durable bounded repair state on disposable PostgreSQL, no live worker."""

import subprocess
from pathlib import Path

import asyncpg
import pytest

from bot.services.lua_correction_inbox import lock_correction_identity, retain_lua_correction
from bot.services.lua_correction_retry import run_next_lua_correction_attempt, seed_lua_correction_attempts
from bot.services.lua_correction_service import apply_retained_lua_correction
from tests.integration.test_lua_correction_repair_pg import repair_db  # noqa: F401
from tests.integration.test_lua_override_boundary_pg import adapter_for, correction_db, metadata  # noqa: F401
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401


@pytest.fixture
async def retry_db(repair_db, monkeypatch):  # noqa: F811
    for key in ("EVENT_STREAM_ENABLED", "LUA_CORRECTION_EVENTS_ENABLED", "LUA_CORRECTION_REPAIR_ENABLED"):
        monkeypatch.setenv(key, "true")
    monkeypatch.setenv("LUA_CORRECTION_SOURCE_KEY", "one")
    writer, reader = repair_db
    migration = Path(__file__).resolve().parents[2] / "migrations/090_lua_correction_attempts.sql"
    await writer.execute(migration.read_text())
    return writer, reader


async def enqueue(conn, **changes):
    input_id = await retain_lua_correction(adapter_for(conn), "one", metadata() | changes)
    await seed_lua_correction_attempts(adapter_for(conn))
    return input_id


@pytest.mark.parametrize("off", ["EVENT_STREAM_ENABLED", "LUA_CORRECTION_EVENTS_ENABLED", "LUA_CORRECTION_REPAIR_ENABLED"])
async def test_disabled_never_accesses_db(monkeypatch, off):
    for key in ("EVENT_STREAM_ENABLED", "LUA_CORRECTION_EVENTS_ENABLED", "LUA_CORRECTION_REPAIR_ENABLED"):
        monkeypatch.setenv(key, "true")
    monkeypatch.setenv(off, "false")
    assert await seed_lua_correction_attempts(None) == []
    assert await run_next_lua_correction_attempt(None) == "disabled"


async def test_success_commits_receipt_and_attempt(retry_db):
    writer, reader = retry_db
    input_id = await enqueue(writer)
    assert await seed_lua_correction_attempts(adapter_for(reader)) == []
    assert await run_next_lua_correction_attempt(adapter_for(writer)) == "applied"
    assert tuple(await reader.fetchrow("SELECT attempts,outcome,terminal FROM lua_correction_attempts")) == (1, "applied", True)
    assert await reader.fetchval("SELECT input_id FROM lua_correction_receipts") == input_id
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == len(await reader.fetch("SELECT * FROM runtime_events")) == 1
    assert await run_next_lua_correction_attempt(adapter_for(reader)) == "idle"
    assert await writer.fetchval("SHOW lock_timeout") == "0"


async def test_missing_target_does_not_starve_later_valid_input(retry_db):
    writer, reader = retry_db
    missing = await enqueue(writer, map_name="missing")
    await enqueue(writer)
    assert await run_next_lua_correction_attempt(adapter_for(writer)) == "missing_round"
    assert await run_next_lua_correction_attempt(adapter_for(reader)) == "applied"
    state = await reader.fetchrow("SELECT attempts,terminal,next_due_at>clock_timestamp() FROM lua_correction_attempts WHERE input_id=$1", missing)
    assert tuple(state) == (1, False, True)


async def test_retry_budget_survives_new_adapters(retry_db):
    writer, reader = retry_db
    await enqueue(writer, map_name="missing")
    for attempt in range(1, 6):
        await writer.execute("UPDATE lua_correction_attempts SET next_due_at=clock_timestamp()")
        assert await run_next_lua_correction_attempt(adapter_for(reader)) == "missing_round"
        assert tuple(await writer.fetchrow("SELECT attempts,terminal FROM lua_correction_attempts")) == (attempt, attempt == 5)
    assert await run_next_lua_correction_attempt(adapter_for(writer)) == "idle"


async def test_late_target_is_repaired_after_durable_delay(retry_db):
    writer, reader = retry_db
    await enqueue(writer)
    await writer.execute("UPDATE rounds SET round_start_unix=NULL")
    assert await run_next_lua_correction_attempt(adapter_for(writer)) == "missing_round"
    assert await run_next_lua_correction_attempt(adapter_for(reader)) == "idle"
    await writer.execute("UPDATE rounds SET round_start_unix=1700000000")
    await writer.execute("UPDATE lua_correction_attempts SET next_due_at=clock_timestamp()")
    assert await run_next_lua_correction_attempt(adapter_for(reader)) == "applied"
    assert tuple(await writer.fetchrow("SELECT attempts,terminal FROM lua_correction_attempts")) == (2, True)


async def test_late_committing_lower_id_is_not_lost(retry_db):
    writer, reader = retry_db
    async with writer.transaction():
        earlier = await retain_lua_correction(adapter_for(writer), "one", metadata() | {"map_name": "missing"})
        later = await retain_lua_correction(adapter_for(reader), "one", metadata())
        assert later > earlier
        assert await seed_lua_correction_attempts(adapter_for(reader)) == [later]
    assert await seed_lua_correction_attempts(adapter_for(reader)) == [earlier]
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_attempts") == len(await reader.fetch("SELECT * FROM lua_correction_attempts")) == 2


async def test_failed_attempt_state_rolls_back_correction_and_receipt(retry_db):
    writer, reader = retry_db
    await enqueue(writer)
    await writer.execute("ALTER TABLE lua_correction_attempts ADD CONSTRAINT fixture_failure CHECK(outcome!='applied')")
    with pytest.raises(asyncpg.CheckViolationError, match="fixture_failure"):
        await run_next_lua_correction_attempt(adapter_for(writer))
    assert await reader.fetchval("SELECT actual_duration_seconds FROM rounds WHERE id=42") == 1800
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 0
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_receipts") == 0
    assert tuple(await reader.fetchrow("SELECT attempts,outcome FROM lua_correction_attempts")) == (0, "pending")


async def test_database_error_rolls_back_savepoint_before_recording_retry(retry_db):
    writer, reader = retry_db
    await enqueue(writer)
    await writer.execute("ALTER TABLE lua_correction_receipts ADD CONSTRAINT fixture_failure CHECK(false)")
    assert await run_next_lua_correction_attempt(adapter_for(writer)) == "database_error"
    assert await reader.fetchval("SELECT actual_duration_seconds FROM rounds WHERE id=42") == 1800
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 0
    assert tuple(await reader.fetchrow("SELECT attempts,outcome,terminal FROM lua_correction_attempts")) == (1, "database_error", False)


async def test_corrupt_input_is_quarantined_before_identity_lock(retry_db):
    writer, reader = retry_db
    await enqueue(writer)
    await writer.execute("UPDATE lua_correction_inputs SET payload_digest=repeat('0',64)")
    assert await run_next_lua_correction_attempt(adapter_for(writer)) == "rejected"
    assert await reader.fetchval("SELECT terminal FROM lua_correction_attempts")
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_receipts") == 0


async def test_identity_lock_contention_defers_without_consuming_budget(retry_db):
    writer, reader = retry_db
    await enqueue(writer)
    async with reader.transaction():
        await lock_correction_identity(adapter_for(reader), "one", metadata())
        assert await run_next_lua_correction_attempt(adapter_for(writer)) == "contended"
    assert tuple(await reader.fetchrow("SELECT attempts,outcome,terminal,next_due_at>clock_timestamp() FROM lua_correction_attempts")) == (0, "contended", False, True)
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 0
    assert await writer.fetchval("SHOW lock_timeout") == "0"


async def test_locked_attempt_is_skipped_not_a_global_queue_lock(retry_db):
    writer, reader = retry_db
    first = await enqueue(writer, map_name="missing")
    await enqueue(writer)
    async with reader.transaction():
        await reader.fetchrow("SELECT * FROM lua_correction_attempts WHERE input_id=$1 FOR UPDATE", first)
        assert await run_next_lua_correction_attempt(adapter_for(writer)) == "applied"
    assert await reader.fetchval("SELECT attempts FROM lua_correction_attempts WHERE input_id=$1", first) == 0


async def test_source_isolation(retry_db):
    writer, reader = retry_db
    await retain_lua_correction(adapter_for(writer), "other", metadata())
    assert await seed_lua_correction_attempts(adapter_for(writer)) == []
    assert await run_next_lua_correction_attempt(adapter_for(reader)) == "idle"
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_attempts") == 0


async def test_direct_completion_is_not_reseeded(retry_db):
    writer, reader = retry_db
    input_id = await retain_lua_correction(adapter_for(writer), "one", metadata())
    assert await apply_retained_lua_correction(adapter_for(writer), "one", input_id) == "applied"
    assert await seed_lua_correction_attempts(adapter_for(reader)) == []


async def test_direct_completion_after_seeding_is_idempotent(retry_db):
    writer, reader = retry_db
    input_id = await enqueue(writer)
    assert await apply_retained_lua_correction(adapter_for(reader), "one", input_id) == "applied"
    assert await run_next_lua_correction_attempt(adapter_for(writer)) == "already_applied"
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 1
    assert await reader.fetchval("SELECT terminal FROM lua_correction_attempts")


@pytest.mark.parametrize("conflict", ["ambiguous_round", "conflicting_revision"])
async def test_conflicts_are_quarantined_without_correction(retry_db, conflict):
    writer, reader = retry_db
    input_id = await enqueue(writer)
    if conflict == "ambiguous_round":
        await writer.execute("INSERT INTO rounds(id,round_number,map_name,round_start_unix) VALUES(43,1,'fixture',1700000000)")
    else:
        await retain_lua_correction(adapter_for(writer), "one", metadata() | {"actual_duration_seconds": 300})
    assert await run_next_lua_correction_attempt(adapter_for(writer)) == conflict
    assert await reader.fetchval("SELECT terminal FROM lua_correction_attempts WHERE input_id=$1", input_id)
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_receipts") == 0


async def test_seed_batch_is_bounded_without_losing_remainder(retry_db):
    writer, reader = retry_db
    for offset in range(107):
        await retain_lua_correction(adapter_for(writer), "one", metadata() | {"round_start_unix": 1700000000 + offset})
    first = await seed_lua_correction_attempts(adapter_for(writer))
    second = await seed_lua_correction_attempts(adapter_for(reader))
    assert len(first) == 100
    assert len(second) == 7
    assert set(first).isdisjoint(second)
    assert await seed_lua_correction_attempts(adapter_for(writer)) == []
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_attempts") == len(await reader.fetch("SELECT * FROM lua_correction_attempts")) == 107


async def test_unexpected_error_defers_then_surfaces_without_starvation(retry_db, monkeypatch):
    writer, reader = retry_db
    first = await enqueue(writer, map_name="missing")
    await enqueue(writer)

    async def failing(adapter, source, input_id):
        if input_id == first:
            raise RuntimeError("fixture unexpected error")
        return await apply_retained_lua_correction(adapter, source, input_id)

    monkeypatch.setattr("bot.services.lua_correction_retry.apply_retained_lua_correction", failing)
    with pytest.raises(RuntimeError, match="fixture unexpected error"):
        await run_next_lua_correction_attempt(adapter_for(writer))
    assert tuple(await reader.fetchrow("SELECT attempts,outcome,next_due_at>clock_timestamp() FROM lua_correction_attempts WHERE input_id=$1", first)) == (1, "unexpected_error", True)
    assert await run_next_lua_correction_attempt(adapter_for(reader)) == "applied"


def test_migration_registered_and_bootstrap_mirrored():
    root = Path(__file__).resolve().parents[2]
    name = "090_lua_correction_attempts.sql"
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; printf "%s\\n" "${MIGRATIONS[@]}"',
         "release-config", str(root / "scripts/release_configs/v1.45.0.sh")],
        check=True, capture_output=True, text=True, timeout=5,
    )
    assert name in result.stdout.splitlines()
    assert (root / "migrations" / name).read_text().strip() in (root / "tools/schema_postgresql.sql").read_text()
