"""Actual directory discovery through paced queue and independent PG observation."""

from tests.integration.test_proximity_source_pg import (
    assert_no_linked_import,
    linked_import,  # noqa: F401
)
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401
from tests.integration.test_runtime_proximity_retry_pg import GENERATION, prepare


async def test_bad_generation_does_not_starve_discovered_pg_import(linked_import, tmp_path):  # noqa: F811
    writer, observer, controls, entered, release, run = linked_import
    directory, digest = prepare(tmp_path)
    (tmp_path / ('0' * 32)).write_text('not a directory')
    first = await run(batch_now=1000, batch_size=1)
    assert first.items[0].result.reason == 'admission_unavailable'
    assert (first.discovery.entries_seen, first.discovery.ignored_entries, first.discovery.total_generations) == (3, 1, 2)
    second = await run(batch_now=1000, batch_after=first.discovery.next_cursor, batch_size=1)
    assert second.items[0].generation == GENERATION
    assert second.items[0].result.reason == 'parent_missing'
    await assert_no_linked_import(observer)
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (10,1,20,'fixture',1789794600)")
    third = await run(batch_now=1030, batch_after=second.discovery.next_cursor, batch_size=2)
    assert [item.result.reason for item in third.items] == ['admission_unavailable', 'matching_strict_receipt_visible']
    assert third.items[1].result.action == 'committed'
    assert await observer.fetchval('SELECT count(*) FROM proof_child') == 1
    assert [tuple(row) for row in await observer.fetch('SELECT * FROM proof_child')] == [(1, 10)]
    assert await observer.fetchval('SELECT file_hash FROM proximity_processed_files') == digest
    assert len(list(directory.glob('.proximity-attempt-*.json'))) == 2
    print('Batch PG proof: malformed first candidate reported, cursor reaches valid '
          'generation, pending parent then committed; 1 child/receipt, ignored file counted')
