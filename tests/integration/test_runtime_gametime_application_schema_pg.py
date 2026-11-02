"""Private102 schema, real constraints and ACLs in rollback-only isolated schema."""

import json
from pathlib import Path

import asyncpg
import pytest

from tests.integration.test_runtime_gametime_link_schema_pg import insert as insert_link
from tests.integration.test_runtime_gametime_link_schema_pg import parents
from tests.integration.test_runtime_website_privileges_pg import acl_db as _acl_db
from tests.integration.test_runtime_website_privileges_pg import default_acls, denied, reachable_role

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / 'migrations/102_runtime_gametime_applications.sql'
acl_db = _acl_db
pytestmark = pytest.mark.timeout(120)


async def prepare(conn):
    await parents(conn)
    await conn.execute((ROOT / 'migrations/101_runtime_gametime_links.sql').read_text())
    await insert_link(conn)
    await insert_link(conn, generation='4' * 32, round_key='2' * 32, canonical_round_id=2)
    events = [await conn.fetchval("INSERT INTO runtime_events "
            "(event_type,schema_version,round_id,round_number,event_details) "
            "VALUES ('round_timing_reconciled',1,$1,1,'{}') RETURNING id", rid) for rid in (1, 2)]
    await conn.execute(MIGRATION.read_text())
    return events


async def insert(conn, event, **changes):
    values = dict(source_key='fixture', generation='3' * 32, canonical_round_id=1, event_id=event,
                  link_snapshot='{}', before_round=json.dumps(dict(actual_duration_seconds=None,
                      total_pause_seconds=0, pause_count=0)),
                  after_values=json.dumps(dict(actual_duration_seconds=600,total_pause_seconds=10,pause_count=1)))
    values.update(changes)
    await conn.execute('INSERT INTO runtime_gametime_applications (' + ','.join(values) + ') VALUES ('
        + ','.join(f'${i}' for i in range(1, len(values) + 1)) + ')', *values.values())


def test_bootstrap_contains_exact_migration_once():
    schema = (ROOT / 'tools/schema_postgresql.sql').read_text()
    assert schema.count(MIGRATION.read_text().strip()) == 1


async def test_no_backfill_unique_parent_event_and_restrictive_fks(acl_db):
    conn = acl_db
    one, two = await prepare(conn)
    assert await conn.fetchval('SELECT count(*) FROM runtime_gametime_applications') == 0
    await insert(conn, one)
    before = await conn.fetch('SELECT * FROM runtime_gametime_applications')
    await conn.execute(MIGRATION.read_text())
    assert await conn.fetch('SELECT * FROM runtime_gametime_applications') == before
    with pytest.raises(asyncpg.UniqueViolationError):
        async with conn.transaction():
            await insert(conn, two, generation='4' * 32)  # Only canonical parent duplicates.
    with pytest.raises(asyncpg.UniqueViolationError):
        async with conn.transaction():
            await insert(conn, one, generation='4' * 32, canonical_round_id=2)  # Only event duplicates.
    for statement, args in [
        ('DELETE FROM runtime_gametime_links WHERE generation=$1', ('3' * 32,)),
        ('DELETE FROM runtime_events WHERE id=$1', (one,)),
    ]:
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            async with conn.transaction():
                await conn.execute(statement, *args)
    assert await conn.fetch('SELECT * FROM runtime_gametime_applications') == before


@pytest.mark.parametrize('column,value', [
    ('generation', 'f' * 32), ('canonical_round_id', 999), ('event_id', 999),
])
async def test_missing_parent_refused(acl_db, column, value):
    one, _ = await prepare(acl_db)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        async with acl_db.transaction():
            await insert(acl_db, one, **{column: value})


@pytest.mark.parametrize('column,value', [
    ('link_snapshot', '[]'), ('before_round', '{}'), ('before_round', '[]'),
    ('before_round', '{"actual_duration_seconds":0,"total_pause_seconds":0,"pause_count":0}'),
    ('after_values', '{}'), ('after_values', '[]'),
    ('after_values', '{"actual_duration_seconds":0,"total_pause_seconds":0,"pause_count":0}'),
    ('after_values', '{"actual_duration_seconds":600,"total_pause_seconds":0,"pause_count":0,"dpm":10}'),
])
async def test_invalid_or_overbroad_snapshot_refused(acl_db, column, value):
    one, _ = await prepare(acl_db)
    with pytest.raises(asyncpg.CheckViolationError):
        async with acl_db.transaction():
            await insert(acl_db, one, **{column: value})


async def test_private_replay_revokes_direct_and_column_grants_preserves_defaults(acl_db):
    conn = acl_db
    await prepare(conn)
    defaults = await default_acls(conn)
    for grantee in ('PUBLIC', 'website_app'):
        await conn.execute(f'GRANT SELECT ON runtime_gametime_applications TO {grantee}')
        await conn.execute(f'GRANT UPDATE(before_round) ON runtime_gametime_applications TO {grantee}')
    await conn.execute(MIGRATION.read_text())
    assert await default_acls(conn) == defaults
    for action in ('SELECT * FROM runtime_gametime_applications',
                   'INSERT INTO runtime_gametime_applications DEFAULT VALUES',
                   "UPDATE runtime_gametime_applications SET before_round='{}'",
                   'DELETE FROM runtime_gametime_applications'):
        await denied(conn, action)


@pytest.mark.parametrize('access', ['table', 'column', 'owner'])
async def test_inherited_access_refused(acl_db, access):
    conn = acl_db
    await prepare(conn)
    role = await reachable_role(conn)
    if access == 'owner':
        await conn.execute(f'ALTER TABLE runtime_gametime_applications OWNER TO "{role}"')
    else:
        permission = 'SELECT(before_round)' if access == 'column' else 'SELECT'
        await conn.execute(f'GRANT {permission} ON runtime_gametime_applications TO "{role}"')
    with pytest.raises(asyncpg.RaiseError, match='retains inherited gametime application access'):
        async with conn.transaction():
            await conn.execute(MIGRATION.read_text())
