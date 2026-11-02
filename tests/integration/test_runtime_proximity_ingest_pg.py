"""Real PG composition of completion gating, strict parent wait and replay.

Uses canonical parser identity/receipt transactions with a minimal injected child
table, not the full analytics schema. Never starts a DB or accesses application
credentials. Fixture cleans only its unique disposable test schema.
"""

import asyncio
import hashlib
import json
from datetime import date

import pytest

from shared.runtime_completion_manifest import record_proximity_completion_once
from shared.runtime_proximity_admission import publish_proximity_admission
from shared.runtime_source_reservation import reserve_source_generation
from shared.runtime_spool import publish_proximity_file
from tests.integration.test_proximity_source_pg import (
    assert_no_linked_import,
    linked_import,  # noqa: F401
)
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401


def record_source(tmp_path):
    source, = tmp_path.glob('*_engagements.txt')
    payload = source.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    receipt = dict(version=1, filename=source.name, bytes=len(payload), state='writer_closed')
    assert record_proximity_completion_once(tmp_path, receipt, expected_sha256=digest) == 'published'
    return source, digest


def snapshot(tmp_path):
    return {p.name: (p.stat().st_ino, p.read_bytes()) for p in tmp_path.iterdir()}


async def test_completion_then_parent_then_session_then_replay(linked_import, tmp_path):  # noqa: F811
    writer, observer, controls, entered, release, run = linked_import
    outcome = await run(manifest_gated=True)
    assert outcome.manifest_status == 'missing_manifest' and outcome.import_result is None
    await assert_no_linked_import(observer)
    source, digest = record_source(tmp_path)
    before = snapshot(tmp_path)
    result = await run(manifest_gated=True)
    assert result.manifest_status == 'match' and result.import_result.pending_reason == 'parent_missing'
    await assert_no_linked_import(observer)
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (10,1,NULL,' FIXTURE ',1789794600)")
    assert (await run(manifest_gated=True)).import_result.pending_reason == 'session_missing'
    await assert_no_linked_import(observer)
    await writer.execute('UPDATE rounds SET gaming_session_id=20 WHERE id=10')
    for _ in range(2):
        outcome = await run(manifest_gated=True)
        result = outcome.import_result
        assert outcome.manifest_status == 'match' and result.success
        assert (result.round_id, result.gaming_session_id) == (10, 20)
        assert await observer.fetchval('SELECT count(*) FROM proof_child') == 1
        assert [tuple(r) for r in await observer.fetch('SELECT * FROM proof_child')] == [(1, 10)]
        assert await observer.fetchval('SELECT count(*) FROM proximity_processed_files') == 1
        assert tuple(await observer.fetchrow('SELECT filename,file_hash,runtime_parent_gate,aggregates_applied FROM proximity_processed_files')) == (source.name, digest, True, True)
    assert snapshot(tmp_path) == before
    print('PG manifest ingestion proof: missing receipt -> parent_missing -> session_missing '
          '-> imported -> replay; independently observed 1 child/1 strict receipt, local files unchanged')


async def test_cancel_after_child_write_retains_completion_for_retry(linked_import, tmp_path):  # noqa: F811
    writer, observer, controls, entered, release, run = linked_import
    record_source(tmp_path)
    before = snapshot(tmp_path)
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (10,1,20,'fixture',1789794600)")
    controls['failure'] = 'cancel'
    with pytest.raises(asyncio.CancelledError):
        await run(manifest_gated=True)
    await assert_no_linked_import(observer)
    assert snapshot(tmp_path) == before
    controls['failure'] = None
    assert (await run(manifest_gated=True)).import_result.success
    assert await observer.fetchval('SELECT count(*) FROM proof_child') == 1
    assert snapshot(tmp_path) == before


async def test_ambiguous_parent_is_not_selected_or_acknowledged(linked_import, tmp_path):  # noqa: F811
    writer, observer, controls, entered, release, run = linked_import
    record_source(tmp_path)
    before = snapshot(tmp_path)
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (10,1,20,'fixture',1789794600),(11,1,21,'fixture',1789794600)")
    result = await run(manifest_gated=True)
    assert result.manifest_status == 'match' and result.import_result.pending_reason == 'parent_ambiguous'
    await assert_no_linked_import(observer)
    assert snapshot(tmp_path) == before


async def test_self_consistent_other_source_cannot_replace_trusted_identity(linked_import, tmp_path):  # noqa: F811
    writer, observer, controls, entered, release, run = linked_import
    source, digest = record_source(tmp_path)
    source.write_bytes(source.read_bytes().replace(b'fixture', b'changed'))
    manifest = tmp_path / (source.name + '.complete.json')
    data = json.loads(manifest.read_text())
    data['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    assert data['sha256'] != digest
    manifest.write_text(json.dumps(data))
    before = snapshot(tmp_path)
    result = await run(manifest_gated=True)
    assert result.manifest_status == 'receipt_conflict' and result.import_result is None
    await assert_no_linked_import(observer)
    assert snapshot(tmp_path) == before


async def test_outer_rollback_is_not_a_durable_import_ack(linked_import, tmp_path):  # noqa: F811
    writer, observer, controls, entered, release, run = linked_import
    record_source(tmp_path)
    before = snapshot(tmp_path)
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (10,1,20,'fixture',1789794600)")
    transaction = writer.transaction()
    await transaction.start()
    try:
        assert (await run(manifest_gated=True)).import_result.success
        assert await writer.fetchval('SELECT count(*) FROM proof_child') == 1
        await assert_no_linked_import(observer)
    finally:
        await transaction.rollback()
    await assert_no_linked_import(observer)
    assert snapshot(tmp_path) == before
    assert (await run(manifest_gated=True)).import_result.success
    assert await observer.fetchval('SELECT count(*) FROM proof_child') == 1


async def test_persisted_admission_drives_strict_import_without_rediscovering_identity(linked_import, tmp_path):  # noqa: F811
    writer, observer, controls, entered, release, run = linked_import
    source, = tmp_path.glob('*_engagements.txt')
    payload = source.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    generation = '0123456789abcdef' * 2
    directory = reserve_source_generation(tmp_path, generation)
    assert await run(admission_directory=directory) is None
    await assert_no_linked_import(observer)
    completion = dict(version=1, filename=source.name, bytes=len(payload), state='writer_closed')
    publish_proximity_admission(directory, source_id='fixture-server', generation=generation,
        completion=completion, expected_sha256=digest, session_date=date(2026, 9, 19))
    assert (await run(admission_directory=directory)).manifest_status == 'missing_manifest'
    await assert_no_linked_import(observer)
    publish_proximity_file(directory, source.name, [payload], expected_size=len(payload), expected_sha256=digest)
    record_proximity_completion_once(directory, completion, expected_sha256=digest)
    before = snapshot(directory)
    assert (await run(admission_directory=directory)).import_result.pending_reason == 'parent_missing'
    await assert_no_linked_import(observer)
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (10,1,20,'fixture',1789794600)")
    for _ in range(2):
        result = await run(admission_directory=directory)
        assert result.import_result.success and result.import_result.gaming_session_id == 20
        assert await observer.fetchval('SELECT count(*) FROM proof_child') == 1
        assert [tuple(r) for r in await observer.fetch('SELECT * FROM proof_child')] == [(1, 10)]
        assert await observer.fetchval('SELECT count(*) FROM proximity_processed_files') == 1
        assert await observer.fetchval('SELECT file_hash FROM proximity_processed_files') == digest
    assert snapshot(directory) == before
    # Corrupt BOTH payload and completion: retained admission still pins the
    # earlier trusted hash rather than adopting these now-self-consistent bytes.
    captured = directory / source.name
    captured.write_bytes(payload.replace(b'fixture', b'changed'))
    manifest = directory / (source.name + '.complete.json')
    data = json.loads(manifest.read_text())
    data['sha256'] = hashlib.sha256(captured.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(data))
    assert (await run(admission_directory=directory)).manifest_status == 'receipt_conflict'
    assert await observer.fetchval('SELECT file_hash FROM proximity_processed_files') == digest
    print('Admission-to-PG proof: retained identity -> waiting capture -> waiting parent '
          '-> strict import/replay 1 child/1 receipt; payload+completion tamper not adopted')
