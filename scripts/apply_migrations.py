#!/usr/bin/env python3
"""
Database migration runner for Slomix ET:Legacy Bot.

Tracks applied migrations in a `schema_migrations` table and applies
any pending .sql files from the migrations/ directory.

Usage:
    python scripts/apply_migrations.py                # Apply pending migrations
    python scripts/apply_migrations.py --status       # Show migration status
    python scripts/apply_migrations.py --baseline     # Mark all as pre-applied

Environment variables (or .env file):
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DATABASE,
    POSTGRES_USER, POSTGRES_PASSWORD
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

async def get_connection() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DATABASE", "etlegacy"),
        user=os.getenv("POSTGRES_USER", "etlegacy_user"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
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
    rows = await conn.fetch("SELECT filename FROM schema_migrations")
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
        migrations = discover_migrations()

        print(f"\nMigrations directory: {MIGRATIONS_DIR}")
        print(f"Total files: {len(migrations)}\n")

        pending = 0
        for filename, path in migrations:
            status = "APPLIED" if filename in applied else "PENDING"
            if status == "PENDING":
                pending += 1
            marker = "  " if filename in applied else ">>"
            print(f"  {marker} [{status:7s}] {filename}")

        print(f"\n  Applied: {len(applied)}, Pending: {pending}\n")
    finally:
        await conn.close()


async def cmd_baseline():
    """Mark all existing migrations as already applied (baseline)."""
    conn = await get_connection()
    try:
        await ensure_tracking_table(conn)
        applied = await get_applied(conn)
        migrations = discover_migrations()

        count = 0
        for filename, path in migrations:
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
        migrations = discover_migrations()

        # Auto-baseline: if tracking table is empty but DB has real tables,
        # all existing migrations are pre-applied.
        if not applied:
            has_tables = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'player_comprehensive_stats')"
            )
            if has_tables:
                print("  Populated database detected with empty tracking table.")
                print("  Running auto-baseline for all existing migrations...\n")
                await cmd_baseline_inner(conn, migrations)
                applied = await get_applied(conn)

        pending = [(f, p) for f, p in migrations if f not in applied]

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
                await conn.execute(
                    """INSERT INTO schema_migrations
                       (version, filename, checksum, applied_by, execution_ms, success)
                       VALUES ($1, $2, $3, 'cli', $4, TRUE)
                       ON CONFLICT (filename) DO NOTHING""",
                    version, filename, checksum, elapsed_ms,
                )
                print(f"OK ({elapsed_ms}ms)")
            except Exception as e:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                await conn.execute(
                    """INSERT INTO schema_migrations
                       (version, filename, checksum, applied_by, execution_ms, success)
                       VALUES ($1, $2, $3, 'cli', $4, FALSE)
                       ON CONFLICT (filename) DO NOTHING""",
                    version, filename, checksum, elapsed_ms,
                )
                print(f"FAILED ({elapsed_ms}ms)")
                print(f"    Error: {e}")
                print("  Stopping at first failure.\n")
                return

        print(f"\n  All {len(pending)} migration(s) applied successfully.\n")
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
    else:
        asyncio.run(cmd_apply())


if __name__ == "__main__":
    main()
