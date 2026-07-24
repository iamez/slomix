"""Startup migration-drift guard.

Prevention for the 2026-07-24 schema drift (memory: schema_migration_drift):
`schema_migrations` had frozen ~May 2026 while migrations/ kept growing, and a
`git-checkout origin/main` deploy applies NO migrations (it bypasses
deploy_release.sh's per-release MIGRATIONS list). The gap only surfaced as an
`UndefinedColumnError: column "publish_state" does not exist` 500 when a request
finally hit the missing column.

This guard reads schema_migrations vs migrations/*.sql at startup and logs a
LOUD warning if any migration is unapplied — so drift shows up in
`journalctl -u ... | grep -iE "warn|error"` the moment a service (re)starts,
instead of as a runtime 500 hours later.

Design:
- READ-ONLY and NON-FATAL: a check failure (e.g. no schema_migrations table on
  a fresh DB) must never block boot. It only warns.
- "Pending" matches scripts/apply_migrations.py semantics: a file on disk that
  is NOT recorded success=TRUE and NOT recorded success=FALSE (failed rows are
  a separate, already-known problem, not silent drift).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

# repo/shared/migration_status.py -> repo/migrations
_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _sort_key(filename: str) -> tuple:
    """Numeric-prefixed migrations (005…063) sort ahead of legacy-named ones
    (add_*.sql), each in natural order — matches apply_migrations.discover."""
    m = re.match(r"^(\d+)", filename)
    return (0, int(m.group(1)), filename) if m else (1, 0, filename)


def _discover() -> list[str]:
    try:
        return sorted((p.name for p in _MIGRATIONS_DIR.glob("*.sql")), key=_sort_key)
    except OSError:
        return []


async def get_pending_migrations(db) -> list[str]:
    """Migration files present on disk but not recorded as applied/failed.

    `db` is any adapter exposing async ``fetch_all(query, params)``. Failed rows
    are excluded (they are a distinct, surfaced problem, not silent drift).
    """
    files = _discover()
    if not files:
        return []
    rows = await db.fetch_all("SELECT filename FROM schema_migrations", ())
    seen = {r[0] for r in (rows or [])}
    return [f for f in files if f not in seen]


async def warn_if_pending_migrations(db, logger: logging.Logger, component: str) -> list[str]:
    """Log loudly if migrations are unapplied. Never raises. Returns the pending
    list (empty when up to date or when the check could not run)."""
    try:
        pending = await get_pending_migrations(db)
    except Exception as exc:  # noqa: BLE001 - a guard must never break startup
        logger.debug("migration-status check skipped (%s): %s", component, exc)
        return []
    if pending:
        logger.error(
            "⚠️ %d PENDING DB MIGRATION(S) [%s] — schema drift, run "
            "`python scripts/apply_migrations.py --status`: %s. Unapplied "
            "migrations cause UndefinedColumn 500s at request time.",
            len(pending), component, ", ".join(pending),
        )
    else:
        logger.info("✅ DB migrations up to date [%s]", component)
    return pending
