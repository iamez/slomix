"""Real PostgreSQL consumer commit/rollback through the HTTP namespace reader."""

import subprocess
from pathlib import Path

import asyncpg
import pytest

from shared.runtime_cache_consumer import consume_http_cache_events
from tests.integration.test_lua_override_boundary_pg import adapter_for
from tests.integration.test_runtime_cache_consumer_pg import cache_db, event  # noqa: F401
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401
from tests.unit.test_runtime_http_cache_generation import PATH, client_for
from website.backend.services import runtime_cache_generation as service
from website.backend.services.http_cache_backend import MemoryCacheBackend


async def test_committed_consumer_generation_controls_two_http_workers(cache_db, monkeypatch):  # noqa: F811
    writer, reader = cache_db
    monkeypatch.setenv("RUNTIME_HTTP_CACHE_NAMESPACE_ENABLED", "true")
    monkeypatch.setattr(service, "get_db_pool", lambda: adapter_for(reader))
    await writer.execute("INSERT INTO rounds VALUES(42,1,7)")
    assert (await consume_http_cache_events(writer)).generation == 0

    async def endpoint():
        return {"session": await reader.fetchval("SELECT gaming_session_id FROM rounds WHERE id=42")}

    async with client_for(MemoryCacheBackend(), service.read_http_cache_generation, endpoint) as one, \
            client_for(MemoryCacheBackend(), service.read_http_cache_generation, endpoint) as two:
        for client in (one, two):
            assert (await client.get(PATH)).json() == {"session": 7}
            assert (await client.get(PATH)).headers["X-Cache"] == "HIT"

        # Neither uncommitted data nor an uncommitted epoch are visible to HTTP.
        transaction = writer.transaction()
        await transaction.start()
        try:
            await writer.execute("UPDATE rounds SET gaming_session_id=9")
            await writer.execute("UPDATE runtime_cache_generations SET generation=10")
            assert await service.read_http_cache_generation() == 0
            assert (await one.get(PATH)).json() == {"session": 7}
        finally:
            await transaction.rollback()

        async with writer.transaction():
            await writer.execute("UPDATE rounds SET gaming_session_id=8")
            await event(writer)
        assert await reader.fetchval("SELECT gaming_session_id FROM rounds WHERE id=42") == 8
        # Consumer lag is explicit: this slice does not poll or consume on GET.
        assert (await one.get(PATH)).json() == {"session": 7}
        await writer.execute("ALTER TABLE runtime_consumer_receipts ADD CONSTRAINT reject_receipt CHECK(false)")
        try:
            await consume_http_cache_events(writer)
        except asyncpg.CheckViolationError:
            pass
        else:
            raise AssertionError("Receipt rejection must roll back generation")
        assert await service.read_http_cache_generation() == 0
        assert await reader.fetchval("SELECT count(*) FROM runtime_consumer_receipts") == 0
        await writer.execute("ALTER TABLE runtime_consumer_receipts DROP CONSTRAINT reject_receipt")
        assert (await consume_http_cache_events(writer)).generation == 1
        assert await reader.fetchval("SELECT generation FROM runtime_cache_generations") == 1
        for client in (one, two):
            response = await client.get(PATH)
            assert response.headers["X-Cache"] == "MISS"
            assert response.json() == {"session": 8}
            assert (await client.get(PATH)).headers["X-Cache"] == "HIT"
        # Missing schema must bypass even a warm, otherwise usable cache.
        await writer.execute("DROP TABLE runtime_cache_generations")
        response = await one.get(PATH)
        assert response.json() == {"session": 8}
        assert response.headers["X-Cache"] == "BYPASS-GENERATION"
        assert response.headers["Cache-Control"] == "no-store"
    print("PG/HTTP proof: rollback keeps generation0; committed receipt advances1; both workers MISS session8; missing schema bypasses")


async def test_website_role_reads_generation_but_cannot_write(cache_db, monkeypatch):  # noqa: F811
    writer, _ = cache_db
    migration = (Path(__file__).resolve().parents[2] / "migrations/092_runtime_cache_generation_read_grant.sql").read_text()
    # Only the explicitly configured disposable cluster/CI service is reachable.
    # Roll back role creation as well as grants; never modify an existing role.
    assert not await writer.fetchval("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='website_app')")
    await writer.execute(migration)  # Role absent is a valid bootstrap state.
    await consume_http_cache_events(writer)
    monkeypatch.setattr(service, "get_db_pool", lambda: adapter_for(writer))
    transaction = writer.transaction()
    await transaction.start()
    try:
        await writer.execute("CREATE ROLE website_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT")
        schema = await writer.fetchval("SELECT current_schema()")
        await writer.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO website_app')
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            async with writer.transaction():
                await writer.execute("SET LOCAL ROLE website_app")
                await service.read_http_cache_generation()
        await writer.execute(migration)
        await writer.execute(migration)  # Idempotent grants.
        async with writer.transaction():
            await writer.execute("SET LOCAL ROLE website_app")
            assert await service.read_http_cache_generation() == 0
            assert await writer.fetchval("SELECT current_user") == "website_app"
            for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                assert not await writer.fetchval(
                    "SELECT has_table_privilege(current_user, 'runtime_cache_generations', $1)", privilege,
                )
            assert not await writer.fetchval(
                "SELECT has_table_privilege(current_user, 'runtime_consumer_receipts', 'SELECT')",
            )
            await writer.execute("RESET ROLE")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            async with writer.transaction():
                await writer.execute("SET LOCAL ROLE website_app")
                await writer.execute("UPDATE runtime_cache_generations SET generation=generation+1")
    finally:
        await transaction.rollback()
    assert not await writer.fetchval("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='website_app')")


def test_generation_grant_registration_and_bootstrap():
    root = Path(__file__).resolve().parents[2]
    name = "092_runtime_cache_generation_read_grant.sql"
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; printf "%s\\n" "${MIGRATIONS[@]}"',
         "release-config", str(root / "scripts/release_configs/v1.45.0.sh")],
        check=True, capture_output=True, text=True, timeout=5,
    )
    assert name in result.stdout.splitlines()
    assert (root / "migrations" / name).read_text().strip() in (root / "tools/schema_postgresql.sql").read_text()
