"""Migration runner integration tests against real PostgreSQL (AUD-002).

The FakeConn unit tests cannot prove transactional semantics — PostgreSQL's
aborted-transaction state and rollback behavior are exactly what the old
runner got wrong. These tests use the CI postgres service (POSTGRES_TEST_*)
and prove:

- migration SQL + ledger success row commit atomically;
- a failing migration rolls back its DDL, records a failure row in a new
  transaction, and exits non-zero;
- checksum drift on an applied file refuses further applies;
- --validate reports drift with a non-zero exit.

Each test uses uniquely-prefixed table/ledger names and cleans up after
itself, so sharing the CI database with other tests is safe.
"""
import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

asyncpg = pytest.importorskip("asyncpg")

from scripts.apply_migrations import cmd_apply, cmd_validate  # noqa: E402

TEST_DB = {
    "host": os.getenv("POSTGRES_TEST_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_TEST_PORT", "5432")),
    "database": os.getenv("POSTGRES_TEST_DATABASE", "etlegacy_test"),
    "user": os.getenv("POSTGRES_TEST_USER", "etlegacy_user"),
    "password": os.getenv("POSTGRES_TEST_PASSWORD", "etlegacy_test_password"),
}


async def _connect_or_skip():
    try:
        return await asyncpg.connect(timeout=5, **TEST_DB)
    except (TimeoutError, OSError, asyncpg.PostgresError) as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")


@pytest.fixture
def runner_env(monkeypatch, tmp_path):
    """Point the runner at the test DB and an isolated migrations dir."""
    monkeypatch.setenv("POSTGRES_HOST", TEST_DB["host"])
    monkeypatch.setenv("POSTGRES_PORT", str(TEST_DB["port"]))
    monkeypatch.setenv("POSTGRES_DATABASE", TEST_DB["database"])
    monkeypatch.setenv("POSTGRES_USER", TEST_DB["user"])
    monkeypatch.setenv("POSTGRES_PASSWORD", TEST_DB["password"])
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    monkeypatch.setattr("scripts.apply_migrations.MIGRATIONS_DIR", mig_dir)
    return mig_dir


@pytest.fixture
async def pg(runner_env):
    """Direct verification connection + per-test unique namespace + cleanup."""
    conn = await _connect_or_skip()
    ns = f"migit_{uuid.uuid4().hex[:8]}"
    yield conn, ns
    await conn.execute(f"DROP TABLE IF EXISTS {ns}_ok, {ns}_partial")
    await conn.execute(
        "DELETE FROM schema_migrations WHERE filename LIKE $1", f"%{ns}%"
    )
    await conn.close()


async def _seed_ledger(conn, ns):
    """Non-empty ledger bypasses the populated-DB auto-baseline guard."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id SERIAL PRIMARY KEY, version TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL UNIQUE, checksum TEXT,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            applied_by TEXT DEFAULT 'manual', execution_ms INTEGER,
            success BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)
    await conn.execute(
        "INSERT INTO schema_migrations (version, filename, applied_by) "
        "VALUES ($1, $2, 'test-seed') ON CONFLICT (filename) DO NOTHING",
        f"000_{ns}_seed", f"000_{ns}_seed.sql",
    )


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
async def test_success_is_atomic_with_ledger(pg, runner_env):
    conn, ns = pg
    await _seed_ledger(conn, ns)
    (runner_env / f"001_{ns}_ok.sql").write_text(
        f"BEGIN;\nCREATE TABLE {ns}_ok (x INTEGER);\nCOMMIT;\n"
    )

    await cmd_apply()

    assert await _table_exists(conn, f"{ns}_ok")
    row = await _ledger_row(conn, f"001_{ns}_ok.sql")
    assert row is not None and row["success"] is True
    assert row["checksum"], "success row must record the file checksum"


@pytest.mark.asyncio
async def test_failure_rolls_back_ddl_and_exits_nonzero(pg, runner_env, capsys):
    """The failing file first creates a table, then errors. The old runner
    left PostgreSQL in aborted-transaction state and exited 0; the new one
    must roll the table back, record success=FALSE, and exit 1."""
    conn, ns = pg
    await _seed_ledger(conn, ns)
    (runner_env / f"001_{ns}_fail.sql").write_text(
        f"BEGIN;\n"
        f"CREATE TABLE {ns}_partial (x INTEGER);\n"
        f"INSERT INTO {ns}_does_not_exist VALUES (1);\n"
        f"COMMIT;\n"
    )

    with pytest.raises(SystemExit) as exc:
        await cmd_apply()
    assert exc.value.code == 1

    assert not await _table_exists(conn, f"{ns}_partial"), (
        "DDL from the failed migration must be rolled back"
    )
    row = await _ledger_row(conn, f"001_{ns}_fail.sql")
    assert row is not None and row["success"] is False, (
        "failure must be recorded in a fresh transaction after rollback"
    )


@pytest.mark.asyncio
async def test_checksum_drift_refuses_apply_and_fails_validate(pg, runner_env, capsys):
    conn, ns = pg
    await _seed_ledger(conn, ns)
    ok_file = runner_env / f"001_{ns}_ok.sql"
    ok_file.write_text(f"BEGIN;\nCREATE TABLE {ns}_ok (x INTEGER);\nCOMMIT;\n")
    await cmd_apply()

    # Tamper with the applied file → both apply and validate must fail.
    ok_file.write_text("SELECT 'tampered';")
    (runner_env / f"002_{ns}_new.sql").write_text("SELECT 1;")

    with pytest.raises(SystemExit) as exc:
        await cmd_apply()
    assert exc.value.code == 1
    assert "checksum mismatch" in capsys.readouterr().out
    assert await _ledger_row(conn, f"002_{ns}_new.sql") is None, (
        "nothing may be applied while drift is unresolved"
    )

    with pytest.raises(SystemExit) as exc:
        await cmd_validate()
    assert exc.value.code == 1
