"""Sealed timing sources + existing inbox, only in opt-in disposable PostgreSQL."""

import asyncio
import hashlib
import json
from pathlib import Path

import asyncpg
import pytest

from bot.core.database_adapter import PostgreSQLAdapter
from bot.runtime_gametime_retention import retain_gametime_source
from tests.integration.test_lua_override_boundary_pg import adapter_for
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401
from tests.integration.test_runtime_full_import_pg import full_import_db  # noqa: F401
from tests.integration.test_runtime_website_privileges_pg import (
    acl_db,  # noqa: F401
    default_acls,
    denied,
    execute_as_website,
    reachable_role,
)
from tests.unit.test_gametime_writer_io import lua, run_writer  # noqa: F401
from tests.unit.test_runtime_gametime_independence import run as run_full_webhook
from tests.unit.test_runtime_gametime_source import NAME, document

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / 'migrations/097_runtime_gametime_sources.sql'


@pytest.fixture
async def retention_db(journal_db):  # noqa: F811
    writer, reader = journal_db
    await writer.execute((ROOT / 'migrations/088_lua_correction_inputs.sql').read_text())
    await writer.execute(MIGRATION.read_text())
    return writer, reader


async def retain(adapter, tmp_path, *, raw=None, source_id='fixture-server', generation='a' * 32):
    raw = json.dumps(document()).encode() if raw is None else raw
    digest = hashlib.sha256(raw).hexdigest()
    path = tmp_path / digest
    # Identical bytes may be used concurrently; no descriptor content differs.
    if not path.exists():
        path.write_bytes(raw)
    with path.open('rb') as stream:
        return await retain_gametime_source(
            adapter, stream.fileno(), source_id=source_id, generation=generation,
            filename=NAME, expected_size=len(raw), expected_sha256=digest,
        )


async def counts(conn):
    return tuple(await conn.fetchrow('''SELECT
        (SELECT count(*) FROM lua_correction_inputs),
        (SELECT count(*) FROM runtime_gametime_sources)'''))


async def test_commit_restart_replay_and_independent_provenance(retention_db, tmp_path):
    writer, reader = retention_db
    raw = json.dumps(document()).encode()
    first = await retain(adapter_for(writer), tmp_path, raw=raw)
    row = await reader.fetchrow('SELECT * FROM runtime_gametime_sources')
    assert (row['source_key'], row['generation'], row['filename'], row['input_id']) == (
        first.source_id, first.generation, NAME, first.input_id,
    )
    assert (row['source_size'], row['source_sha256']) == (len(raw), hashlib.sha256(raw).hexdigest())
    payload = json.loads(await reader.fetchval('SELECT payload FROM lua_correction_inputs'))
    assert payload['actual_duration_seconds'] + payload['total_pause_seconds'] == 610
    assert payload['round_end_unix'] - payload['round_start_unix'] == 610
    assert await retain(adapter_for(reader), tmp_path, raw=raw) == first
    assert await reader.fetchval('SELECT retained_at FROM runtime_gametime_sources') == row['retained_at']
    assert await counts(reader) == (1, 1)
    assert len(await reader.fetch('SELECT * FROM runtime_gametime_sources')) == 1
    assert await reader.fetchval('SELECT count(*) FROM rounds') == 0


async def test_actual_lua_file_to_sealed_retention(retention_db, tmp_path, lua):  # noqa: F811
    writer, reader = retention_db
    output = run_writer(lua, tmp_path)
    assert 'RESULT=true' in output
    source = tmp_path / NAME
    raw = source.read_bytes()
    with source.open('rb') as stream:
        retained = await retain_gametime_source(adapter_for(writer), stream.fileno(),
            source_id='fixture-server', generation='a' * 32, filename=NAME,
            expected_size=len(raw), expected_sha256=hashlib.sha256(raw).hexdigest())
    payload = json.loads(await reader.fetchval('SELECT payload FROM lua_correction_inputs'))
    emitted = json.loads(raw)['meta']
    assert payload['actual_duration_seconds'] == emitted['actual_duration_seconds'] == 600
    assert payload['total_pause_seconds'] == emitted['pause_seconds'] == 10
    assert await reader.fetchval('SELECT input_id FROM runtime_gametime_sources') == retained.input_id
    assert await counts(reader) == (1, 1)
    assert source.read_bytes() == raw  # Timing-only retention never deletes/ACKs the file.
    print(f'LUA FILE -> SEALED PARSER -> PG: {Path(lua).name}, 600s+10s, 1 input/1 source')


@pytest.mark.parametrize(('enabled', 'target'), [(False, True), (True, False)])
async def test_notification_off_full_hook_file_retention_and_replay(retention_db, tmp_path, enabled, target):
    writer, reader = retention_db
    output = run_full_webhook(tmp_path, enabled=enabled, target=target, mode='frame', failure_only=True)
    assert 'COUNTS launches=0 opens=1 shell=1' in output
    source = tmp_path / NAME
    raw = source.read_bytes()
    first = await retain(adapter_for(writer), tmp_path, raw=raw)
    rows = await reader.fetch('SELECT * FROM runtime_gametime_sources')
    payload = json.loads(await reader.fetchval('SELECT payload FROM lua_correction_inputs'))
    assert payload['actual_duration_seconds'] == 600 and payload['total_pause_seconds'] == 10
    assert payload['round_end_unix'] - payload['round_start_unix'] == 610
    assert len(rows) == await reader.fetchval('SELECT count(*) FROM runtime_gametime_sources') == 1
    assert await retain(adapter_for(reader), tmp_path, raw=raw) == first
    assert await reader.fetch('SELECT * FROM runtime_gametime_sources') == rows
    assert await counts(reader) == (1, 1)
    assert await reader.fetchval('SELECT count(*) FROM rounds') == 0
    assert source.read_bytes() == raw
    print('FULL LUA FRAME -> SEALED TIMING -> PG: Discord unavailable, 600s+10s, '
          'replay unchanged, no inferred round parent or source acknowledgement')


@pytest.mark.parametrize('different_projection', [False, True])
async def test_conflicting_generation_rolls_back_new_input(retention_db, tmp_path, different_projection):
    writer, reader = retention_db
    first = await retain(adapter_for(writer), tmp_path)
    original = await reader.fetchrow('SELECT * FROM runtime_gametime_sources')
    changed = document()
    if different_projection:
        changed['meta']['actual_duration_seconds'] = 599
        changed['payload']['embeds'][0]['fields'][4]['value'] = '599 sec'
    # Extra whitespace changes the raw hash even when normalized timing is equal.
    raw = json.dumps(changed, indent=2).encode()
    with pytest.raises(ValueError, match='generation conflicts'):
        await retain(adapter_for(writer), tmp_path, raw=raw)
    assert await counts(reader) == (1, 1)
    assert await reader.fetchrow('SELECT * FROM runtime_gametime_sources') == original
    assert await reader.fetchval('SELECT id FROM lua_correction_inputs') == first.input_id


async def test_distinct_artifacts_share_projection_but_sources_do_not(retention_db, tmp_path):
    writer, reader = retention_db
    adapter = adapter_for(writer)
    one = await retain(adapter, tmp_path)
    two = await retain(adapter, tmp_path, generation='b' * 32, raw=json.dumps(document(), indent=2).encode())
    other = await retain(adapter, tmp_path, source_id='other-server')
    assert one.input_id == two.input_id != other.input_id
    assert await counts(reader) == (2, 3)
    assert await reader.fetchval('SELECT count(DISTINCT source_sha256) FROM runtime_gametime_sources') == 2


async def test_outer_rollback_is_invisible_to_other_connection(retention_db, tmp_path):
    writer, reader = retention_db
    adapter = adapter_for(writer)
    with pytest.raises(RuntimeError, match='fixture abort'):
        async with adapter.transaction():
            await retain(adapter, tmp_path)
            assert await counts(writer) == (1, 1)
            assert await counts(reader) == (0, 0)
            raise RuntimeError('fixture abort')
    assert await counts(reader) == (0, 0)


async def test_cancel_between_input_and_source_rolls_back(retention_db, tmp_path, monkeypatch):
    writer, reader = retention_db
    adapter = adapter_for(writer)
    original = adapter.fetch_one
    reached = asyncio.Event()

    async def pause(query, params=None):
        if 'INSERT INTO runtime_gametime_sources' in query:
            reached.set()
            await asyncio.Event().wait()
        return await original(query, params)

    monkeypatch.setattr(adapter, 'fetch_one', pause)
    task = asyncio.create_task(retain(adapter, tmp_path))
    try:
        await asyncio.wait_for(reached.wait(), 3)
        assert await counts(reader) == (0, 0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await counts(reader) == (0, 0)
        assert not writer.is_in_transaction()
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize('conflict', [False, 'same-identity', 'different-identity'])
async def test_concurrent_replay_or_conflict_waits_for_commit(retention_db, tmp_path, conflict):
    writer, reader = retention_db
    adapter = adapter_for(writer)
    task = None
    try:
        async with adapter.transaction():
            first = await retain(adapter, tmp_path)
            changed = document()
            if conflict == 'different-identity':
                changed['meta']['round_start_unix'] = 1699999999
                changed['payload']['embeds'][0]['fields'][2]['value'] = '1699999999'
            raw = json.dumps(changed, indent=2).encode() if conflict else None
            task = asyncio.create_task(retain(adapter_for(reader), tmp_path, raw=raw))
            for _ in range(100):
                wait_type = await writer.fetchval(
                    'SELECT wait_event_type FROM pg_stat_activity WHERE pid=$1', reader.get_server_pid(),
                )
                if wait_type == 'Lock':
                    break
                await asyncio.sleep(0.01)
            assert wait_type == 'Lock'
            assert not task.done()
        if conflict:
            with pytest.raises(ValueError, match='generation conflicts'):
                await asyncio.wait_for(task, 3)
        else:
            assert await asyncio.wait_for(task, 3) == first
        assert await counts(reader) == (1, 1)
    finally:
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_waiting_writer_succeeds_after_first_writer_rollback(retention_db, tmp_path):
    writer, reader = retention_db
    adapter = adapter_for(writer)
    task = None
    try:
        with pytest.raises(RuntimeError, match='fixture abort'):
            async with adapter.transaction():
                await retain(adapter, tmp_path)
                task = asyncio.create_task(retain(adapter_for(reader), tmp_path))
                for _ in range(100):
                    wait_type = await writer.fetchval(
                        'SELECT wait_event_type FROM pg_stat_activity WHERE pid=$1', reader.get_server_pid(),
                    )
                    if wait_type == 'Lock':
                        break
                    await asyncio.sleep(0.01)
                assert wait_type == 'Lock'
                assert not task.done()
                raise RuntimeError('fixture abort')
        result = await asyncio.wait_for(task, 3)
        assert await counts(reader) == (1, 1)
        assert await reader.fetchval('SELECT input_id FROM runtime_gametime_sources') == result.input_id
    finally:
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_migration_replay_and_fk_do_not_adopt_or_cross_sources(retention_db, tmp_path):
    writer, reader = retention_db
    await writer.execute(MIGRATION.read_text())
    assert await counts(reader) == (0, 0)
    first = await retain(adapter_for(writer), tmp_path)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await writer.execute('DELETE FROM lua_correction_inputs WHERE id=$1', first.input_id)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await writer.execute("UPDATE runtime_gametime_sources SET source_key='other-server'")
    assert await counts(reader) == (1, 1)
    # PUBLIC has no privilege entries, independently of the executing owner's rights.
    assert await reader.fetchval('''SELECT count(*) FROM pg_class c,
        LATERAL aclexplode(c.relacl) a
        WHERE c.oid='runtime_gametime_sources'::regclass AND a.grantee=0''') == 0


async def test_missing_migration_rolls_back_inbox(journal_db, tmp_path):  # noqa: F811
    writer, reader = journal_db
    await writer.execute((ROOT / 'migrations/088_lua_correction_inputs.sql').read_text())
    with pytest.raises(asyncpg.UndefinedTableError):
        await retain(adapter_for(writer), tmp_path)
    assert await reader.fetchval('SELECT count(*) FROM lua_correction_inputs') == 0


async def test_migration_does_not_invent_sources_for_legacy_inputs(journal_db, tmp_path):  # noqa: F811
    from bot.services.lua_correction_inbox import retain_lua_correction

    writer, reader = journal_db
    await writer.execute((ROOT / 'migrations/088_lua_correction_inputs.sql').read_text())
    old_id = await retain_lua_correction(adapter_for(writer), 'fixture-server', {
        'map_name': 'supply', 'round_number': 1, 'round_start_unix': 1700000000,
        'round_end_unix': 1700000610, 'actual_duration_seconds': 600,
        'total_pause_seconds': 10, 'pause_count': 1,
    })
    await writer.execute(MIGRATION.read_text())
    assert await counts(reader) == (1, 0)
    # Only explicit re-admission creates a source receipt; payload identity is reused.
    assert (await retain(adapter_for(writer), tmp_path)).input_id == old_id
    assert await counts(reader) == (1, 1)


async def test_migration_restricts_new_table_not_existing_defaults(acl_db):  # noqa: F811
    conn = acl_db
    defaults = await default_acls(conn)
    old_acl = await conn.fetchval("SELECT relacl::text FROM pg_class WHERE oid='lua_correction_inputs'::regclass")
    await conn.execute(MIGRATION.read_text())
    await conn.execute(MIGRATION.read_text())
    assert await default_acls(conn) == defaults
    assert await conn.fetchval(
        "SELECT relacl::text FROM pg_class WHERE oid='lua_correction_inputs'::regclass",
    ) == old_acl
    for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'):
        assert not await conn.fetchval(
            "SELECT has_table_privilege('website_app', 'runtime_gametime_sources', $1)", privilege,
        )
    await denied(conn, 'SELECT * FROM runtime_gametime_sources')
    await denied(conn, 'INSERT INTO runtime_gametime_sources DEFAULT VALUES')


async def test_direct_column_privilege_is_removed_by_table_revoke(acl_db):  # noqa: F811
    conn = acl_db
    await conn.execute(MIGRATION.read_text())
    await conn.execute('GRANT SELECT(filename) ON runtime_gametime_sources TO website_app')
    assert await conn.fetchval(
        "SELECT has_column_privilege('website_app', 'runtime_gametime_sources', 'filename', 'SELECT')",
    )
    # PostgreSQL table REVOKE also removes matching direct column privileges.
    await conn.execute(MIGRATION.read_text())
    assert not await conn.fetchval(
        "SELECT has_any_column_privilege('website_app', 'runtime_gametime_sources', 'SELECT')",
    )
    await denied(conn, 'SELECT filename FROM runtime_gametime_sources')


@pytest.mark.parametrize('access', ['table', 'column', 'owner'])
async def test_set_role_bypass_makes_migration_fail_closed(acl_db, access):  # noqa: F811
    conn = acl_db
    await conn.execute(MIGRATION.read_text())
    role = await reachable_role(conn)
    if access == 'owner':
        await conn.execute(f'ALTER TABLE runtime_gametime_sources OWNER TO "{role}"')
        await conn.execute(f'REVOKE ALL ON runtime_gametime_sources FROM "{role}"')
        operation = 'ALTER TABLE runtime_gametime_sources ADD COLUMN owner_proof INTEGER'
    else:
        permission = 'SELECT(filename)' if access == 'column' else 'SELECT'
        await conn.execute(f'GRANT {permission} ON runtime_gametime_sources TO "{role}"')
        operation = 'SELECT filename FROM runtime_gametime_sources'
    # Demonstrate the capability through the website identity, not superuser SET.
    await execute_as_website(conn, operation, role=role)
    with pytest.raises(asyncpg.RaiseError, match='retains inherited gametime source access'):
        async with conn.transaction():
            await conn.execute(MIGRATION.read_text())


@pytest.mark.timeout(120)  # Includes complete schema creation on the shared disk.
async def test_full_bootstrap_real_pool_receipt_without_round_or_repair(full_import_db, tmp_path):  # noqa: F811
    manager, reader = full_import_db
    adapter = PostgreSQLAdapter('unused', 5432, 'unused', 'unused', '', min_pool_size=1, max_pool_size=2)
    adapter.pool = manager.pool
    result = await retain(adapter, tmp_path)
    assert await reader.fetchval('SELECT input_id FROM runtime_gametime_sources') == result.input_id
    assert await counts(reader) == (1, 1)
    assert await reader.fetchval('SELECT count(*) FROM rounds') == 0
    assert await reader.fetchval('SELECT count(*) FROM lua_correction_receipts') == 0
    print('GAMETIME RETENTION PROOF: sealed file -> normalized input + source FK; '
          'independent connection sees 1+1 committed rows, 0 rounds and 0 repair receipts')


def test_bootstrap_contains_exact_new_migration():
    assert MIGRATION.read_text().strip() in (ROOT / 'tools/schema_postgresql.sql').read_text()
