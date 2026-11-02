"""Local retry permits around canonical strict ingestion in disposable PG only."""

import asyncio
import hashlib
import json
from datetime import date

import pytest

from shared.runtime_completion_manifest import record_proximity_completion_once
from shared.runtime_proximity_admission import publish_proximity_admission
from shared.runtime_proximity_retry import reserve_proximity_retry
from shared.runtime_source_reservation import reserve_source_generation
from shared.runtime_spool import publish_proximity_file
from tests.integration.test_proximity_source_pg import (
    assert_no_linked_import,
    linked_import,  # noqa: F401
)
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401

GENERATION = 'abcdef0123456789' * 2


def prepare(tmp_path):
    source, = tmp_path.glob('*_engagements.txt')
    payload = source.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    directory = reserve_source_generation(tmp_path, GENERATION)
    completion = dict(version=1, filename=source.name, bytes=len(payload), state='writer_closed')
    publish_proximity_admission(directory, source_id='fixture-server', generation=GENERATION,
        completion=completion, expected_sha256=digest, session_date=date(2026, 9, 19))
    publish_proximity_file(directory, source.name, [payload], expected_size=len(payload), expected_sha256=digest)
    record_proximity_completion_once(directory, completion, expected_sha256=digest)
    return directory, digest


def reserve(directory, now):
    return reserve_proximity_retry(directory, source_id='fixture-server', generation=GENERATION, now=now)


async def test_pending_cancel_and_retry_are_paced_without_losing_source(linked_import, tmp_path):  # noqa: F811
    writer, observer, controls, entered, release, run = linked_import
    directory, digest = prepare(tmp_path)
    original = {p.name: p.read_bytes() for p in directory.iterdir()}
    with reserve(directory, 1000) as permit:
        assert permit.status == 'reserved'
        assert (await run(admission_directory=directory)).import_result.pending_reason == 'parent_missing'
        with reserve(directory, 9999) as competing:
            assert competing.status == 'busy'
    await assert_no_linked_import(observer)
    with reserve(directory, 1029) as permit:
        assert permit.status == 'not_due'
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (10,1,20,'fixture',1789794600)")
    controls['failure'] = 'cancel'
    with pytest.raises(asyncio.CancelledError), reserve(directory, 1030) as permit:
        assert permit.status == 'reserved' and permit.attempt == 2
        await run(admission_directory=directory)
    await assert_no_linked_import(observer)
    with reserve(directory, 1089) as permit:
        assert permit.status == 'not_due' and permit.attempt == 2
    controls['failure'] = None
    with reserve(directory, 1090) as permit:
        assert permit.status == 'reserved' and permit.attempt == 3
        assert (await run(admission_directory=directory)).import_result.success
    assert [tuple(row) for row in await observer.fetch('SELECT * FROM proof_child')] == [(1, 10)]
    assert await observer.fetchval('SELECT count(*) FROM proof_child') == 1
    assert await observer.fetchval('SELECT count(*) FROM proximity_processed_files') == 1
    assert await observer.fetchval('SELECT file_hash FROM proximity_processed_files') == digest
    assert {name: (directory / name).read_bytes() for name in original} == original
    assert [json.loads(p.read_text())['attempt'] for p in sorted(directory.glob('.proximity-attempt-*.json'))] == [1, 2, 3]
    print('Retry-to-PG proof: pending -> 30s wait -> cancelled/rolled-back attempt '
          '-> 60s wait -> strict import; 1 child/1 receipt independently observed; source retained')


async def test_outer_rollback_does_not_retire_retry_work(linked_import, tmp_path):  # noqa: F811
    writer, observer, controls, entered, release, run = linked_import
    directory, digest = prepare(tmp_path)
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (10,1,20,'fixture',1789794600)")
    with reserve(directory, 1000) as permit:
        assert permit.status == 'reserved'
        outer = writer.transaction()
        await outer.start()
        try:
            assert (await run(admission_directory=directory)).import_result.success
            await assert_no_linked_import(observer)
        finally:
            await outer.rollback()
    await assert_no_linked_import(observer)
    with reserve(directory, 1030) as permit:
        assert permit.status == 'reserved' and permit.attempt == 2
        assert (await run(admission_directory=directory)).import_result.success
    assert await observer.fetchval('SELECT file_hash FROM proximity_processed_files') == digest
