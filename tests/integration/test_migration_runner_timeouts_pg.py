"""Real migration entrypoint against a new, explicitly opted-in private DB."""

import asyncio
import os
import sys
import time
from pathlib import Path

import asyncpg
import pytest

from tests.integration import test_apply_migrations_pg as migration_fixtures

migration_runner = migration_fixtures.migration_runner
migration_target = migration_fixtures.migration_target


@pytest.fixture
def bounded_runner(monkeypatch, tmp_path, migration_target, migration_runner):
    for key, value in migration_target.items():
        monkeypatch.setenv("POSTGRES_" + key.upper(), str(value))
    for name, value in (("CONNECT", "2"), ("COMMAND", "5"), ("STATEMENT", "2"), ("LOCK", "1")):
        monkeypatch.setenv(f"MIGRATION_{name}_TIMEOUT_SECONDS", value)
    monkeypatch.setattr(migration_runner, "MIGRATIONS_DIR", tmp_path)
    assert migration_runner.get_connection_kwargs() == migration_target
    return migration_runner


async def test_statement_timeout_rolls_back_and_records_failure(bounded_runner, migration_target, capsys):
    runner = bounded_runner
    (runner.MIGRATIONS_DIR / "001_slow.sql").write_text(
        "CREATE TABLE owned_timeout_probe (x int); SELECT pg_sleep(10);", encoding="utf-8",
    )
    start = time.monotonic()
    with pytest.raises(SystemExit) as error:
        await runner.cmd_apply()
    assert error.value.code == 1
    elapsed = time.monotonic() - start
    assert elapsed < 8
    assert "canceling statement due to statement timeout" in capsys.readouterr().out
    print(f"Real runner statement timeout: {elapsed:.3f}s; exit=1; checking rollback/ledger")
    reader = await asyncpg.connect(**migration_target, timeout=5, command_timeout=5, ssl=False)
    try:
        assert await reader.fetchval("SELECT to_regclass('owned_timeout_probe')") is None
        assert await reader.fetchval("SELECT success FROM schema_migrations WHERE filename='001_slow.sql'") is False
        assert await reader.fetchval("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND application_name='slomix-migrations'") == 0
        # A timeout is retryable, not an applied migration or a poisoned runner.
        (runner.MIGRATIONS_DIR / "001_slow.sql").write_text(
            "CREATE TABLE owned_timeout_probe (x int);", encoding="utf-8",
        )
        await runner.cmd_apply()
        assert await reader.fetchval("SELECT to_regclass('owned_timeout_probe')") is not None
        assert await reader.fetchval("SELECT success FROM schema_migrations WHERE filename='001_slow.sql'") is True
    finally:
        await reader.close(timeout=5)


async def test_real_cli_lock_timeout_is_nonzero_and_releases_connection(bounded_runner, migration_target):
    runner = bounded_runner
    blocker = await asyncpg.connect(**migration_target, timeout=5, command_timeout=5, ssl=False)
    try:
        await runner.ensure_tracking_table(blocker)
        async with blocker.transaction():
            await blocker.execute("LOCK TABLE schema_migrations IN ACCESS EXCLUSIVE MODE")
            start = time.monotonic()
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(Path(runner.__file__)), "--status", "--json",
                env=dict(os.environ), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=8)
            assert proc.returncode != 0, stdout.decode()
            assert b"canceling statement due to lock timeout" in stderr, stderr.decode()
            assert time.monotonic() - start < 8
            print(f"Real CLI lock timeout: {time.monotonic() - start:.3f}s; exit={proc.returncode}")
        assert await blocker.fetchval("SELECT count(*) FROM schema_migrations") == 0
        assert await blocker.fetchval("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND application_name='slomix-migrations'") == 0
    finally:
        await blocker.close(timeout=5)
