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

Skips when the CI PostgreSQL service is unavailable (local dev) or the test
user cannot CREATE DATABASE.

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

import os
import re
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

asyncpg = pytest.importorskip("asyncpg")

from scripts.apply_migrations import (  # noqa: E402
    cmd_baseline,
    cmd_validate,
    discover_migrations,
    split_statements,
    unwrap_outer_transaction,
)

REPO = Path(__file__).resolve().parents[2]
DUMP = REPO / "tools" / "schema_postgresql.sql"

TEST_DB = {
    "host": os.getenv("POSTGRES_TEST_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_TEST_PORT", "5432")),
    "database": os.getenv("POSTGRES_TEST_DATABASE", "etlegacy_test"),
    "user": os.getenv("POSTGRES_TEST_USER", "etlegacy_user"),
    "password": os.getenv("POSTGRES_TEST_PASSWORD", "etlegacy_test_password"),
}

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


async def _admin_conn():
    try:
        return await asyncpg.connect(timeout=5, **TEST_DB)
    except (TimeoutError, OSError, asyncpg.PostgresError) as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")


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
async def test_dump_contains_every_migration(monkeypatch):
    admin = await _admin_conn()
    parity_db = f"parity_{uuid.uuid4().hex[:8]}"
    try:
        await admin.execute(f'CREATE DATABASE "{parity_db}"')
    except asyncpg.InsufficientPrivilegeError as e:
        # Local dev users typically lack CREATEDB; only the CI service user is
        # guaranteed to have it. Skip (like the connection check) instead of
        # hard-failing the suite outside CI (Copilot on #516).
        await admin.close()
        pytest.skip(f"test user cannot CREATE DATABASE: {e}")
    try:
        conn = await asyncpg.connect(**{**TEST_DB, "database": parity_db})
        try:
            # 1) canonical dump onto the empty database — every error is real.
            await conn.execute(DUMP.read_text(encoding="utf-8"))
            before = await _snapshot(conn)
            assert before, "dump produced no schema — wrong file?"

            # 2) re-apply every committed migration, statement by statement.
            problems: list[str] = []
            for filename, path in discover_migrations():
                body = unwrap_outer_transaction(path.read_text(encoding="utf-8"))
                for stmt in split_statements(body):
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

            # 3) schema unchanged ⇒ dump ⊇ migrations.
            after = await _snapshot(conn)
            added = sorted(after - before)
            assert not added, (
                "migrations ADDED objects the dump lacks (dump drift):\n"
                + "\n".join(map(str, added[:40]))
            )
        finally:
            await conn.close()

        # 4) the deploy_clean.sh flow: baseline + validate must be clean.
        monkeypatch.setenv("POSTGRES_HOST", TEST_DB["host"])
        monkeypatch.setenv("POSTGRES_PORT", str(TEST_DB["port"]))
        monkeypatch.setenv("POSTGRES_DATABASE", parity_db)
        monkeypatch.setenv("POSTGRES_USER", TEST_DB["user"])
        monkeypatch.setenv("POSTGRES_PASSWORD", TEST_DB["password"])
        await cmd_baseline()
        await cmd_validate()  # exits non-zero on drift; clean = returns
    finally:
        await admin.execute(f'DROP DATABASE IF EXISTS "{parity_db}"')
        await admin.close()
