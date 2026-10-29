"""Dispatcher decisions remain transaction-scoped in an isolated PG schema."""

from tests.integration.test_proximity_source_pg import (
    assert_no_linked_import,
    linked_import,  # noqa: F401
)
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401
from tests.integration.test_runtime_proximity_retry_pg import prepare


async def test_dispatch_waits_and_never_upgrades_outer_transaction(linked_import, tmp_path):  # noqa: F811
    writer, observer, controls, entered, release, run = linked_import
    directory, digest = prepare(tmp_path)
    first = await run(admission_directory=directory, dispatch_now=1000)
    assert (first.action, first.reason) == ('retry', 'parent_missing')
    await assert_no_linked_import(observer)
    wait = await run(admission_directory=directory, dispatch_now=1029)
    assert (wait.action, wait.reason) == ('deferred', 'not_due')
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (10,1,20,'fixture',1789794600)")
    outer = writer.transaction()
    await outer.start()
    try:
        observed = await run(admission_directory=directory, dispatch_now=1030)
        assert observed.action == 'verify_commit'
        assert observed.import_result.import_result.success
        await assert_no_linked_import(observer)
    finally:
        await outer.rollback()
    await assert_no_linked_import(observer)
    result = await run(admission_directory=directory, dispatch_now=1090)
    assert result.action == 'verify_commit' and result.permit.attempt == 3
    assert await observer.fetchval('SELECT count(*) FROM proof_child') == 1
    assert [tuple(row) for row in await observer.fetch('SELECT * FROM proof_child')] == [(1, 10)]
    assert await observer.fetchval('SELECT file_hash FROM proximity_processed_files') == digest
    print('Dispatch PG proof: retry -> deferred -> verify_commit with invisible '
          'outer transaction -> rollback -> due retry; 1 committed child/receipt')
