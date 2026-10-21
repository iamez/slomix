"""Forward-only proximity provenance schema on explicitly disposable PostgreSQL."""

from datetime import date
from pathlib import Path

import asyncpg
import pytest

from tests.integration.test_runtime_website_privileges_pg import acl_db as _acl_db
from tests.integration.test_runtime_website_privileges_pg import default_acls, denied, reachable_role

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / 'migrations/100_runtime_proximity_mappings.sql'
acl_db = _acl_db
pytestmark = pytest.mark.timeout(120)


async def parents(conn):
    """Only synthetic transaction-scoped parents; no application data."""
    await conn.execute('CREATE TABLE rounds (id INTEGER PRIMARY KEY)')
    await conn.execute('CREATE TABLE proximity_processed_files (filename TEXT PRIMARY KEY)')
    await conn.execute((ROOT / 'migrations/099_runtime_round_mappings.sql').read_text())
    await conn.execute('INSERT INTO rounds VALUES (1),(2),(3)')
    for number in (1, 2):
        key = str(number) * 32
        await conn.execute(
            'INSERT INTO runtime_round_mappings VALUES '
            "('fixture',$1,$1,1,$1,$1,$2,1,$3,'supply',$4,$3,DEFAULT)",
            key, f'stats-{number}.txt', 'a' * 64, number,
        )
    await conn.execute(
        "INSERT INTO proximity_processed_files VALUES ('first.txt'),('second.txt'),('third.txt')"
    )


async def insert(conn, **changed):
    values = dict(filename='first.txt', source_key='fixture', generation='3' * 32,
                  round_key='1' * 32, source_size=1, source_sha256='b' * 64,
                  session_date=date(2026, 10, 8), canonical_round_id=1)
    values.update(changed)
    columns = ','.join(values)
    placeholders = ','.join(f'${index}' for index in range(1, len(values) + 1))
    await conn.execute(
        f'INSERT INTO runtime_proximity_mappings ({columns}) VALUES ({placeholders})',
        *values.values(),
    )


def _assert_exact_migration_once(schema, migration):
    assert migration in schema
    assert schema.count(migration.strip()) == 1


@pytest.mark.parametrize('migration_name', ['096_proximity_receipt_round_link.sql',
                                         '100_runtime_proximity_mappings.sql'])
def test_bootstrap_appends_exact_proximity_mapping_migration(migration_name):
    schema = (ROOT / 'tools/schema_postgresql.sql').read_text()
    migration = (ROOT / 'migrations' / migration_name).read_text()
    # Forward migrations may follow this block; its exact bytes must remain once.
    _assert_exact_migration_once(schema, migration)


@pytest.mark.parametrize('mutation', ['missing', 'edited', 'duplicated'])
@pytest.mark.parametrize('migration_name', ['096_proximity_receipt_round_link.sql',
                                         '100_runtime_proximity_mappings.sql'])
def test_bootstrap_contract_rejects_changed_proximity_migration(mutation, migration_name):
    schema = (ROOT / 'tools/schema_postgresql.sql').read_text()
    migration = (ROOT / 'migrations' / migration_name).read_text()
    _assert_exact_migration_once(schema, migration)
    if mutation == 'missing':
        changed = schema.replace(migration, '')
    elif mutation == 'edited':
        changed = schema.replace(migration, migration.replace('ON DELETE RESTRICT', 'ON DELETE CASCADE', 1))
    else:
        changed = schema + migration
    assert changed != schema
    with pytest.raises(AssertionError):
        _assert_exact_migration_once(changed, migration)


async def test_schema_has_no_backfill_and_rerun_preserves_exact_row(acl_db):
    conn = acl_db
    await parents(conn)
    await conn.execute(MIGRATION.read_text())
    assert await conn.fetch('SELECT * FROM runtime_proximity_mappings') == []
    await insert(conn)
    before = await conn.fetch('SELECT * FROM runtime_proximity_mappings')
    assert len(before) == await conn.fetchval('SELECT count(*) FROM runtime_proximity_mappings') == 1
    assert tuple(before[0].keys()) == (
        'filename', 'source_key', 'generation', 'round_key', 'source_size',
        'source_sha256', 'session_date', 'canonical_round_id', 'created_at',
    )
    assert before[0]['created_at'] is not None
    await conn.execute(MIGRATION.read_text())
    assert await conn.fetch('SELECT * FROM runtime_proximity_mappings') == before
    print('Proximity100 schema proof: zero backfill; exact single row survives migration replay')


@pytest.mark.parametrize('changed', [
    {'filename': 'missing.txt'},
    {'source_key': 'other'},
    {'round_key': 'f' * 32},
    {'canonical_round_id': 99},
])
async def test_missing_receipt_mapping_or_parent_rejected(acl_db, changed):
    conn = acl_db
    await parents(conn)
    await conn.execute(MIGRATION.read_text())
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        async with conn.transaction():
            await insert(conn, **changed)
    assert await conn.fetchval('SELECT count(*) FROM runtime_proximity_mappings') == 0


@pytest.mark.parametrize('changed', [
    {'filename': 'first.txt', 'generation': '4' * 32, 'round_key': '2' * 32, 'canonical_round_id': 2},
    {'filename': 'second.txt', 'generation': '3' * 32, 'round_key': '2' * 32, 'canonical_round_id': 2},
    {'filename': 'second.txt', 'generation': '4' * 32, 'round_key': '2' * 32, 'canonical_round_id': 1},
])
async def test_filename_generation_and_canonical_parent_are_unique(acl_db, changed):
    conn = acl_db
    await parents(conn)
    await conn.execute(MIGRATION.read_text())
    await insert(conn)
    before = await conn.fetch('SELECT * FROM runtime_proximity_mappings')
    with pytest.raises(asyncpg.UniqueViolationError):
        async with conn.transaction():
            await insert(conn, **changed)
    assert await conn.fetch('SELECT * FROM runtime_proximity_mappings') == before


@pytest.mark.parametrize('sql', [
    "DELETE FROM proximity_processed_files WHERE filename='first.txt'",
    'DELETE FROM rounds WHERE id=1',
    "DELETE FROM runtime_round_mappings WHERE source_key='fixture' AND round_key='" + '1' * 32 + "'",
])
async def test_receipt_stats_mapping_and_parent_deletions_are_restricted(acl_db, sql):
    conn = acl_db
    await parents(conn)
    await conn.execute(MIGRATION.read_text())
    await insert(conn)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        async with conn.transaction():
            await conn.execute(sql)
    assert await conn.fetchval('SELECT count(*) FROM runtime_proximity_mappings') == 1


@pytest.mark.parametrize('changed', [
    {'filename': ''}, {'filename': 'x' * 241},
    {'source_key': 'Fixture'}, {'source_key': ''},
    {'generation': 'A' * 32}, {'generation': '3' * 31},
    {'round_key': 'A' * 32}, {'round_key': '1' * 31},
    {'source_size': 0}, {'source_size': 8388609},
    {'source_sha256': 'B' * 64}, {'source_sha256': 'b' * 63},
])
async def test_schema_rejects_unbounded_or_noncanonical_identity(acl_db, changed):
    conn = acl_db
    await parents(conn)
    await conn.execute(MIGRATION.read_text())
    with pytest.raises(asyncpg.CheckViolationError):
        async with conn.transaction():
            await insert(conn, **changed)
    assert await conn.fetch('SELECT * FROM runtime_proximity_mappings') == []


@pytest.mark.parametrize('privilege', ['SELECT', 'INSERT', 'UPDATE', 'REFERENCES'])
async def test_direct_column_grants_are_removed_without_default_acl_changes(acl_db, privilege):
    conn = acl_db
    await parents(conn)
    before = await default_acls(conn)
    await conn.execute(MIGRATION.read_text())
    await conn.execute(
        f'GRANT {privilege}(round_key) ON runtime_proximity_mappings TO website_app'
    )
    await conn.execute(MIGRATION.read_text())
    assert await default_acls(conn) == before
    assert not await conn.fetchval(
        "SELECT has_any_column_privilege('website_app','runtime_proximity_mappings',"
        "'SELECT,INSERT,UPDATE,REFERENCES')"
    )
    await denied(conn, 'SELECT round_key FROM runtime_proximity_mappings')
    await denied(conn, 'INSERT INTO runtime_proximity_mappings DEFAULT VALUES')


@pytest.mark.parametrize('access', ['table', 'column', 'owner'])
async def test_inherited_access_fails_migration_closed(acl_db, access):
    conn = acl_db
    await parents(conn)
    await conn.execute(MIGRATION.read_text())
    role = await reachable_role(conn)
    if access == 'owner':
        await conn.execute(f'ALTER TABLE runtime_proximity_mappings OWNER TO "{role}"')
    else:
        permission = 'SELECT(round_key)' if access == 'column' else 'SELECT'
        await conn.execute(f'GRANT {permission} ON runtime_proximity_mappings TO "{role}"')
    with pytest.raises(asyncpg.RaiseError, match='retains inherited proximity mapping access'):
        async with conn.transaction():
            await conn.execute(MIGRATION.read_text())


@pytest.mark.parametrize('privilege', ['SELECT', 'INSERT', 'UPDATE', 'REFERENCES'])
async def test_public_column_access_is_removed(acl_db, privilege):
    conn = acl_db
    await parents(conn)
    await conn.execute(MIGRATION.read_text())
    await conn.execute(f'GRANT {privilege}(round_key) ON runtime_proximity_mappings TO PUBLIC')
    await conn.execute(MIGRATION.read_text())
    assert not await conn.fetchval(
        "SELECT has_any_column_privilege('website_app','runtime_proximity_mappings',"
        "'SELECT,INSERT,UPDATE,REFERENCES')"
    )
    await denied(conn, 'SELECT round_key FROM runtime_proximity_mappings')
