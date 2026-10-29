"""Immutable timing schema publication; PostgreSQL runs only in opted-in fixtures."""

import hashlib
import subprocess
from pathlib import Path

import asyncpg
import pytest

from tests.integration.test_runtime_website_privileges_pg import acl_db as _acl_db
from tests.integration.test_runtime_website_privileges_pg import default_acls, denied, reachable_role

ROOT = Path(__file__).resolve().parents[2]
acl_db = _acl_db
pytestmark = pytest.mark.timeout(120)
# Applied source bytes recovered from the preserved runtime release, not edited SQL.
APPLIED = {
    '097_runtime_gametime_sources.sql': 'ffd018cb86c58f534cbcbf5a0061d678d0e74af123659bcda3054128b85f8a91',
    '098_runtime_gametime_identities.sql': '14495168444b63d3d742b172fb86eb1d9a9052d5f1b4905c9ef1d654fe531b8a',
    '101_runtime_gametime_links.sql': '80a472fbe41540a250bbda8be29ef895de8f55001a2ec6658686e1719e465dc4',
    '102_runtime_gametime_applications.sql': '00054be52aaf206b29101fd581c25cf0f523e1b50c04e93741e4b523ab81c83f',
    '103_player_track_death_type.sql': '7a969bd2c842b3debb0c693cdabeef768b4002448132b1be4b757027cc9d4cfe',
}


def migration(number):
    files = list((ROOT / 'migrations').glob(f'{number:03}_*.sql'))
    assert len(files) == 1
    return files[0].read_text()


@pytest.mark.parametrize('filename,digest', APPLIED.items())
def test_applied_migration_bytes_are_preserved(filename, digest):
    assert hashlib.sha256((ROOT / 'migrations' / filename).read_bytes()).hexdigest() == digest


def test_release_registers_all_timing_dependencies_once_in_order():
    output = subprocess.run(
        ['bash', '-c', 'source "$1"; printf "%s\\n" "${MIGRATIONS[@]}"',
         'release-config', str(ROOT / 'scripts/release_configs/v1.45.0.sh')],
        check=True, capture_output=True, text=True, timeout=5,
    ).stdout.splitlines()
    names = [next((ROOT / 'migrations').glob(f'{number:03}_*.sql')).name
             for number in range(96, 106)]
    assert all(output.count(name) == 1 for name in names)
    assert [output.index(name) for name in names] == sorted(output.index(name) for name in names)


@pytest.mark.parametrize('number', [97, 98, 101, 102])
def test_bootstrap_contains_exact_timing_migration_once(number):
    schema = (ROOT / 'tools/schema_postgresql.sql').read_text()
    assert schema.count(migration(number).strip()) == 1


async def prepare_sources(conn):
    await conn.execute(migration(97))
    await conn.execute("INSERT INTO lua_correction_inputs "
        "(id,source_key,payload_version,payload_digest,map_name,round_number,round_start_unix,payload) "
        "VALUES (7,'fixture',1,repeat('0',64),'supply',1,1,'{}')")
    await conn.execute("INSERT INTO runtime_gametime_sources VALUES "
        "('fixture',repeat('a',32),'gametime-supply-R1-1.json',1,repeat('b',64),7,DEFAULT)")


async def test_identity_migration_preserves_legacy_sources_without_inference(acl_db):
    conn = acl_db
    await prepare_sources(conn)
    before = await conn.fetch('SELECT * FROM runtime_gametime_sources')
    for _ in range(2):
        await conn.execute(migration(97))
        await conn.execute(migration(98))
    assert await conn.fetch('SELECT * FROM runtime_gametime_sources') == before
    assert await conn.fetchval('SELECT count(*) FROM runtime_gametime_identities') == 0
    await conn.execute("INSERT INTO runtime_gametime_identities VALUES "
        "('fixture',repeat('a',32),repeat('c',32),repeat('c',32),1,repeat('c',32),DEFAULT)")
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        async with conn.transaction():
            await conn.execute('DELETE FROM runtime_gametime_sources')
    assert await conn.fetchval('SELECT count(*) FROM runtime_gametime_identities') == 1


@pytest.mark.parametrize('number,table,column', [
    (97, 'runtime_gametime_sources', 'filename'),
    (98, 'runtime_gametime_identities', 'round_id'),
])
async def test_private_schema_replay_removes_column_access_preserves_defaults(acl_db, number, table, column):
    conn = acl_db
    await conn.execute(migration(97))
    before = await default_acls(conn)
    await conn.execute(migration(number))
    await conn.execute(f'GRANT SELECT({column}) ON {table} TO website_app')
    await conn.execute(migration(number))
    assert await default_acls(conn) == before
    assert not await conn.fetchval("SELECT has_any_column_privilege('website_app',$1,'SELECT')", table)
    await denied(conn, f'SELECT {column} FROM {table}')


@pytest.mark.parametrize('number,table', [(97, 'runtime_gametime_sources'), (98, 'runtime_gametime_identities')])
@pytest.mark.parametrize('access', ['table', 'column', 'owner'])
async def test_reachable_role_access_refuses_schema_success(acl_db, number, table, access):
    conn = acl_db
    await conn.execute(migration(97))
    await conn.execute(migration(number))
    role = await reachable_role(conn)
    if access == 'owner':
        await conn.execute(f'ALTER TABLE {table} OWNER TO "{role}"')
    else:
        permission = 'SELECT(source_key)' if access == 'column' else 'SELECT'
        await conn.execute(f'GRANT {permission} ON {table} TO "{role}"')
    with pytest.raises(asyncpg.RaiseError, match='retains inherited gametime'):
        async with conn.transaction():
            await conn.execute(migration(number))


async def test_lifecycle_column_is_nullable_repeatable_and_never_backfilled(acl_db):
    conn = acl_db
    await conn.execute('CREATE TABLE player_track (id INTEGER PRIMARY KEY)')
    await conn.execute('INSERT INTO player_track VALUES (1)')
    await conn.execute(migration(103))
    assert await conn.fetchval('SELECT death_type FROM player_track WHERE id=1') is None
    await conn.execute("INSERT INTO player_track VALUES (2,'shutdown')")
    before = await conn.fetch('SELECT * FROM player_track ORDER BY id')
    await conn.execute(migration(103))
    assert await conn.fetch('SELECT * FROM player_track ORDER BY id') == before
    assert [tuple(row) for row in before] == [(1, None), (2, 'shutdown')]
