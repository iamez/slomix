#!/usr/bin/env python3
"""
Database migration runner for Slomix ET:Legacy Bot.

Tracks applied migrations in a `schema_migrations` table and applies
any pending .sql files from the migrations/ directory.

Usage:
    python scripts/apply_migrations.py                       # Apply pending migrations
    python scripts/apply_migrations.py --only FILE [FILE..]  # Apply only the named pending files
    python scripts/apply_migrations.py --status [--json]     # Show migration status
    python scripts/apply_migrations.py --validate [--json]   # Exit non-zero on pending/failed/checksum drift
    python scripts/apply_migrations.py --baseline            # Mark all as pre-applied
    python scripts/apply_migrations.py --mark FILE [FILE..]  # Record specific files as applied without running them

Exit codes:
    0  success / nothing to do / validation clean
    1  migration failure, checksum drift, validation drift, or refused operation
    2  bad CLI arguments

Environment variables (or .env file):
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DATABASE,
    POSTGRES_USER, POSTGRES_PASSWORD

    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD are accepted as
    fallbacks — production .env files in this repo historically used
    DB_* names. POSTGRES_* takes precedence when both are present.
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import asyncpg
except ImportError:
    print("ERROR: asyncpg not installed. Run: pip install asyncpg")
    sys.exit(1)

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass  # python-dotenv is optional

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

# Session-level advisory lock key so two runners (or a runner racing a deploy)
# can never interleave migration writes. Value is the ASCII of 'SLOMIX_M'.
ADVISORY_LOCK_KEY = 0x534C4F4D49585F4D

# ── Ordering ──────────────────────────────────────────────────────────

_NUM_PREFIX = re.compile(r"^(\d+)")


def _sort_key(filename: str) -> tuple:
    """Sort: unnumbered files first (alpha), then numbered by prefix."""
    m = _NUM_PREFIX.match(filename)
    if m:
        return (1, int(m.group(1)), filename)
    return (0, 0, filename)


def _version_from_filename(filename: str) -> str:
    """Extract a unique version key from a migration filename."""
    return filename.removesuffix(".sql")


def _file_checksum(path: Path) -> str:
    """SHA-256 hex digest of a file's contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── SQL transaction-control analysis ──────────────────────────────────

class MigrationRejected(Exception):
    """The migration file contains transaction control the runner cannot wrap."""


def _mask_sql_noise(sql: str) -> str:
    """Return a same-length copy with comments and string literals blanked.

    Same-length masking keeps every offset identical to the original, so a
    token span found in the masked text can be sliced out of the original.
    Handles: `--` line comments, nested `/* */` block comments, single-quoted
    strings ('' escape), and dollar-quoted strings ($tag$ ... $tag$ — where
    PL/pgSQL bodies with their own BEGIN/END live).
    """
    out = list(sql)
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""
        if ch == "-" and nxt == "-":
            j = sql.find("\n", i)
            j = n if j == -1 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif ch == "/" and nxt == "*":
            depth, j = 1, i + 2
            while j < n and depth:
                if sql[j] == "/" and j + 1 < n and sql[j + 1] == "*":
                    depth += 1
                    j += 2
                elif sql[j] == "*" and j + 1 < n and sql[j + 1] == "/":
                    depth -= 1
                    j += 2
                else:
                    j += 1
            for k in range(i, min(j, n)):
                out[k] = " "
            i = j
        elif ch == "'":
            j = i + 1
            while j < n:
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":  # escaped ''
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            for k in range(i, min(j, n)):
                out[k] = " "
            i = j
        elif ch == "$":
            m = re.match(r"\$([A-Za-z_][A-Za-z0-9_]*)?\$", sql[i:])
            if m:
                tag = m.group(0)
                j = sql.find(tag, i + len(tag))
                j = n if j == -1 else j + len(tag)
                for k in range(i, min(j, n)):
                    out[k] = " "
                i = j
            else:
                i += 1
        else:
            i += 1
    return "".join(out)


_TXN_TOKEN = re.compile(
    r"\b(?:BEGIN|COMMIT|ROLLBACK|SAVEPOINT|START\s+TRANSACTION|END\s+TRANSACTION)\b",
    re.IGNORECASE,
)
_OPEN_TOKEN = re.compile(r"^(?:BEGIN|START\s+TRANSACTION)$", re.IGNORECASE)


def unwrap_outer_transaction(sql: str) -> str:
    """Strip a single outer BEGIN;…COMMIT; wrapper; reject other txn control.

    Most migrations in this repo wrap themselves in BEGIN;/COMMIT;. The runner
    supplies its own transaction (so the ledger write is atomic with the
    migration), which means the file's wrapper must be removed — an inner
    COMMIT would silently end the runner's transaction and break atomicity.
    Any transaction control that is NOT exactly one leading BEGIN plus one
    trailing COMMIT (comments/strings excluded via masking) raises
    MigrationRejected: such a file needs restructuring, not guessing.
    """
    masked = _mask_sql_noise(sql)
    tokens = list(_TXN_TOKEN.finditer(masked))
    if not tokens:
        return sql

    first, last = tokens[0], tokens[-1]
    body_before = masked[:first.start()].strip()

    # Exactly one leading BEGIN and one COMMIT. Content is allowed AFTER the
    # COMMIT (e.g. 014 runs a post-commit DO block); it simply joins the
    # runner's transaction, which is safe for the DDL/DO patterns used here.
    ok_wrapper = (
        len(tokens) == 2
        and _OPEN_TOKEN.match(first.group(0))
        and last.group(0).upper() == "COMMIT"
        and body_before == ""
    )
    if not ok_wrapper:
        found = ", ".join(t.group(0).upper() for t in tokens)
        raise MigrationRejected(
            f"unsupported transaction control ({found}); only a single outer "
            "BEGIN;…COMMIT; wrapper is allowed — the runner manages the transaction"
        )

    # Slice the wrapper (and its trailing semicolons) out of the original.
    open_end = first.end()
    if open_end < len(sql) and sql[open_end:].lstrip().startswith(";"):
        open_end = sql.index(";", open_end) + 1
    close_start, close_end = last.start(), last.end()
    tail = sql[close_end:]
    stripped_tail = tail.lstrip()
    if stripped_tail.startswith(";"):
        close_end += len(tail) - len(stripped_tail) + 1
    return sql[:first.start()] + sql[open_end:close_start] + sql[close_end:]


def requires_non_transactional(sql: str) -> bool:
    """True for statements PostgreSQL refuses inside a transaction block."""
    return re.search(r"\bCONCURRENTLY\b", _mask_sql_noise(sql)) is not None


def split_statements(sql: str) -> list[str]:
    """Split SQL on top-level semicolons (comments/strings masked out).

    Used only for the non-transactional (CONCURRENTLY) path: a multi-statement
    string sent as one simple query runs in an implicit transaction, which
    PostgreSQL rejects for CONCURRENTLY — each statement must go separately.
    """
    masked = _mask_sql_noise(sql)
    statements, start = [], 0
    for i, ch in enumerate(masked):
        if ch == ";":
            stmt = sql[start:i].strip()
            if stmt:
                statements.append(stmt)
            start = i + 1
    tail = sql[start:].strip()
    if tail:
        statements.append(tail)
    return statements


# ── Database helpers ──────────────────────────────────────────────────

def _env(*names: str, default: str = "") -> str:
    """Return first env var from `names` that is *defined*, else `default`.

    Lets us accept both POSTGRES_* (this script's documented convention) and
    DB_* (historical prod .env convention). POSTGRES_* wins when both are set,
    even if explicitly empty — an operator who exports `POSTGRES_PASSWORD=''`
    has explicitly overridden the DB_* fallback (e.g. for password-less
    trust-auth setups in dev). Truthiness check (`if v:`) would incorrectly
    fall back through here. (Codex P2 review on #257.)
    """
    for n in names:
        v = os.getenv(n)
        if v is not None:
            return v
    return default


async def get_connection() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=_env("POSTGRES_HOST", "DB_HOST", default="localhost"),
        port=int(_env("POSTGRES_PORT", "DB_PORT", default="5432")),
        database=_env("POSTGRES_DATABASE", "DB_NAME", default="etlegacy"),
        user=_env("POSTGRES_USER", "DB_USER", default="etlegacy_user"),
        password=_env("POSTGRES_PASSWORD", "DB_PASSWORD", default=""),
    )


async def acquire_runner_lock(conn: asyncpg.Connection):
    """Take the session advisory lock or refuse to run.

    pg_try_advisory_lock (not the blocking variant): a second runner should
    fail fast with a clear message, not hang behind an unknown peer.
    """
    got = await conn.fetchval("SELECT pg_try_advisory_lock($1)", ADVISORY_LOCK_KEY)
    if not got:
        print("ERROR: another migration runner holds the advisory lock; aborting.")
        sys.exit(1)


async def ensure_tracking_table(conn: asyncpg.Connection):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id              SERIAL PRIMARY KEY,
            version         TEXT NOT NULL UNIQUE,
            filename        TEXT NOT NULL UNIQUE,
            checksum        TEXT,
            applied_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            applied_by      TEXT DEFAULT 'manual',
            execution_ms    INTEGER,
            success         BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)


async def get_applied(conn: asyncpg.Connection) -> set[str]:
    """Filenames recorded as successfully applied.

    Rows with success = FALSE are failure records, not applied migrations —
    counting them here made a once-failed migration permanently skipped
    (Codex audit finding 1).
    """
    rows = await conn.fetch(
        "SELECT filename FROM schema_migrations WHERE success = TRUE"
    )
    return {r["filename"] for r in rows}


async def get_failed(conn: asyncpg.Connection) -> set[str]:
    """Filenames whose last recorded attempt failed."""
    rows = await conn.fetch(
        "SELECT filename FROM schema_migrations WHERE success = FALSE"
    )
    return {r["filename"] for r in rows}


async def get_checksum_mismatches(conn: asyncpg.Connection) -> list[str]:
    """Applied files whose on-disk content no longer matches the ledger.

    A recorded checksum of NULL (pre-checksum rows) is treated as unknown and
    skipped — only a positive mismatch is drift.
    """
    recorded = {
        r["filename"]: r["checksum"]
        for r in await conn.fetch(
            "SELECT filename, checksum FROM schema_migrations WHERE success = TRUE"
        )
    }
    mismatches = []
    for filename, path in discover_migrations():
        rec = recorded.get(filename)
        if rec and rec != _file_checksum(path):
            mismatches.append(filename)
    return mismatches


def discover_migrations() -> list[tuple[str, Path]]:
    """Return sorted list of (filename, path) for all .sql migration files."""
    files = sorted(
        [f.name for f in MIGRATIONS_DIR.glob("*.sql")],
        key=_sort_key,
    )
    return [(f, MIGRATIONS_DIR / f) for f in files]


async def collect_state(conn: asyncpg.Connection) -> dict:
    """Shared status snapshot for --status/--validate."""
    applied = await get_applied(conn)
    failed = await get_failed(conn)
    migrations = discover_migrations()
    discovered = {f for f, _ in migrations}
    # A FAILED file is not also PENDING — counting it in both let Pending+Failed
    # exceed total_files and listed the same file twice (Copilot review on #509).
    pending = [f for f, _ in migrations if f not in applied and f not in failed]
    # Rows recorded in the ledger (applied OR failed) whose SQL file is gone from
    # the checkout (deleted or renamed): fresh installs and drift audits would
    # silently diverge because the version lives in the DB but not in the repo.
    # Include FAILED rows too — an orphaned failed row is drift the targeted-apply
    # preflight must also catch (Copilot/Codex review on #509).
    missing = sorted((applied | failed) - discovered)
    mismatches = await get_checksum_mismatches(conn)
    return {
        "total_files": len(migrations),
        "applied": sorted(applied),
        "failed": sorted(failed),
        "pending": pending,
        "missing": missing,
        "checksum_mismatches": mismatches,
    }


# ── Commands ──────────────────────────────────────────────────────────

async def cmd_status(json_out: bool = False):
    """Show which migrations are applied vs pending."""
    conn = await get_connection()
    try:
        await ensure_tracking_table(conn)
        state = await collect_state(conn)
        if json_out:
            print(json.dumps(state, indent=2))
            return

        applied = set(state["applied"])
        failed = set(state["failed"])
        print(f"\nMigrations directory: {MIGRATIONS_DIR}")
        print(f"Total files: {state['total_files']}\n")

        for filename, _path in discover_migrations():
            if filename in applied:
                status, marker = "APPLIED", "  "
            elif filename in failed:
                status, marker = "FAILED", "!!"
            else:
                status, marker = "PENDING", ">>"
            drift = "  (CHECKSUM MISMATCH)" if filename in state["checksum_mismatches"] else ""
            print(f"  {marker} [{status:7s}] {filename}{drift}")

        for filename in state["missing"]:
            print(f"  ?? [MISSING] {filename}  (recorded applied, no file on disk)")

        print(f"\n  Applied: {len(applied)}, Failed: {len(failed)}, "
              f"Pending: {len(state['pending'])}, "
              f"Missing: {len(state['missing'])}, "
              f"Checksum mismatches: {len(state['checksum_mismatches'])}")
        if state["missing"]:
            print("  MISSING migrations are recorded in the ledger but absent from "
                  "migrations/ — restore the file or reconcile the ledger.")
        if failed:
            print("  FAILED migrations retry on next apply; if they were fixed "
                  "manually via psql, reconcile with --mark.")
        print()
    finally:
        await conn.close()


async def cmd_validate(json_out: bool = False):
    """Exit non-zero when the ledger and the migrations directory disagree.

    Deploy integration point: deploy_release.sh runs this after applying a
    release's migrations and aborts the deploy on any drift (pending, failed,
    or checksum mismatch).
    """
    conn = await get_connection()
    try:
        await ensure_tracking_table(conn)
        # Take the runner lock so validation can't observe a half-written ledger
        # while another session is mid-apply (uncommitted rows / transient drift).
        # Fail-fast keeps deploy gating deterministic (Copilot review on #509).
        await acquire_runner_lock(conn)
        state = await collect_state(conn)
    finally:
        await conn.close()

    clean = (
        not state["pending"]
        and not state["failed"]
        and not state["missing"]
        and not state["checksum_mismatches"]
    )
    state["clean"] = clean
    if json_out:
        print(json.dumps(state, indent=2))
    else:
        print(f"  Applied: {len(state['applied'])}, Failed: {len(state['failed'])}, "
              f"Pending: {len(state['pending'])}, "
              f"Missing: {len(state['missing'])}, "
              f"Checksum mismatches: {len(state['checksum_mismatches'])}")
        for f in state["pending"]:
            print(f"    >> PENDING  {f}")
        for f in state["failed"]:
            print(f"    !! FAILED   {f}")
        for f in state["missing"]:
            print(f"    ?? MISSING  {f}")
        for f in state["checksum_mismatches"]:
            print(f"    ~~ CHECKSUM {f}")
        print(f"  Validation: {'CLEAN' if clean else 'DRIFT DETECTED'}")
    if not clean:
        sys.exit(1)


async def cmd_baseline():
    """Mark all existing migrations as already applied (baseline)."""
    conn = await get_connection()
    try:
        await ensure_tracking_table(conn)
        applied = await get_applied(conn)
        failed = await get_failed(conn)
        migrations = discover_migrations()

        count = 0
        for filename, path in migrations:
            if filename in failed:
                # ON CONFLICT DO NOTHING below would silently leave the row at
                # success=FALSE — reconciling a failure record needs --mark.
                print(f"  [SKIP-FAILED] {filename} (has a failure record; "
                      "reconcile with --mark after verifying)")
                continue
            if filename not in applied:
                version = _version_from_filename(filename)
                checksum = _file_checksum(path)
                await conn.execute(
                    """INSERT INTO schema_migrations (version, filename, checksum, applied_by)
                       VALUES ($1, $2, $3, 'baseline')
                       ON CONFLICT (filename) DO NOTHING""",
                    version, filename, checksum,
                )
                count += 1
                print(f"  [BASELINE] {filename}")

        if count == 0:
            print("  All migrations already recorded.")
        else:
            print(f"\n  Recorded {count} migration(s) as baseline.\n")
    finally:
        await conn.close()


async def _record_failure(conn, version, filename, checksum, elapsed_ms):
    """Write the failure row in its own (new) transaction.

    Called after the migration transaction rolled back, so the connection is
    out of aborted-transaction state and this insert can succeed.
    """
    await conn.execute(
        """INSERT INTO schema_migrations
           (version, filename, checksum, applied_by, execution_ms, success)
           VALUES ($1, $2, $3, 'cli', $4, FALSE)
           ON CONFLICT (filename) DO UPDATE
           SET success = FALSE, checksum = EXCLUDED.checksum,
               applied_by = 'cli', execution_ms = EXCLUDED.execution_ms,
               applied_at = NOW()""",
        version, filename, checksum, elapsed_ms,
    )


_SUCCESS_UPSERT = """INSERT INTO schema_migrations
   (version, filename, checksum, applied_by, execution_ms, success)
   VALUES ($1, $2, $3, 'cli', $4, TRUE)
   ON CONFLICT (filename) DO UPDATE
   SET success = TRUE, checksum = EXCLUDED.checksum,
       applied_by = 'cli', execution_ms = EXCLUDED.execution_ms,
       applied_at = NOW()"""


async def cmd_apply(only: list[str] | None = None):
    """Apply pending migrations in order.

    Each migration's SQL and its ledger success row commit in the SAME
    transaction; on error the transaction rolls back, the failure row is
    recorded in a new transaction, and the process exits non-zero (the old
    behavior returned normally, so deploy scripts saw exit 0 on failure —
    Codex audit AUD-002).
    """
    conn = await get_connection()
    try:
        await ensure_tracking_table(conn)
        await acquire_runner_lock(conn)
        applied = await get_applied(conn)
        failed = await get_failed(conn)
        migrations = discover_migrations()

        # Populated DB with an empty tracking table: refuse instead of silently
        # baselining — an existing DB with schema drift would be marked fully
        # migrated without any validation (Codex audit finding 2). The operator
        # must run --baseline explicitly.
        if not applied and not failed:
            has_tables = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'player_comprehensive_stats')"
            )
            if has_tables:
                print("  Populated database detected with empty tracking table.")
                print("  Refusing to apply: this DB predates migration tracking, so")
                print("  pending migrations may already be (partially) applied.")
                print("  Verify the schema, then run:  apply_migrations.py --baseline\n")
                sys.exit(1)

        mismatches = await get_checksum_mismatches(conn)
        if mismatches:
            print("  ERROR: applied migration file(s) changed on disk since they")
            print("  were recorded (checksum mismatch). Refusing to apply anything")
            print("  until the drift is resolved:")
            for f in mismatches:
                print(f"    ~~ {f}")
            sys.exit(1)

        pending = [(f, p) for f, p in migrations if f not in applied]

        if only:
            known = {f for f, _ in migrations}
            unknown = [f for f in only if f not in known]
            if unknown:
                print(f"  ERROR: --only file(s) not found under {MIGRATIONS_DIR}:")
                for f in unknown:
                    print(f"    {f}")
                sys.exit(1)
            wanted = set(only)
            # Refuse a targeted apply while UNRELATED ledger drift exists: any
            # migration outside `only` that is un-applied (pending or previously
            # failed) or recorded-applied-but-missing from disk. Otherwise a
            # release deploy advances the DB for its new files and records their
            # success even though reconciliation (e.g. 052-060) is still
            # outstanding — the deploy's own post-apply --validate runs too late
            # to prevent that write (Codex review on #509). Checksum mismatches
            # are already refused globally above.
            unrelated = sorted(
                f for f, _ in migrations if f not in applied and f not in wanted
            )
            # Include FAILED rows whose file is gone: an orphaned failed-and-
            # deleted migration is drift the preflight must catch too, not just
            # applied-and-deleted rows (Codex review on #509).
            missing = sorted((applied | failed) - known)
            if unrelated or missing:
                print("  ERROR: --only refuses to run while unrelated ledger drift exists.")
                print("  Reconcile these before deploying the targeted set:")
                for f in unrelated:
                    print(f"    {'FAILED ' if f in failed else 'PENDING'}: {f}")
                for f in missing:
                    print(f"    MISSING: {f}")
                sys.exit(1)
            already = [f for f in only if f in applied]
            for f in already:
                print(f"  [SKIP] {f} (already applied)")
            pending = [(f, p) for f, p in pending if f in wanted]

        if failed:
            retrying = [f for f, _ in pending if f in failed]
            if retrying:
                print(f"  NOTE: {len(retrying)} previously FAILED migration(s) will be retried:")
                for f in sorted(retrying):
                    print(f"    !! {f}")
                print()

        if not pending:
            print("  No pending migrations.\n")
            return

        print(f"  Applying {len(pending)} migration(s)...\n")

        for filename, path in pending:
            version = _version_from_filename(filename)
            checksum = _file_checksum(path)
            sql = path.read_text(encoding="utf-8")

            print(f"  Applying: {filename} ... ", end="", flush=True)
            start = time.monotonic()
            try:
                body = unwrap_outer_transaction(sql)
            except MigrationRejected as e:
                print("REJECTED")
                print(f"    Error: {e}")
                sys.exit(1)

            try:
                if requires_non_transactional(body):
                    # CREATE INDEX CONCURRENTLY etc. refuse to run inside a
                    # transaction block; apply statement-by-statement (each
                    # autocommits) and record success separately. Not atomic —
                    # a mid-file failure leaves earlier statements applied,
                    # which the failure row + non-zero exit make visible.
                    print("(non-transactional: CONCURRENTLY) ... ", end="", flush=True)
                    for stmt in split_statements(body):
                        await conn.execute(stmt)
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    await conn.execute(_SUCCESS_UPSERT, version, filename, checksum, elapsed_ms)
                else:
                    async with conn.transaction():
                        await conn.execute(body)
                        elapsed_ms = int((time.monotonic() - start) * 1000)
                        await conn.execute(_SUCCESS_UPSERT, version, filename, checksum, elapsed_ms)
                print(f"OK ({elapsed_ms}ms)")
            except Exception as e:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                await _record_failure(conn, version, filename, checksum, elapsed_ms)
                print(f"FAILED ({elapsed_ms}ms)")
                print(f"    Error: {e}")
                print("  Stopping at first failure.\n")
                sys.exit(1)

        print(f"\n  All {len(pending)} migration(s) applied successfully.\n")
    finally:
        await conn.close()


async def cmd_mark(filenames: list[str]):
    """Record specific migration files as applied without running their SQL.

    Use after manually applying a migration via raw `psql` (e.g. during an
    emergency deploy) so the tracking table stays in sync. Refuses any
    filename that doesn't exist under `migrations/`.
    """
    if not filenames:
        print("ERROR: --mark requires at least one filename. "
              "Example: --mark 052_add_weapon_stats_mv.sql")
        sys.exit(1)

    discovered = {f: p for f, p in discover_migrations()}
    missing = [f for f in filenames if f not in discovered]
    if missing:
        print(f"ERROR: file(s) not found under {MIGRATIONS_DIR}:")
        for f in missing:
            print(f"    {f}")
        sys.exit(1)

    conn = await get_connection()
    try:
        await ensure_tracking_table(conn)
        # Fetch (filename, success) so we can distinguish already-marked-OK
        # rows from previously-failed rows that should now be reconciled.
        # (Copilot review on #257.)
        existing: dict[str, bool] = {
            r["filename"]: r["success"]
            for r in await conn.fetch(
                "SELECT filename, success FROM schema_migrations"
            )
        }

        marked = 0
        skipped = 0
        repaired = 0
        raced = 0
        for filename in filenames:
            path = discovered[filename]
            version = _version_from_filename(filename)
            checksum = _file_checksum(path)

            prior = existing.get(filename)
            if prior is True:
                print(f"  [SKIP   ] {filename} (already recorded success=TRUE)")
                skipped += 1
                continue

            if prior is False:
                # Reconcile a previously-failed row: a manual psql apply
                # succeeded, so flip success to TRUE and record the manual
                # provenance + fresh checksum.
                row = await conn.fetchrow(
                    """UPDATE schema_migrations
                       SET success = TRUE,
                           applied_by = 'manual-mark',
                           checksum = $2,
                           applied_at = NOW()
                       WHERE filename = $1
                       RETURNING id""",
                    filename, checksum,
                )
                if row is None:
                    # Row vanished between SELECT and UPDATE — exotic, but report it.
                    print(f"  [RACED  ] {filename} (row disappeared during reconcile)")
                    raced += 1
                else:
                    print(f"  [REPAIR ] {filename} (success FALSE→TRUE)")
                    repaired += 1
                continue

            # No existing row → insert. Use RETURNING to verify a real insert
            # happened (vs a concurrent insert hitting the UNIQUE constraint).
            row = await conn.fetchrow(
                """INSERT INTO schema_migrations
                   (version, filename, checksum, applied_by, success)
                   VALUES ($1, $2, $3, 'manual-mark', TRUE)
                   ON CONFLICT (filename) DO NOTHING
                   RETURNING id""",
                version, filename, checksum,
            )
            if row is None:
                # Lost the race against a concurrent writer.
                print(f"  [RACED  ] {filename} (concurrent insert won; row already exists)")
                raced += 1
            else:
                print(f"  [MARKED ] {filename}")
                marked += 1

        print(
            f"\n  Marked: {marked}, Repaired: {repaired}, "
            f"Skipped: {skipped}, Raced: {raced}\n"
        )
    finally:
        await conn.close()


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Slomix migration runner (see module docstring)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true",
                       help="show applied/failed/pending state")
    group.add_argument("--validate", action="store_true",
                       help="exit 1 on pending/failed/checksum drift")
    group.add_argument("--baseline", action="store_true",
                       help="mark all migrations as pre-applied")
    group.add_argument("--mark", nargs="+", metavar="FILE",
                       help="record files as applied without running them")
    group.add_argument("--only", nargs="+", metavar="FILE",
                       help="apply only the named pending files")
    parser.add_argument("--json", action="store_true",
                        help="JSON output (with --status/--validate)")
    args = parser.parse_args()

    if args.json and not (args.status or args.validate):
        parser.error("--json requires --status or --validate")

    if args.status:
        asyncio.run(cmd_status(json_out=args.json))
    elif args.validate:
        asyncio.run(cmd_validate(json_out=args.json))
    elif args.baseline:
        asyncio.run(cmd_baseline())
    elif args.mark:
        # Strip leading paths if the user pasted them.
        asyncio.run(cmd_mark([Path(a).name for a in args.mark]))
    elif args.only:
        asyncio.run(cmd_apply(only=[Path(a).name for a in args.only]))
    else:
        asyncio.run(cmd_apply())


if __name__ == "__main__":
    main()
