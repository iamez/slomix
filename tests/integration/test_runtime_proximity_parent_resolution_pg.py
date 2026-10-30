"""Execute declared-parent resolution against real PostgreSQL, without consumers."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from shared.proximity_receipt_link import record_receipt_parent, validate_receipt_parent
from shared.runtime_proximity_mapping import DeclaredMappingPending, ResolvedDeclaredParent, resolve_declared_parent
from tests.integration.proximity_adapter_helpers import pg_query
from tests.integration.test_runtime_website_privileges_pg import acl_db as _acl_db
from tests.unit.test_runtime_round_identity import FIRST, SECOND

ROOT = Path(__file__).resolve().parents[2]
acl_db = _acl_db
pytestmark = pytest.mark.timeout(120)


@pytest.fixture
async def mapped_parents(acl_db):
    conn = acl_db
    await conn.execute('''CREATE TABLE rounds (
        id INTEGER PRIMARY KEY, map_name TEXT, round_number INTEGER,
        gaming_session_id INTEGER, match_id TEXT, round_date TEXT, round_time TEXT)''')
    await conn.execute((ROOT / 'migrations/099_runtime_round_mappings.sql').read_text())
    for half, identity in enumerate((FIRST, SECOND), 1):
        filename = f'2026-09-25-120000-supply-round-{half}.txt'
        await conn.execute("INSERT INTO rounds VALUES "
            "($1,'supply',$1,20,'2026-09-25-120000','2026-09-25','120000')", half)
        await conn.execute('''INSERT INTO runtime_round_mappings VALUES
            ($1,$2,$3,$4,$5,$6,$7,1,$8,'supply',$9,$8,DEFAULT)''',
            identity.source_id, identity.round_id, identity.match_id, half,
            identity.first_round_id, str(half) * 32, filename, 'a' * 64, half)
        await conn.execute('''INSERT INTO runtime_events
            (event_type,schema_version,round_id,round_number,gaming_session_id,
             source_filename,source_payload_sha256,validation_passed)
            VALUES ('round_stats_imported',1,$1,$1,20,$2,$3,TRUE)''', half, filename, 'a' * 64)

    async def fetch_one(query, params=()):
        return await conn.fetchrow(pg_query(query), *params)

    return conn, SimpleNamespace(fetch_one=fetch_one)


@pytest.mark.parametrize('lock', [False, True])
async def test_real_postgres_resolves_both_halves_and_preserves_rows(mapped_parents, lock):
    conn, adapter = mapped_parents
    before = await conn.fetch('SELECT * FROM runtime_round_mappings ORDER BY round_number')
    for half, identity in enumerate((FIRST, SECOND), 1):
        assert await resolve_declared_parent(adapter, identity, 'supply', lock=lock) == ResolvedDeclaredParent(half, 20)
    assert await conn.fetch('SELECT * FROM runtime_round_mappings ORDER BY round_number') == before
    assert len(before) == await conn.fetchval('SELECT count(*) FROM runtime_round_mappings') == 2
    print('Declared parent proof: both halves resolve through mapping, canonical row and import journal; no writes')


@pytest.mark.parametrize('damage', ['journal_hash', 'journal_missing', 'journal_invalid',
                                  'parent_session', 'parent_date', 'first_journal'])
async def test_real_parent_or_journal_contradiction_is_refused(mapped_parents, damage):
    conn, adapter = mapped_parents
    if damage == 'journal_hash':
        await conn.execute("UPDATE runtime_events SET source_payload_sha256=repeat('f',64) WHERE round_id=2")
    elif damage == 'journal_missing':
        await conn.execute('DELETE FROM runtime_events WHERE round_id=2')
    elif damage in {'journal_invalid', 'first_journal'}:
        await conn.execute('UPDATE runtime_events SET validation_passed=FALSE WHERE round_id=$1',
                           1 if damage == 'first_journal' else 2)
    elif damage == 'parent_session':
        await conn.execute('UPDATE rounds SET gaming_session_id=NULL WHERE id=2')
    else:
        await conn.execute("UPDATE rounds SET round_date='2026-09-26' WHERE id=2")
    with pytest.raises(ValueError, match='canonical'):
        await resolve_declared_parent(adapter, SECOND, 'supply')


async def test_missing_mapping_remains_pending_without_clock_fallback(mapped_parents):
    conn, adapter = mapped_parents
    await conn.execute('DELETE FROM runtime_round_mappings WHERE round_number=2')
    assert await conn.fetchval('SELECT count(*) FROM rounds') == 2
    with pytest.raises(DeclaredMappingPending, match='mapping_pending'):
        await resolve_declared_parent(adapter, SECOND, 'supply')


async def prepare_receipt(conn):
    await conn.execute('''CREATE TABLE proximity_processed_files (
        filename TEXT PRIMARY KEY, aggregates_applied BOOLEAN,
        file_hash TEXT, runtime_parent_gate BOOLEAN)''')
    await conn.execute((ROOT / 'migrations/096_proximity_receipt_round_link.sql').read_text())
    await conn.execute("INSERT INTO proximity_processed_files VALUES ('fixture',FALSE,repeat('a',64),TRUE,NULL)")


async def test_receipt_link_participates_in_caller_rollback_and_refuses_reassignment(mapped_parents):
    conn, adapter = mapped_parents
    await prepare_receipt(conn)
    await validate_receipt_parent(adapter, 'fixture', 1)
    with pytest.raises(RuntimeError, match='caller rollback'):
        async with conn.transaction():
            await conn.execute('UPDATE proximity_processed_files SET aggregates_applied=TRUE')
            await record_receipt_parent(adapter, 'fixture', 1)
            assert await conn.fetchval('SELECT linked_round_id FROM proximity_processed_files') == 1
            raise RuntimeError('caller rollback')
    assert tuple(await conn.fetchrow('SELECT aggregates_applied,linked_round_id FROM proximity_processed_files')) == (
        False, None,
    )
    await validate_receipt_parent(adapter, 'fixture', 1)
    await conn.execute('UPDATE proximity_processed_files SET aggregates_applied=TRUE')
    await record_receipt_parent(adapter, 'fixture', 1)
    await validate_receipt_parent(adapter, 'fixture', 1)
    with pytest.raises(ValueError, match='conflicts'):
        await validate_receipt_parent(adapter, 'fixture', 2)
    with pytest.raises(RuntimeError, match='not recorded'):
        await record_receipt_parent(adapter, 'fixture', 2)
    assert await conn.fetchval('SELECT linked_round_id FROM proximity_processed_files') == 1


async def test_missing_or_completed_unlinked_receipt_is_not_adopted(mapped_parents):
    conn, adapter = mapped_parents
    await prepare_receipt(conn)
    with pytest.raises(RuntimeError, match='claimed receipt'):
        await validate_receipt_parent(adapter, 'missing', 1)
    await conn.execute('UPDATE proximity_processed_files SET aggregates_applied=TRUE')
    with pytest.raises(ValueError, match='lacks durable round identity'):
        await validate_receipt_parent(adapter, 'fixture', 1)
    assert await conn.fetchval('SELECT linked_round_id FROM proximity_processed_files') is None


@pytest.mark.parametrize('assignment', ['runtime_parent_gate=FALSE', 'runtime_parent_gate=NULL',
                                       'file_hash=NULL', 'aggregates_applied=FALSE'])
async def test_receipt_recording_requires_complete_strict_provenance(mapped_parents, assignment):
    conn, adapter = mapped_parents
    await prepare_receipt(conn)
    await conn.execute('UPDATE proximity_processed_files SET aggregates_applied=TRUE')
    await conn.execute('UPDATE proximity_processed_files SET ' + assignment)
    with pytest.raises(RuntimeError, match='not recorded'):
        await record_receipt_parent(adapter, 'fixture', 1)
    assert await conn.fetchval('SELECT linked_round_id FROM proximity_processed_files') is None
