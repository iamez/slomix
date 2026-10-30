"""Two real connections distinguish returned success from committed receipts."""

import pytest

from shared.runtime_proximity_commit import inspect_proximity_commit
from tests.integration.test_proximity_source_pg import linked_import  # noqa: F401
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401
from tests.integration.test_runtime_proximity_retry_pg import GENERATION, prepare


async def test_commit_visibility_rollback_and_provenance(linked_import, tmp_path):  # noqa: F811
    writer, reader, controls, entered, release, run = linked_import
    directory, digest = prepare(tmp_path)

    async def observe(conn=reader):
        return await inspect_proximity_commit(directory, source_id='fixture-server',
                                              generation=GENERATION, observer=conn)

    assert (await observe()).status == 'not_committed'
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (10,1,20,'fixture',1789794600)")
    for commit in (False, True):
        outer = writer.transaction()
        await outer.start()
        try:
            assert (await run(admission_directory=directory)).import_result.success
            assert (await observe()).status == 'not_committed'
            assert await reader.fetchval('SELECT count(*) FROM proof_child') == 0
            with pytest.raises(RuntimeError, match='outside any transaction'):
                await observe(writer)
        finally:
            if commit:
                await outer.commit()
            else:
                await outer.rollback()
        assert (await observe()).status == ('committed' if commit else 'not_committed')
    assert await reader.fetchval('SELECT file_hash FROM proximity_processed_files') == digest
    assert await reader.fetchval('SELECT count(*) FROM proof_child') == 1
    assert [tuple(row) for row in await reader.fetch('SELECT * FROM proof_child')] == [(1, 10)]
    # Never trust a prior observation after database mutation/restore.
    await writer.execute('UPDATE proximity_processed_files SET linked_round_id=NULL')
    assert (await observe()).reason == 'strict_provenance_missing'
    await writer.execute('UPDATE proximity_processed_files SET runtime_parent_gate=FALSE')
    assert (await observe()).reason == 'strict_provenance_missing'
    print('Commit proof: writer success invisible to observer; rollback stays absent; '
          'commit exposes strict digest receipt +1 child; writer transaction rejected; '
          'later provenance change is detected, no persistent completion marker')
