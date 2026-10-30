"""Queue outcomes against real PG; prior success must not hide restored absence."""

import json

from tests.integration.test_proximity_source_pg import (
    assert_no_linked_import,
    linked_import,  # noqa: F401
)
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401
from tests.integration.test_runtime_proximity_retry_pg import prepare


async def test_queue_restart_rollback_and_restored_receipt_absence(linked_import, tmp_path):  # noqa: F811
    writer, observer, controls, entered, release, run = linked_import
    directory, digest = prepare(tmp_path)
    original = {p.name: p.read_bytes() for p in directory.iterdir()}
    first = await run(admission_directory=directory, queue_now=1000)
    assert (first.action, first.reason) == ('retry', 'parent_missing')
    assert (await run(admission_directory=directory, queue_now=1029)).reason == 'not_due'
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (10,1,20,'fixture',1789794600)")
    outer = writer.transaction()
    await outer.start()
    try:
        result = await run(admission_directory=directory, queue_now=1030)
        assert (result.action, result.reason) == ('retry', 'receipt_not_visible')
        await assert_no_linked_import(observer)
    finally:
        await outer.rollback()
    assert (await run(admission_directory=directory, queue_now=1090)).action == 'committed'
    before = len(list(directory.glob('.proximity-attempt-*.json')))
    assert (await run(admission_directory=directory, queue_now=2000)).action == 'committed'
    assert len(list(directory.glob('.proximity-attempt-*.json'))) == before == 3
    # Model a receipt table restored to an earlier empty state. Keep the old
    # table and its rows: this test does not delete original evidence.
    await writer.execute('ALTER TABLE proximity_processed_files RENAME TO retained_receipts')
    await writer.execute('CREATE TABLE proximity_processed_files (LIKE retained_receipts INCLUDING ALL)')
    recovered = await run(admission_directory=directory, queue_now=2000)
    assert recovered.action == 'committed' and recovered.attempt == 4
    assert await observer.fetchval('SELECT count(*) FROM proof_child') == 1
    assert [tuple(r) for r in await observer.fetch('SELECT * FROM proof_child')] == [(1, 10)]
    assert await observer.fetchval('SELECT file_hash FROM proximity_processed_files') == digest
    assert {name: (directory / name).read_bytes() for name in original} == original
    actions = [json.loads(p.read_text())['action'] for p in sorted(directory.glob('.proximity-outcome-*.json'))]
    assert actions == ['retry', 'retry', 'committed', 'committed']
    print('Queue PG proof: pending/cooldown -> uncommitted success/rollback -> committed '
          '-> no replay -> restored receipt absence triggers paced reimport, 1 child retained')
