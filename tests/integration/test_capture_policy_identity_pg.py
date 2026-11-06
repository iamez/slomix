"""Legacy epoch association must not claim ownership when canonical rounds collide."""
import json

import asyncpg
import pytest

from tests.integration.test_runtime_events_pg import connection_options
from website.backend.services.round_web_service import load_capture_policy

EPOCH = 1791280000
MANIFEST = {
    "source": "declared", "position_sample_interval_ms": 200,
    "capabilities": {"shot_fired": "enabled"},
    "event_time_basis": {"status": "declared", "value": "level_time_offset_v1"},
}


@pytest.fixture
async def identity_db():
    conn = await asyncpg.connect(**connection_options())
    try:
        await conn.execute("SET search_path=pg_temp")
        await conn.execute("""CREATE TEMP TABLE rounds(
            id INT PRIMARY KEY, map_name TEXT, round_number INT, round_start_unix BIGINT)""")
        await conn.execute("""CREATE TEMP TABLE proximity_processed_files(
            filename TEXT PRIMARY KEY, round_key TEXT, capabilities JSONB,
            linked_round_id INT REFERENCES rounds(id))""")

        class Adapter:
            async def fetch_all(self, sql, params):
                return await conn.fetch(sql, *params)

        yield conn, Adapter()
    finally:
        await conn.close()


async def insert_receipt(conn, name, epoch, manifest=MANIFEST, *, half=1, linked_round_id=None):
    await conn.execute("INSERT INTO proximity_processed_files VALUES($1,$2,$3,$4)",
                       name, f"2026-10-06|supply|{half}|{epoch}",
                       json.dumps(manifest) if manifest is not None else None, linked_round_id)


@pytest.mark.parametrize("other_map,other_half", [("oasis", 1), ("supply", 2), ("supply", 1)])
@pytest.mark.parametrize("receipt_count", [1, 2])
async def test_colliding_rounds_never_borrow_even_identical_manifest(identity_db, other_map,
                                                                   other_half, receipt_count):
    conn, adapter = identity_db
    await conn.execute("INSERT INTO rounds VALUES(1,'supply',1,$1),(2,$2,$3,$1)",
                       EPOCH, other_map, other_half)
    for index in range(receipt_count):
        await insert_receipt(conn, f"source-{index}.txt", EPOCH)
    # Independent counts: conflict is in canonical rounds, not differing metadata.
    assert await conn.fetchval("SELECT count(*) FROM rounds WHERE round_start_unix=$1", EPOCH) == 2
    assert await conn.fetchval("SELECT count(*) FROM proximity_processed_files") == receipt_count
    for round_id in (1, 2):
        policy = await load_capture_policy(adapter, round_id)
        assert policy.event_time_basis is None
        assert policy.observation_interval_ms is None
        assert policy.manifest_count == 0
        assert set(policy.capabilities.values()) == {"unknown"}
    print(f"IDENTITY PROOF: 2 canonical rounds/{receipt_count} receipts -> both unknown")


@pytest.mark.parametrize("malformed", [None, {}, [], "not-json"])
async def test_unique_epochs_retain_legacy_key_compatibility_and_missing_siblings(identity_db, malformed):
    conn, adapter = identity_db
    await conn.execute("INSERT INTO rounds VALUES(1,'supply',1,$1),(2,'supply',2,$2)", EPOCH, EPOCH+600)
    # Historical parser normalized some key half numbers differently. Uniqueness
    # is a conservative guard, NOT a claim of exact whole-key/source ownership.
    await insert_receipt(conn, "old-normalization.txt", EPOCH, half=0)
    await insert_receipt(conn, "second.txt", EPOCH+600, half=2)
    for round_id in (1, 2):
        policy = await load_capture_policy(adapter, round_id)
        assert policy.event_time_basis == "level_time_offset_v1"
        assert policy.observation_interval_ms == 200
        assert policy.capabilities["shot_fired"] == "enabled"
    await insert_receipt(conn, "sibling.txt", EPOCH, malformed)
    assert (await load_capture_policy(adapter, 1)).event_time_basis is None
    assert (await load_capture_policy(adapter, 2)).event_time_basis == "level_time_offset_v1"
    print("IDENTITY PROOF: distinct epochs preserved; absent sibling still blocks agreement")


@pytest.mark.parametrize("epoch", [None, 0, -1])
async def test_missing_identity_never_inherits_matching_text(identity_db, epoch):
    conn, adapter = identity_db
    await conn.execute("INSERT INTO rounds VALUES(1,'supply',1,$1)", epoch)
    await insert_receipt(conn, "invalid.txt", epoch)
    policy = await load_capture_policy(adapter, 1)
    assert policy.event_time_basis is None
    assert policy.observation_interval_ms is None
    assert policy.manifest_count == 0


async def test_explicit_links_separate_colliding_rounds(identity_db):
    conn, adapter = identity_db
    await conn.execute("INSERT INTO rounds VALUES(1,'supply',1,$1),(2,'oasis',1,$1)", EPOCH)
    different = {**MANIFEST, "position_sample_interval_ms": 500,
                 "capabilities": {"shot_fired": "disabled"}}
    await insert_receipt(conn, "first.txt", EPOCH, linked_round_id=1)
    await insert_receipt(conn, "second.txt", EPOCH, different, linked_round_id=2)
    for round_id, cadence, state in [(1, 200, "enabled"), (2, 500, "disabled")]:
        policy = await load_capture_policy(adapter, round_id)
        assert policy.observation_interval_ms == cadence
        assert policy.capabilities["shot_fired"] == state
        assert policy.event_time_basis == "level_time_offset_v1"
        assert policy.manifest_count == 1
        assert await conn.fetchval('SELECT count(*) FROM proximity_processed_files WHERE linked_round_id=$1', round_id) == 1
    print("LINKED READER PROOF: equal epoch, separate file ownership, independent policies")


@pytest.mark.parametrize("ambiguous", [False, True])
@pytest.mark.parametrize("sibling", [MANIFEST, None])
async def test_unlinked_sibling_cannot_disappear_beside_explicit_link(identity_db, ambiguous, sibling):
    conn, adapter = identity_db
    await conn.execute("INSERT INTO rounds VALUES(1,'supply',1,$1)", EPOCH)
    if ambiguous:
        await conn.execute("INSERT INTO rounds VALUES(2,'oasis',1,$1)", EPOCH)
    await insert_receipt(conn, "bound.txt", EPOCH, linked_round_id=1)
    await insert_receipt(conn, "legacy.txt", EPOCH, sibling)
    policy = await load_capture_policy(adapter, 1)
    known = not ambiguous and sibling is not None
    assert policy.event_time_basis == ("level_time_offset_v1" if known else None)
    assert policy.observation_interval_ms == (200 if known else None)
    assert policy.capabilities["shot_fired"] == ("enabled" if known else "unknown")
    if ambiguous:
        # Identical declaration cannot resolve ownership of the legacy sibling.
        other = await load_capture_policy(adapter, 2)
        assert other.manifest_count == 0 and other.event_time_basis is None


@pytest.mark.parametrize("epoch", [None, 0, EPOCH + 600])
async def test_explicit_link_survives_parent_metadata_edits_without_leaking(identity_db, epoch):
    conn, adapter = identity_db
    await conn.execute("INSERT INTO rounds VALUES(1,'supply',1,$1),(2,'oasis',1,$2)", epoch, EPOCH)
    await insert_receipt(conn, "bound.txt", EPOCH, linked_round_id=1)
    assert (await load_capture_policy(adapter, 1)).event_time_basis == "level_time_offset_v1"
    # The old key's epoch happens to match round2; never fall back for a bound file.
    assert (await load_capture_policy(adapter, 2)).manifest_count == 0


async def test_null_bound_manifest_blocks_its_round_only(identity_db):
    conn, adapter = identity_db
    await conn.execute("INSERT INTO rounds VALUES(1,'supply',1,$1),(2,'oasis',1,$1)", EPOCH)
    await insert_receipt(conn, "good.txt", EPOCH, linked_round_id=1)
    await insert_receipt(conn, "missing.txt", EPOCH, None, linked_round_id=1)
    await insert_receipt(conn, "other.txt", EPOCH, linked_round_id=2)
    assert (await load_capture_policy(adapter, 1)).event_time_basis is None
    assert (await load_capture_policy(adapter, 2)).event_time_basis == "level_time_offset_v1"
