"""Actual runtime ACL repair with permissive inherited defaults, isolated only."""

import subprocess
import uuid
from pathlib import Path

import asyncpg
import pytest

from tests.integration.test_runtime_events_pg import connection_options

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = "093_runtime_website_least_privilege.sql"
TABLES = (
    "runtime_events", "lua_correction_inputs", "lua_correction_receipts",
    "lua_correction_attempts", "runtime_consumer_receipts", "runtime_cache_generations",
)


@pytest.fixture
async def acl_db():
    conn = await asyncpg.connect(**connection_options())
    tx = conn.transaction()
    await tx.start()
    try:
        # Existing roles are never changed; new test roles roll back with the fixture.
        if not await conn.fetchval("SELECT EXISTS(SELECT FROM pg_roles WHERE rolname='website_app')"):
            await conn.execute("CREATE ROLE website_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT")
        schema = "runtime_acl_test_" + uuid.uuid4().hex
        await conn.execute(f'CREATE SCHEMA "{schema}"')
        await conn.execute(f'SET LOCAL search_path TO "{schema}"')
        await conn.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO website_app')
        # Reproduce the restored DEV defaults without changing public/default ACLs.
        await conn.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA "{schema}" '
                           'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO website_app')
        await conn.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA "{schema}" '
                           'GRANT ALL PRIVILEGES ON SEQUENCES TO website_app')
        await conn.execute("CREATE TABLE legacy_fixture (id BIGSERIAL PRIMARY KEY)")
        for number in range(83, 93):
            files = list((ROOT / "migrations").glob(f"{number:03}_*.sql"))
            assert len(files) == 1
            await conn.execute(files[0].read_text())
        yield conn
    finally:
        await tx.rollback()
        await conn.close(timeout=5)


async def default_acls(conn):
    return await conn.fetch("SELECT defaclrole, defaclnamespace, defaclobjtype, defaclacl::text "
                            "FROM pg_default_acl ORDER BY oid")


async def denied(conn, sql):
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        async with conn.transaction():
            await conn.execute("SET LOCAL ROLE website_app")
            await conn.execute(sql)


async def test_restricts_inherited_runtime_grants_without_changing_legacy_or_defaults(acl_db):
    conn = acl_db
    defaults_before = await default_acls(conn)
    for table in TABLES:
        assert await conn.fetchval("SELECT has_table_privilege('website_app', $1, 'INSERT')", table)
    sequences = [await conn.fetchval("SELECT pg_get_serial_sequence($1, 'id')", table)
                 for table in ("runtime_events", "lua_correction_inputs")]
    for sequence in sequences:
        assert await conn.fetchval("SELECT has_sequence_privilege('website_app', $1, 'USAGE')", sequence)
    # 092's SELECT grant does not imply read-only: prove the old write capability.
    async with conn.transaction():
        await conn.execute("SET LOCAL ROLE website_app")
        await conn.execute("INSERT INTO runtime_cache_generations(cache_name) VALUES('http-api')")
        await conn.execute("RESET ROLE")
    migration = (ROOT / "migrations" / MIGRATION).read_text()
    await conn.execute(migration)
    await conn.execute(migration)  # Idempotence must not broaden grants.
    assert await default_acls(conn) == defaults_before
    async with conn.transaction():
        await conn.execute("SET LOCAL ROLE website_app")
        assert await conn.fetchval("SELECT generation FROM runtime_cache_generations") == 0
        await conn.execute("INSERT INTO legacy_fixture DEFAULT VALUES")
        await conn.execute("UPDATE legacy_fixture SET id=id")
        await conn.execute("DELETE FROM legacy_fixture")
        await conn.execute("RESET ROLE")
    for table in TABLES:
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
            expected = table == "runtime_cache_generations" and privilege == "SELECT"
            assert await conn.fetchval(
                "SELECT has_table_privilege('website_app', $1, $2)", table, privilege,
            ) is expected, (table, privilege)
        if table != "runtime_cache_generations":
            await denied(conn, f"SELECT * FROM {table}")
        await denied(conn, f"INSERT INTO {table} DEFAULT VALUES")
        await denied(conn, f"DELETE FROM {table} WHERE false")
        await denied(conn, f"TRUNCATE {table}")
        column = await conn.fetchval(
            "SELECT attname FROM pg_attribute WHERE attrelid=$1::regclass "
            "AND attnum>0 AND NOT attisdropped AND attidentity='' ORDER BY attnum LIMIT 1", table,
        )
        await denied(conn, f'UPDATE {table} SET "{column}"="{column}" WHERE false')
    for sequence in sequences:
        for privilege in ("SELECT", "UPDATE", "USAGE"):
            assert not await conn.fetchval(
                "SELECT has_sequence_privilege('website_app', $1, $2)", sequence, privilege,
            )
        await denied(conn, f"SELECT nextval('{sequence}')")
        await denied(conn, f"SELECT setval('{sequence}', 50)")
        await denied(conn, f"SELECT last_value FROM {sequence}")
    print("ACL proof: six runtime tables restricted, two sequences denied; "
          "generation SELECT and legacy CRUD preserved; default ACLs unchanged")


@pytest.mark.parametrize("object_kind", ["table", "sequence"])
async def test_unrevoked_public_privileges_fail_closed(acl_db, object_kind):
    conn = acl_db
    if object_kind == "table":
        await conn.execute("GRANT INSERT ON runtime_cache_generations TO PUBLIC")
    else:
        sequence = await conn.fetchval("SELECT pg_get_serial_sequence('runtime_events', 'id')")
        await conn.execute(f"GRANT USAGE ON SEQUENCE {sequence} TO PUBLIC")
    with pytest.raises(asyncpg.RaiseError, match=f"retains runtime {object_kind} privileges"):
        async with conn.transaction():
            await conn.execute((ROOT / "migrations" / MIGRATION).read_text())
    # Failed migration is atomic; unrelated effective privileges are not removed.
    assert await conn.fetchval("SELECT has_table_privilege('website_app', 'runtime_events', 'INSERT')")


async def test_non_owner_migration_cannot_falsely_report_success(acl_db):
    conn = acl_db
    with pytest.raises((asyncpg.RaiseError, asyncpg.InsufficientPrivilegeError)):
        async with conn.transaction():
            await conn.execute("SET LOCAL ROLE website_app")
            await conn.execute((ROOT / "migrations" / MIGRATION).read_text())
    assert await conn.fetchval("SELECT has_table_privilege('website_app', 'runtime_events', 'INSERT')")


def test_runtime_privilege_migration_registered_and_in_bootstrap():
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; printf "%s\\n" "${MIGRATIONS[@]}"',
         "release-config", str(ROOT / "scripts/release_configs/v1.45.0.sh")],
        check=True, capture_output=True, text=True, timeout=5,
    )
    assert MIGRATION in result.stdout.splitlines()
    assert (ROOT / "migrations" / MIGRATION).read_text().strip() in (
        ROOT / "tools/schema_postgresql.sql"
    ).read_text()


async def test_missing_generation_grant_cannot_be_certified(acl_db):
    """Fault-inject an ineffective GRANT and execute the actual SQL postcondition."""
    conn = acl_db
    migration = (ROOT / "migrations" / MIGRATION).read_text()
    grant = "GRANT SELECT ON runtime_cache_generations TO website_app;"
    assert migration.count(grant) == 1
    migration = migration.replace(grant, "NULL;")
    with pytest.raises(asyncpg.RaiseError, match="lacks runtime generation read privilege"):
        async with conn.transaction():
            await conn.execute(migration)


async def execute_as_website(conn, sql, *, role=None):
    """Use the real session identity, not the superuser's unrestricted SET ROLE."""
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute("SET LOCAL SESSION AUTHORIZATION website_app")
        if role:
            await conn.execute(f'SET LOCAL ROLE "{role}"')
        return await conn.execute(sql)
    finally:
        await tx.rollback()


async def reachable_role(conn):
    """Transactional two-hop NOINHERIT chain; no existing role is altered."""
    bridge = "acl_bridge_" + uuid.uuid4().hex
    writer = "acl_writer_" + uuid.uuid4().hex
    await conn.execute(f'CREATE ROLE "{bridge}" NOLOGIN NOINHERIT')
    await conn.execute(f'CREATE ROLE "{writer}" NOLOGIN')
    version = int(await conn.fetchval("SHOW server_version_num"))
    options = " WITH INHERIT FALSE, SET TRUE" if version >= 160000 else ""
    await conn.execute(f'GRANT "{writer}" TO "{bridge}"{options}')
    await conn.execute(f'GRANT "{bridge}" TO website_app')
    schema = await conn.fetchval("SELECT current_schema()")
    await conn.execute(f'GRANT USAGE, CREATE ON SCHEMA "{schema}" TO "{writer}"')
    capability = "SET" if version >= 160000 else "MEMBER"
    assert await conn.fetchval("SELECT pg_has_role('website_app', $1, $2)", writer, capability)
    assert not await conn.fetchval("SELECT pg_has_role('website_app', $1, 'USAGE')", writer)
    return writer


@pytest.mark.parametrize("grantee_kind", ["public", "reachable-role"])
@pytest.mark.parametrize("privilege", ["SELECT", "INSERT", "UPDATE", "REFERENCES"])
async def test_column_privilege_bypass_fails_closed(acl_db, grantee_kind, privilege):
    conn = acl_db
    role = await reachable_role(conn) if grantee_kind == "reachable-role" else None
    grantee = f'"{role}"' if role else "PUBLIC"
    table, column = ("runtime_events", "event_type") if privilege == "SELECT" else (
        "runtime_cache_generations", "generation",
    )
    await conn.execute(f"GRANT {privilege} ({column}) ON {table} TO {grantee}")
    # Remove direct table grants to isolate the column-level bypass.
    await conn.execute(f"REVOKE ALL PRIVILEGES ON {table} FROM website_app")
    identity = role or "website_app"
    assert not await conn.fetchval("SELECT has_table_privilege($1, $2, $3)", identity, table, privilege)
    assert await conn.fetchval("SELECT has_any_column_privilege($1, $2, $3)", identity, table, privilege)
    if privilege == "SELECT":
        await execute_as_website(conn, "SELECT event_type FROM runtime_events", role=role)
    elif privilege == "UPDATE":
        await execute_as_website(conn, "UPDATE runtime_cache_generations SET generation=9", role=role)
    with pytest.raises(asyncpg.RaiseError, match="retains runtime table privileges"):
        async with conn.transaction():
            await conn.execute((ROOT / "migrations" / MIGRATION).read_text())


@pytest.mark.parametrize("access", ["table", "sequence", "owner-with-revoked-grants"])
async def test_set_role_bypass_fails_closed(acl_db, access):
    conn = acl_db
    writer = await reachable_role(conn)
    if access == "sequence":
        sequence = await conn.fetchval("SELECT pg_get_serial_sequence('runtime_events', 'id')")
        await conn.execute(f'GRANT USAGE ON SEQUENCE {sequence} TO "{writer}"')
        operation = f"SELECT nextval('{sequence}')"
        expected = "sequence"
    elif access == "table":
        await conn.execute(f'GRANT INSERT ON runtime_cache_generations TO "{writer}"')
        operation = "INSERT INTO runtime_cache_generations(cache_name) VALUES('role-proof')"
        expected = "table"
    else:
        await conn.execute(f'ALTER TABLE runtime_cache_generations OWNER TO "{writer}"')
        await conn.execute(f'REVOKE ALL PRIVILEGES ON runtime_cache_generations FROM "{writer}"')
        assert not await conn.fetchval(
            "SELECT has_table_privilege($1, 'runtime_cache_generations', 'INSERT')", writer,
        )
        operation = "ALTER TABLE runtime_cache_generations ADD COLUMN owner_proof INTEGER"
        expected = "table"
    await execute_as_website(conn, operation, role=writer)
    with pytest.raises(asyncpg.RaiseError, match=f"retains runtime {expected} privileges"):
        async with conn.transaction():
            await conn.execute((ROOT / "migrations" / MIGRATION).read_text())


@pytest.mark.parametrize("grantee_kind", ["public", "reachable-role", "pg-maintain"])
async def test_pg17_maintain_privilege_fails_closed(acl_db, grantee_kind):
    conn = acl_db
    if int(await conn.fetchval("SHOW server_version_num")) < 170000:
        pytest.skip("MAINTAIN requires a real PostgreSQL 17+ server")
    role = await reachable_role(conn) if grantee_kind != "public" else None
    if grantee_kind == "pg-maintain":
        await conn.execute(f'GRANT pg_maintain TO "{role}"')
    else:
        grantee = f'"{role}"' if role else "PUBLIC"
        await conn.execute(f"GRANT MAINTAIN ON runtime_cache_generations TO {grantee}")
    await execute_as_website(conn, "ANALYZE runtime_cache_generations", role=role)
    with pytest.raises(asyncpg.RaiseError, match="retains runtime table privileges"):
        async with conn.transaction():
            await conn.execute((ROOT / "migrations" / MIGRATION).read_text())


async def test_pg16_membership_without_set_or_inherit_does_not_false_alarm(acl_db):
    conn = acl_db
    if int(await conn.fetchval("SHOW server_version_num")) < 160000:
        pytest.skip("Independent membership SET/INHERIT options require PostgreSQL 16+")
    writer = "acl_unreachable_" + uuid.uuid4().hex
    await conn.execute(f'CREATE ROLE "{writer}" NOLOGIN')
    await conn.execute(f'GRANT INSERT ON runtime_cache_generations TO "{writer}"')
    await conn.execute(f'GRANT "{writer}" TO website_app WITH INHERIT FALSE, SET FALSE')
    assert await conn.fetchval("SELECT pg_has_role('website_app', $1, 'MEMBER')", writer)
    for capability in ("SET", "USAGE"):
        assert not await conn.fetchval("SELECT pg_has_role('website_app', $1, $2)", writer, capability)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await execute_as_website(conn, "SELECT 1", role=writer)
    await conn.execute((ROOT / "migrations" / MIGRATION).read_text())
