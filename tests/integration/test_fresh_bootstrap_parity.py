"""Fresh-bootstrap schema parity (IMP-001).

deploy_clean.sh bootstraps a FRESH database from tools/schema_postgresql.sql
and then `--baseline`s the migration ledger — which records every migration as
applied WITHOUT comparing schemas (cmd_baseline just writes rows). That is
only sound if the canonical dump really CONTAINS every migration's effect.
This test proves it on the CI PostgreSQL:

1. create a brand-new empty database;
2. apply the canonical dump;
3. snapshot the schema (columns + indexes);
4. re-apply EVERY committed migration statement-by-statement — "already
   exists" errors are tolerated (they PROVE presence); any other error
   (undefined column/table/…) is drift and fails;
5. snapshot again — it must be IDENTICAL (a migration that silently added
   something the dump lacked would show up here);
6. `--baseline` + `--validate` must then report a clean ledger.

Only missing explicit private/CI opt-in skips. Requested connection, privilege
or cleanup failures fail. Each case owns its database; collection does not load
application dotenv. This test proves presence parity, not safe historical replay.

Known limitation (Codex on #516): this proves PRESENCE parity, not
DEFINITION parity. An idempotent migration (`ADD COLUMN IF NOT EXISTS`,
`CREATE INDEX IF NOT EXISTS`) no-ops when the dump carries an object of the
same NAME but a different type/default/predicate, and the before/after
snapshot stays equal. Definition-level comparison needs a second
migrations-only schema build, which the migration set can't produce on its
own (migrations assume the pre-migration base schema) — tracked as an owner
follow-up in the remediation plan.
"""
from __future__ import annotations

import re
from pathlib import Path

import asyncpg
import pytest

# Reuse the audited target lifecycle and deferred, dotenv-disabled runner.
from tests.integration.test_apply_migrations_pg import (  # noqa: F401
    migration_runner,
    migration_target,
)

REPO = Path(__file__).resolve().parents[2]
DUMP = REPO / "tools" / "schema_postgresql.sql"

# SQLSTATEs that prove the object ALREADY EXISTS in the dump-bootstrapped
# schema — exactly what parity wants. Anything else (undefined column/table,
# syntax, …) means the dump is missing something the migration assumes.
_ALREADY_EXISTS = {
    "42701",  # duplicate_column
    "42P07",  # duplicate_table / duplicate_index
    "42710",  # duplicate_object (constraints, triggers, …)
    "42723",  # duplicate_function
}

_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _has_executable_sql(stmt: str) -> bool:
    """False for comment-only fragments. split_statements() can yield a chunk
    that is ONLY trailing comments (e.g. add_round_status.sql's status legend
    after the final ';'); asyncpg's execute() crashes with an AttributeError
    on such empty queries instead of a PostgresError, so they must be skipped
    — there is nothing to prove parity against anyway."""
    without_blocks = _BLOCK_COMMENT_RE.sub("", stmt)
    return any(
        line.split("--", 1)[0].strip()
        for line in without_blocks.splitlines()
    )


@pytest.fixture
def parity_runner(monkeypatch, migration_target, migration_runner):  # noqa: F811 - imported pytest fixtures
    """Exercise real ledger code, but restrict every connection to the owned DB."""
    for key, value in migration_target.items():
        monkeypatch.setenv("POSTGRES_" + key.upper(), str(value))

    async def connect_owned():
        resolved = migration_runner.get_connection_kwargs()
        if resolved != migration_target:
            raise AssertionError("Parity runner escaped its owned test database")
        return await asyncpg.connect(**resolved, timeout=5, command_timeout=5, ssl=False)

    monkeypatch.setattr(migration_runner, "get_connection", connect_owned)
    return migration_runner


@pytest.fixture
async def parity_connection(parity_runner, migration_target):  # noqa: F811 - imported pytest fixture
    """Reader closes before migration_target removes only its newly owned DB."""
    conn = await parity_runner.get_connection()
    try:
        identity = await conn.fetchrow("SELECT current_database() AS database, current_user AS username")
        if (identity["database"] != migration_target["database"]
                or identity["username"] != migration_target["user"]):
            raise AssertionError("Parity connection database/user identity mismatch")
        yield conn
    finally:
        await conn.close(timeout=5)


async def _snapshot(conn) -> frozenset:
    cols = await conn.fetch(
        """SELECT table_name, column_name, data_type, is_nullable,
                  COALESCE(column_default, '') AS column_default
           FROM information_schema.columns WHERE table_schema = 'public'"""
    )
    idx = await conn.fetch(
        "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public'"
    )
    return frozenset(
        [tuple(r) for r in cols] + [tuple(r) for r in idx]
    )


@pytest.mark.asyncio
async def test_dump_contains_every_migration(parity_connection, parity_runner):
    conn = parity_connection
    # 1) canonical dump onto the empty database — every error is real.
    await conn.execute(DUMP.read_text(encoding="utf-8"), timeout=60)
    # pg_dump resets server bounds; do not let the replay inherit unlimited SQL.
    await conn.execute("SET statement_timeout = '5s'; SET lock_timeout = '1s'")
    before = await _snapshot(conn)
    assert before, "dump produced no schema — wrong file?"

    # 2) re-apply every committed migration, statement by statement.
    problems: list[str] = []
    for filename, path in parity_runner.discover_migrations():
        body = parity_runner.unwrap_outer_transaction(path.read_text(encoding="utf-8"))
        for stmt in parity_runner.split_statements(body):
            if not _has_executable_sql(stmt):
                continue
            try:
                await conn.execute(stmt)
            except asyncpg.PostgresError as e:
                state = getattr(e, "sqlstate", "")
                if state in _ALREADY_EXISTS:
                    continue  # presence proven — parity holds
                problems.append(
                    f"{filename}: [{state}] {e} :: {stmt[:120]}"
                )
    assert not problems, (
        "canonical dump is missing effects these migrations assume:\n"
        + "\n".join(problems)
    )

    # 3) No observed column/index additions or removals (presence parity only).
    # `after - before` catches objects a migration adds that the dump
    # lacks; `before - after` catches objects a migration REMOVES that
    # the dump still creates (e.g. 045's dropped monitoring tables) —
    # deploy_clean.sh baselines immediately after the dump, so either
    # direction means the fresh ledger lies about the schema (Codex
    # on #516).
    after = await _snapshot(conn)
    added = sorted(after - before)
    removed = sorted(before - after)
    assert not added and not removed, (
        "dump ≠ migrations:\n"
        + "".join(f"  MIGRATION-ONLY (dump lacks): {a}\n" for a in added[:25])
        + "".join(f"  DUMP-ONLY (migration removes): {r}\n" for r in removed[:25])
    )

    # Real baseline/validate on the same pinned target, not an application DB.
    await parity_runner.cmd_baseline()
    await parity_runner.cmd_validate()
    # This reader is independent of the runner's now-closed ledger connections.
    ledger = await conn.fetch("SELECT filename, success, checksum FROM schema_migrations")
    expected = {filename for filename, _ in parity_runner.discover_migrations()}
    assert {row['filename'] for row in ledger} == expected
    assert all(row['success'] for row in ledger)
    assert await conn.fetchval('SELECT count(*) FROM schema_migrations') == len(ledger) == len(expected)
    print(f'Bootstrap presence proof: {len(before)} unchanged column/index entries; '
          f'{len(ledger)} ledger rows; {sum(row["checksum"] is None for row in ledger)} historical NULL checksums')
