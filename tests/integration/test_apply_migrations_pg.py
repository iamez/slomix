"""Migration runner integration tests against real PostgreSQL (AUD-002).

The FakeConn unit tests cannot prove transactional semantics — PostgreSQL's
aborted-transaction state and rollback behavior are exactly what the old
runner got wrong. These tests use an explicitly allowed private/CI cluster
and prove:

- migration SQL + ledger success row commit atomically;
- a failing migration rolls back its DDL, records a failure row in a new
  transaction, and exits non-zero;
- checksum drift on an applied file refuses further applies;
- --validate reports drift with a non-zero exit.

Every test owns a new database including its migration ledger. No existing
application or shared CI ledger is modified. Missing opt-in skips; a requested
but invalid/unavailable target fails. Collection never loads application .env.
"""
import hashlib
import importlib.util
import os
import uuid
from pathlib import Path

import asyncpg
import pytest

from tests.disposable_database import isolated_database


@pytest.fixture
async def migration_target():
    """Permission is explicit; all requested infrastructure errors propagate."""
    if not os.getenv("RUNTIME_EVENTS_TEST_SOCKET") and not os.getenv("RUNTIME_EVENTS_TEST_CI"):
        pytest.skip("Disposable PostgreSQL not explicitly configured")
    async with isolated_database() as config:
        yield {key: config[key] for key in ("host", "port", "database", "user", "password")}


@pytest.fixture
def migration_runner(monkeypatch):
    """Load a separate real runner instance with dotenv discovery disabled."""
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    path = Path(__file__).resolve().parents[2] / "scripts/apply_migrations.py"
    spec = importlib.util.spec_from_file_location("isolated_migration_runner", path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner


@pytest.fixture
def runner_env(monkeypatch, tmp_path, migration_target, migration_runner):
    """Real runner settings resolve only to this fixture's owned database."""
    for key, value in migration_target.items():
        monkeypatch.setenv("POSTGRES_" + key.upper(), str(value))
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    monkeypatch.setattr(migration_runner, "MIGRATIONS_DIR", mig_dir)

    async def connect_owned():
        resolved = migration_runner.get_connection_kwargs()
        if resolved != migration_target:
            raise AssertionError("Migration runner escaped its owned test database")
        return await asyncpg.connect(**resolved, timeout=5, command_timeout=5, ssl=False)

    # Only connection setup is bounded/restricted; execute real runner SQL,
    # transaction control, ledger writes and checksum/exit behavior unchanged.
    monkeypatch.setattr(migration_runner, "get_connection", connect_owned)
    return mig_dir


@pytest.fixture
async def pg(runner_env, migration_target):
    """Independent reader; close before the owning fixture drops its database."""
    conn = await asyncpg.connect(**migration_target, timeout=5, command_timeout=5, ssl=False)
    ns = f"migit_{uuid.uuid4().hex[:8]}"
    try:
        assert await conn.fetchval("SELECT current_database()") == migration_target["database"]
        assert await conn.fetchval("SELECT to_regclass('public.schema_migrations')") is None
        yield conn, ns
    finally:
        await conn.close(timeout=5)


async def _ledger_row(conn, filename):
    return await conn.fetchrow(
        "SELECT success, checksum FROM schema_migrations WHERE filename = $1",
        filename,
    )


async def _table_exists(conn, name):
    return await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
        name,
    )


@pytest.mark.asyncio
async def test_success_is_atomic_with_ledger(pg, runner_env, migration_runner):
    conn, ns = pg
    (runner_env / f"001_{ns}_ok.sql").write_text(
        f"BEGIN;\nCREATE TABLE {ns}_ok (x INTEGER);\nCOMMIT;\n"
    )

    await migration_runner.cmd_apply()

    assert await _table_exists(conn, f"{ns}_ok")
    row = await _ledger_row(conn, f"001_{ns}_ok.sql")
    assert row is not None and row["success"] is True
    assert row["checksum"] == hashlib.sha256((runner_env / f"001_{ns}_ok.sql").read_bytes()).hexdigest()


@pytest.mark.asyncio
async def test_failure_rolls_back_ddl_and_exits_nonzero(pg, runner_env, migration_runner):
    """The failing file first creates a table, then errors. The old runner
    left PostgreSQL in aborted-transaction state and exited 0; the new one
    must roll the table back, record success=FALSE, and exit 1."""
    conn, ns = pg
    (runner_env / f"001_{ns}_fail.sql").write_text(
        f"BEGIN;\n"
        f"CREATE TABLE {ns}_partial (x INTEGER);\n"
        f"INSERT INTO {ns}_does_not_exist VALUES (1);\n"
        f"COMMIT;\n"
    )

    with pytest.raises(SystemExit) as exc:
        await migration_runner.cmd_apply()
    assert exc.value.code == 1

    assert not await _table_exists(conn, f"{ns}_partial"), (
        "DDL from the failed migration must be rolled back"
    )
    row = await _ledger_row(conn, f"001_{ns}_fail.sql")
    assert row is not None and row["success"] is False, (
        "failure must be recorded in a fresh transaction after rollback"
    )


@pytest.mark.asyncio
async def test_ledger_failure_also_rolls_back_migration_ddl(pg, runner_env, migration_runner, capsys):
    """An error in the success ledger write must undo the preceding DDL too."""
    conn, ns = pg
    await migration_runner.ensure_tracking_table(conn)
    await conn.execute("""
        CREATE FUNCTION reject_success() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.success THEN
                RAISE EXCEPTION 'synthetic success ledger rejection';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER reject_success BEFORE INSERT OR UPDATE ON schema_migrations
        FOR EACH ROW EXECUTE FUNCTION reject_success();
    """)
    filename = f"001_{ns}_ledger_failure.sql"
    (runner_env / filename).write_text(f"CREATE TABLE {ns}_partial (x INTEGER);")
    with pytest.raises(SystemExit) as exc:
        await migration_runner.cmd_apply()
    assert exc.value.code == 1
    assert "synthetic success ledger rejection" in capsys.readouterr().out
    assert not await _table_exists(conn, f"{ns}_partial")
    row = await _ledger_row(conn, filename)
    assert row is not None and row["success"] is False
    assert row["checksum"] == hashlib.sha256((runner_env / filename).read_bytes()).hexdigest()


@pytest.mark.asyncio
async def test_checksum_drift_refuses_apply_and_fails_validate(pg, runner_env, migration_runner, capsys):
    conn, ns = pg
    ok_file = runner_env / f"001_{ns}_ok.sql"
    ok_file.write_text(f"BEGIN;\nCREATE TABLE {ns}_ok (x INTEGER);\nCOMMIT;\n")
    await migration_runner.cmd_apply()

    # Tamper with the applied file → both apply and validate must fail.
    ok_file.write_text("SELECT 'tampered';")
    (runner_env / f"002_{ns}_new.sql").write_text("SELECT 1;")

    with pytest.raises(SystemExit) as exc:
        await migration_runner.cmd_apply()
    assert exc.value.code == 1
    assert "checksum mismatch" in capsys.readouterr().out
    assert await _ledger_row(conn, f"002_{ns}_new.sql") is None, (
        "nothing may be applied while drift is unresolved"
    )

    with pytest.raises(SystemExit) as exc:
        await migration_runner.cmd_validate()
    assert exc.value.code == 1
