"""DB-only repair attempts and atomic receipts, not a running worker."""

import asyncio
from pathlib import Path

import asyncpg
import pytest

from bot.services.lua_correction_inbox import retain_lua_correction
from bot.services.lua_correction_service import apply_retained_lua_correction
from tests.integration.test_lua_override_boundary_pg import adapter_for, correction_db, metadata  # noqa: F401
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401


@pytest.fixture
async def repair_db(correction_db):  # noqa: F811
    writer, reader = correction_db
    root = Path(__file__).resolve().parents[2]
    for migration in ("088_lua_correction_inputs.sql", "089_lua_correction_receipts.sql"):
        await writer.execute((root / "migrations" / migration).read_text())
    await writer.execute("UPDATE rounds SET round_start_unix=1700000000 WHERE id=42")
    return writer, reader


async def retained(writer):
    return await retain_lua_correction(adapter_for(writer), "one", metadata())


async def test_repair_and_duplicate_receipt(repair_db):
    writer, reader = repair_db
    input_id = await retained(writer)
    assert await apply_retained_lua_correction(adapter_for(writer), "one", input_id) == "applied"
    assert await apply_retained_lua_correction(adapter_for(reader), "one", input_id) == "already_applied"
    assert await reader.fetchval("SELECT dpm FROM player_comprehensive_stats") == 120
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 1
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_receipts") == 1
    assert len(await reader.fetch("SELECT * FROM lua_correction_receipts")) == 1


async def test_failed_receipt_rolls_back_correction_and_event(repair_db):
    writer, reader = repair_db
    input_id = await retained(writer)
    await writer.execute("ALTER TABLE lua_correction_receipts ADD CONSTRAINT fixture_failure CHECK(false)")
    with pytest.raises(asyncpg.CheckViolationError, match="fixture_failure"):
        await apply_retained_lua_correction(adapter_for(writer), "one", input_id)
    assert await reader.fetchval("SELECT actual_duration_seconds FROM rounds WHERE id=42") == 1800
    assert await reader.fetchval("SELECT dpm FROM player_comprehensive_stats") == 0
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 0
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_receipts") == 0
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_inputs") == 1


@pytest.mark.parametrize("case,expected", [
    ("wrong_source", "missing_input"), ("missing", "missing_round"),
    ("ambiguous", "ambiguous_round"), ("revision", "conflicting_revision"),
])
async def test_repair_refuses_unsafe_targets(repair_db, case, expected):
    writer, reader = repair_db
    input_id = await retained(writer)
    if case == "missing":
        await writer.execute("UPDATE rounds SET round_start_unix=NULL")
    if case == "ambiguous":
        await writer.execute("INSERT INTO rounds(id,map_name,round_number,round_start_unix) VALUES (43,'fixture',1,1700000000)")
    if case == "revision":
        await retain_lua_correction(adapter_for(writer), "one", metadata() | {"actual_duration_seconds": 700})
    assert await apply_retained_lua_correction(
        adapter_for(writer), "other" if case == "wrong_source" else "one", input_id,
    ) == expected
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_receipts") == 0
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 0


@pytest.mark.parametrize("column,value", [("map_name", "wrong"), ("payload_digest", "0" * 64), ("payload", '{}')])
async def test_corrupted_input_rejected(repair_db, column, value):
    writer, reader = repair_db
    input_id = await retained(writer)
    # Column names are fixture constants, never runtime input.
    await writer.execute(f"UPDATE lua_correction_inputs SET {column}=$1", value)
    with pytest.raises(ValueError):
        await apply_retained_lua_correction(adapter_for(writer), "one", input_id)
    assert await reader.fetchval("SELECT count(*) FROM runtime_events") == 0


@pytest.mark.parametrize("operation", ["revision", "duplicate"])
async def test_concurrent_revision_waits_for_completed_attempt(repair_db, operation):
    writer, reader = repair_db
    input_id = await retained(writer)
    adapter = adapter_for(writer)
    task = None
    try:
        async with adapter.transaction():
            assert await apply_retained_lua_correction(adapter, "one", input_id) == "applied"
            if operation == "revision":
                pending = retain_lua_correction(adapter_for(reader), "one", metadata() | {"actual_duration_seconds": 700})
            else:
                pending = apply_retained_lua_correction(adapter_for(reader), "one", input_id)
            task = asyncio.create_task(pending)
            for _ in range(100):
                wait = await writer.fetchval("SELECT wait_event_type FROM pg_stat_activity WHERE pid=$1", reader.get_server_pid())
                if wait == "Lock":
                    break
                await asyncio.sleep(0.01)
            assert wait == "Lock"
            assert not task.done()
        result = await asyncio.wait_for(task, 2)
        if operation == "revision":
            assert await apply_retained_lua_correction(adapter, "one", result) == "conflicting_revision"
        else:
            assert result == "already_applied"
        assert await reader.fetchval("SELECT count(*) FROM lua_correction_receipts") == 1
        assert await reader.fetchval("SELECT actual_duration_seconds FROM rounds WHERE id=42") == 600
    finally:
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_missing_round_remains_retryable(repair_db):
    writer, reader = repair_db
    input_id = await retained(writer)
    await writer.execute("UPDATE rounds SET round_start_unix=NULL")
    assert await apply_retained_lua_correction(adapter_for(writer), "one", input_id) == "missing_round"
    assert await reader.fetchval("SELECT count(*) FROM lua_correction_inputs") == 1
    await writer.execute("UPDATE rounds SET round_start_unix=1700000000")
    assert await apply_retained_lua_correction(adapter_for(reader), "one", input_id) == "applied"


@pytest.mark.parametrize("ambiguous", [False, True])
async def test_normalized_map_target_and_ambiguity(repair_db, ambiguous):
    writer, _ = repair_db
    input_id = await retained(writer)
    await writer.execute("UPDATE rounds SET map_name=' FIXTURE ' WHERE id=42")
    if ambiguous:
        await writer.execute("INSERT INTO rounds(id,map_name,round_number,round_start_unix) VALUES (43,'fixture',1,1700000000)")
    assert await apply_retained_lua_correction(adapter_for(writer), "one", input_id) == (
        "ambiguous_round" if ambiguous else "applied"
    )


@pytest.mark.parametrize("value", [True, False, 0, -1, "1", 1.5])
async def test_invalid_input_id_before_database(value):
    with pytest.raises(ValueError, match="input ID"):
        await apply_retained_lua_correction(None, "one", value)


def test_receipt_bootstrap_parity():
    root = Path(__file__).resolve().parents[2]
    sql = (root / "migrations/089_lua_correction_receipts.sql").read_text().strip()
    assert sql in (root / "tools/schema_postgresql.sql").read_text()
    assert '"089_lua_correction_receipts.sql"' in (root / "scripts/release_configs/v1.45.0.sh").read_text()
