#!/usr/bin/env python3
"""
Database migration runner for Slomix ET:Legacy Bot.

Tracks applied migrations in a `schema_migrations` table and applies
any pending .sql files from the migrations/ directory.

Usage:
    python scripts/apply_migrations.py                       # Apply pending migrations
    python scripts/apply_migrations.py --status              # Show migration status
    python scripts/apply_migrations.py --baseline            # Mark all as pre-applied
    python scripts/apply_migrations.py --mark FILE [FILE..]  # Record specific files as applied without running them

Environment variables (or .env file):
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DATABASE,
    POSTGRES_USER, POSTGRES_PASSWORD

    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD are accepted as
    fallbacks — production .env files in this repo historically used
    DB_* names. POSTGRES_* takes precedence when both are present.
"""

import asyncio
import hashlib
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


def discover_migrations() -> list[tuple[str, Path]]:
    """Return sorted list of (filename, path) for all .sql migration files."""
    files = sorted(
        [f.name for f in MIGRATIONS_DIR.glob("*.sql")],
        key=_sort_key,
    )
    return [(f, MIGRATIONS_DIR / f) for f in files]


# ── Commands ──────────────────────────────────────────────────────────

async def cmd_status():
    """Show which migrations are applied vs pending."""
    conn = await get_connection()
    try:
        await ensure_tracking_table(conn)
        applied = await get_applied(conn)
        failed = await get_failed(conn)
        migrations = discover_migrations()

        print(f"\nMigrations directory: {MIGRATIONS_DIR}")
        print(f"Total files: {len(migrations)}\n")

        pending = 0
        for filename, path in migrations:
            if filename in applied:
                status, marker = "APPLIED", "  "
            elif filename in failed:
                status, marker = "FAILED", "!!"
                pending += 1
            else:
                status, marker = "PENDING", ">>"
                pending += 1
            print(f"  {marker} [{status:7s}] {filename}")

        print(f"\n  Applied: {len(applied)}, Failed: {len(failed)}, Pending: {pending}")
        if failed:
            print("  FAILED migrations retry on next apply; if they were fixed "
                  "manually via psql, reconcile with --mark.")
        print()
    finally:
        await conn.close()


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


async def cmd_apply():
    """Apply pending migrations in order."""
    conn = await get_connection()
    try:
        await ensure_tracking_table(conn)
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

        pending = [(f, p) for f, p in migrations if f not in applied]
        if failed:
            print(f"  NOTE: {len(failed)} previously FAILED migration(s) will be retried:")
            for f in sorted(failed):
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
                await conn.execute(sql)
                elapsed_ms = int((time.monotonic() - start) * 1000)
                # DO UPDATE, not DO NOTHING: a retried migration conflicts with
                # its own earlier success=FALSE row, and the outcome must
                # overwrite it or the retry's success is never recorded.
                await conn.execute(
                    """INSERT INTO schema_migrations
                       (version, filename, checksum, applied_by, execution_ms, success)
                       VALUES ($1, $2, $3, 'cli', $4, TRUE)
                       ON CONFLICT (filename) DO UPDATE
                       SET success = TRUE, checksum = EXCLUDED.checksum,
                           applied_by = 'cli', execution_ms = EXCLUDED.execution_ms,
                           applied_at = NOW()""",
                    version, filename, checksum, elapsed_ms,
                )
                print(f"OK ({elapsed_ms}ms)")
            except Exception as e:
                elapsed_ms = int((time.monotonic() - start) * 1000)
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
                print(f"FAILED ({elapsed_ms}ms)")
                print(f"    Error: {e}")
                print("  Stopping at first failure.\n")
                return

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


async def cmd_baseline_inner(conn: asyncpg.Connection, migrations: list):
    """Baseline helper (uses existing connection)."""
    for filename, path in migrations:
        version = _version_from_filename(filename)
        checksum = _file_checksum(path)
        await conn.execute(
            """INSERT INTO schema_migrations (version, filename, checksum, applied_by)
               VALUES ($1, $2, $3, 'baseline')
               ON CONFLICT (filename) DO NOTHING""",
            version, filename, checksum,
        )
        print(f"    [BASELINE] {filename}")


# ── Main ──────────────────────────────────────────────────────────────

def main():
    if "--status" in sys.argv:
        asyncio.run(cmd_status())
    elif "--baseline" in sys.argv:
        asyncio.run(cmd_baseline())
    elif "--mark" in sys.argv:
        idx = sys.argv.index("--mark")
        # Everything after --mark, stripped of leading paths if user pasted them
        filenames = [Path(a).name for a in sys.argv[idx + 1:] if not a.startswith("-")]
        asyncio.run(cmd_mark(filenames))
    else:
        asyncio.run(cmd_apply())


if __name__ == "__main__":
    main()
