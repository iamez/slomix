"""Durable timing link schema in owner-opted-in disposable rollback fixtures."""

from pathlib import Path

import asyncpg
import pytest

from tests.integration.test_runtime_website_privileges_pg import acl_db as _acl_db
from tests.integration.test_runtime_website_privileges_pg import default_acls, denied, reachable_role

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / 'migrations/101_runtime_gametime_links.sql'
acl_db = _acl_db
pytestmark = pytest.mark.timeout(120)


async def parents(conn):
    await conn.execute('CREATE TABLE rounds (id INTEGER PRIMARY KEY)')
    for number in (97, 98, 99):
        files = list((ROOT / 'migrations').glob(f'{number:03}_*.sql'))
        assert len(files) == 1
        await conn.execute(files[0].read_text())
    await conn.execute("INSERT INTO lua_correction_inputs "
        "(id,source_key,payload_version,payload_digest,map_name,round_number,round_start_unix,payload) "
        "VALUES (7,'fixture',1,repeat('0',64),'supply',1,1,'{}'),"
        "(8,'other',1,repeat('0',64),'supply',1,1,'{}')")
    await conn.execute('INSERT INTO rounds VALUES (1),(2),(3)')
    for number in (1, 2):
        key, generation = str(number) * 32, str(number + 2) * 32
        await conn.execute(
            'INSERT INTO runtime_round_mappings VALUES '
            "('fixture',$1,$1,1,$1,$1,$2,1,$3,'supply',$4,$3,DEFAULT)",
            key, f'stats-{number}.txt', 'a' * 64, number,
        )
        await conn.execute('INSERT INTO runtime_gametime_sources VALUES '
            "('fixture',$1,'gametime-supply-R1-1.json',1,$2,7,DEFAULT)", generation, 'b' * 64)
        await conn.execute('INSERT INTO runtime_gametime_identities VALUES '
            "('fixture',$1,$2,$2,1,$2,DEFAULT)", generation, key)


async def insert(conn, **changed):
    values = dict(source_key='fixture', generation='3' * 32, round_key='1' * 32,
        canonical_round_id=1, input_id=7, filename='gametime-supply-R1-1.json',
        source_size=1, source_sha256='b' * 64, projection_sha256='c' * 64)
    values.update(changed)
    columns = ','.join(values)
    placeholders = ','.join(f'${index}' for index in range(1, len(values) + 1))
    await conn.execute(
        f'INSERT INTO runtime_gametime_links ({columns}) VALUES ({placeholders})', *values.values(),
    )


def test_bootstrap_appends_exact_link_migration():
    schema = (ROOT / 'tools/schema_postgresql.sql').read_text()
    assert MIGRATION.read_text() in schema
    assert schema.count(MIGRATION.read_text().strip()) == 1


async def test_no_backfill_replay_and_shared_input_for_distinct_canonical_targets(acl_db):
    conn = acl_db
    await parents(conn)
    await conn.execute(MIGRATION.read_text())
    assert await conn.fetch('SELECT * FROM runtime_gametime_links') == []
    await insert(conn)
    await insert(conn, generation='4' * 32, round_key='2' * 32, canonical_round_id=2)
    before = await conn.fetch('SELECT * FROM runtime_gametime_links ORDER BY generation')
    assert len(before) == await conn.fetchval('SELECT count(*) FROM runtime_gametime_links') == 2
    assert tuple(before[0].keys()) == (
        'source_key', 'generation', 'round_key', 'canonical_round_id', 'input_id',
        'filename', 'source_size', 'source_sha256', 'projection_sha256', 'linked_at',
    )
    assert [row['input_id'] for row in before] == [7, 7]
    assert all(row['linked_at'] is not None for row in before)
    await conn.execute(MIGRATION.read_text())
    assert await conn.fetch('SELECT * FROM runtime_gametime_links ORDER BY generation') == before
    print('Timing101 schema proof: no backfill; 2 distinct canonical targets share 1 input; replay unchanged')


@pytest.mark.parametrize('changed', [
    {'generation': 'f' * 32}, {'round_key': 'f' * 32},
    {'canonical_round_id': 99}, {'input_id': 99}, {'input_id': 8},
])
async def test_missing_or_cross_source_parents_rejected(acl_db, changed):
    conn = acl_db
    await parents(conn)
    await conn.execute(MIGRATION.read_text())
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        async with conn.transaction():
            await insert(conn, **changed)
    assert await conn.fetch('SELECT * FROM runtime_gametime_links') == []


@pytest.mark.parametrize('changed', [
    {'generation': '3' * 32, 'round_key': '2' * 32, 'canonical_round_id': 2},
    {'generation': '4' * 32, 'round_key': '2' * 32, 'canonical_round_id': 1},
])
async def test_artifact_primary_key_and_one_authoritative_artifact_per_round(acl_db, changed):
    conn = acl_db
    await parents(conn)
    await conn.execute(MIGRATION.read_text())
    await insert(conn)
    before = await conn.fetch('SELECT * FROM runtime_gametime_links')
    with pytest.raises(asyncpg.UniqueViolationError):
        async with conn.transaction():
            await insert(conn, **changed)
    assert await conn.fetch('SELECT * FROM runtime_gametime_links') == before


@pytest.mark.parametrize('sql', [
    "DELETE FROM runtime_gametime_identities WHERE generation=repeat('3',32)",
    "DELETE FROM runtime_round_mappings WHERE round_key=repeat('1',32)",
    'DELETE FROM rounds WHERE id=1', 'DELETE FROM lua_correction_inputs WHERE id=7',
])
async def test_linked_parent_deletions_are_restricted(acl_db, sql):
    conn = acl_db
    await parents(conn)
    await conn.execute(MIGRATION.read_text())
    await insert(conn)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        async with conn.transaction():
            await conn.execute(sql)
    assert await conn.fetchval('SELECT count(*) FROM runtime_gametime_links') == 1


@pytest.mark.parametrize('changed', [
    {'source_key': 'Fixture'}, {'generation': 'A' * 32}, {'round_key': 'A' * 32},
    {'filename': 'not-gametime.json'}, {'source_size': 0}, {'source_size': 1048577},
    {'source_sha256': 'B' * 64}, {'projection_sha256': 'c' * 63},
])
async def test_invalid_or_unbounded_binding_rejected(acl_db, changed):
    conn = acl_db
    await parents(conn)
    await conn.execute(MIGRATION.read_text())
    with pytest.raises(asyncpg.CheckViolationError):
        async with conn.transaction():
            await insert(conn, **changed)
    assert await conn.fetch('SELECT * FROM runtime_gametime_links') == []


@pytest.mark.parametrize('privilege', ['SELECT', 'INSERT', 'UPDATE', 'REFERENCES'])
async def test_direct_column_access_removed_without_default_acl_changes(acl_db, privilege):
    conn = acl_db
    await parents(conn)
    before = await default_acls(conn)
    await conn.execute(MIGRATION.read_text())
    for grantee in ('website_app', 'PUBLIC'):
        await conn.execute(f'GRANT {privilege}(round_key) ON runtime_gametime_links TO {grantee}')
    await conn.execute(MIGRATION.read_text())
    assert await default_acls(conn) == before
    assert not await conn.fetchval(
        "SELECT has_any_column_privilege('website_app','runtime_gametime_links',"
        "'SELECT,INSERT,UPDATE,REFERENCES')"
    )
    await denied(conn, 'SELECT round_key FROM runtime_gametime_links')
    await denied(conn, 'INSERT INTO runtime_gametime_links DEFAULT VALUES')


@pytest.mark.parametrize('access', ['table', 'column', 'owner'])
async def test_inherited_access_fails_closed(acl_db, access):
    conn = acl_db
    await parents(conn)
    await conn.execute(MIGRATION.read_text())
    role = await reachable_role(conn)
    if access == 'owner':
        await conn.execute(f'ALTER TABLE runtime_gametime_links OWNER TO "{role}"')
    else:
        permission = 'SELECT(round_key)' if access == 'column' else 'SELECT'
        await conn.execute(f'GRANT {permission} ON runtime_gametime_links TO "{role}"')
    with pytest.raises(asyncpg.RaiseError, match='retains inherited gametime link access'):
        async with conn.transaction():
            await conn.execute(MIGRATION.read_text())
