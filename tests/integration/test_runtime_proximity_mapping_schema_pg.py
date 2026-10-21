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


async def parents(conn, *, link_sql=None):
    """Only synthetic transaction-scoped parents; no application data."""
    await conn.execute('CREATE TABLE rounds (id INTEGER PRIMARY KEY)')
    await conn.execute('CREATE TABLE proximity_processed_files ('
                       'filename TEXT PRIMARY KEY, runtime_parent_gate BOOLEAN, '
                       'aggregates_applied BOOLEAN, file_hash TEXT)')
    await conn.execute(link_sql if link_sql is not None else
                       (ROOT / 'migrations/096_proximity_receipt_round_link.sql').read_text())
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
        "INSERT INTO proximity_processed_files VALUES "
        "('first.txt',true,true,$1,1),('second.txt',true,true,$1,2),('third.txt',true,true,$1,3)",
        'b' * 64,
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


async def test_stats_identity_cannot_bind_another_existing_round(acl_db):
    await parents(acl_db)
    await acl_db.execute(MIGRATION.read_text())
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        async with acl_db.transaction():
            await insert(acl_db, filename='second.txt', canonical_round_id=2)
    assert await acl_db.fetchval('SELECT count(*) FROM runtime_proximity_mappings') == 0


@pytest.mark.parametrize('receipt', [
    (None, None, None, None), (True, True, 'b' * 64, None),
    (True, True, 'c' * 64, 1), (True, True, 'b' * 64, 2),
])
async def test_legacy_unlinked_or_mismatched_receipt_cannot_be_adopted(acl_db, receipt):
    await parents(acl_db)
    await acl_db.execute(MIGRATION.read_text())
    await acl_db.execute("UPDATE proximity_processed_files SET runtime_parent_gate=$1, "
                        "aggregates_applied=$2, file_hash=$3, linked_round_id=$4 "
                        "WHERE filename='first.txt'", *receipt)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        async with acl_db.transaction():
            await insert(acl_db)
    assert await acl_db.fetchval('SELECT count(*) FROM runtime_proximity_mappings') == 0


@pytest.mark.parametrize('gate,aggregates', [(None, True), (False, True), (True, None), (True, False)])
async def test_link_requires_true_gate_and_applied_aggregates(acl_db, gate, aggregates):
    await parents(acl_db)
    with pytest.raises(asyncpg.CheckViolationError):
        async with acl_db.transaction():
            await acl_db.execute("UPDATE proximity_processed_files SET runtime_parent_gate=$1, "
                                "aggregates_applied=$2 WHERE filename='first.txt'", gate, aggregates)


@pytest.mark.parametrize('change', ["file_hash='c'", 'linked_round_id=NULL', 'linked_round_id=2'])
async def test_receipt_binding_cannot_change_after_mapping(acl_db, change):
    await parents(acl_db)
    await acl_db.execute(MIGRATION.read_text())
    await insert(acl_db)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        async with acl_db.transaction():
            await acl_db.execute(f"UPDATE proximity_processed_files SET {change} WHERE filename='first.txt'")
    assert await acl_db.fetchval('SELECT count(*) FROM runtime_proximity_mappings') == 1


@pytest.mark.parametrize('guard', ['stats_parent', 'strict_receipt', 'nullable_gate'])
async def test_mutated_schema_guard_accepts_invalid_binding(acl_db, guard):
    """In-memory mutants prove each SQL guard is exercised on disposable PG."""
    migration = MIGRATION.read_bytes()
    link_path = ROOT / 'migrations/096_proximity_receipt_round_link.sql'
    link_original = link_path.read_bytes()
    link_sql = link_original.decode()
    sql = migration.decode()
    if guard == 'stats_parent':
        sql = sql.replace('FOREIGN KEY (source_key, round_key, canonical_round_id)',
                          'FOREIGN KEY (source_key, round_key)').replace(
            'REFERENCES runtime_round_mappings(source_key, round_key, canonical_round_id)',
            'REFERENCES runtime_round_mappings(source_key, round_key)')
    elif guard == 'strict_receipt':
        sql = sql.replace(',\n    FOREIGN KEY (filename, canonical_round_id, source_sha256)\n'
                          '        REFERENCES proximity_processed_files(filename, linked_round_id, file_hash) '
                          'ON DELETE RESTRICT', '')
    else:
        link_sql = link_sql.replace('runtime_parent_gate IS TRUE AND', 'runtime_parent_gate AND')
    assert sql != migration.decode() or link_sql != link_original.decode()
    await parents(acl_db, link_sql=link_sql)
    await acl_db.execute(sql)
    if guard == 'stats_parent':
        await insert(acl_db, filename='second.txt', canonical_round_id=2)
    else:
        if guard == 'strict_receipt':
            await acl_db.execute("UPDATE proximity_processed_files SET linked_round_id=NULL "
                                "WHERE filename='first.txt'")
        else:
            await acl_db.execute("UPDATE proximity_processed_files SET runtime_parent_gate=NULL "
                                "WHERE filename='first.txt'")
        await insert(acl_db)
    invalid_rows = await acl_db.fetch('SELECT * FROM runtime_proximity_mappings')
    assert len(invalid_rows) == await acl_db.fetchval('SELECT count(*) FROM runtime_proximity_mappings') == 1
    # The same no-invalid-row assertion must visibly fail with the guard removed.
    with pytest.raises(AssertionError):
        assert invalid_rows == []
    assert MIGRATION.read_bytes() == migration
    assert link_path.read_bytes() == link_original
    print(f'Observed failing SQL guard mutation: {guard}; source bytes unchanged')
