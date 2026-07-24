"""Startup migration-drift guard.

Prevention for the 2026-07-24 schema drift (memory: schema_migration_drift):
`schema_migrations` had frozen ~May 2026 while migrations/ kept growing, and a
`git-checkout origin/main` deploy applies NO migrations (it bypasses
deploy_release.sh's per-release MIGRATIONS list). The gap only surfaced as an
`UndefinedColumnError: column "publish_state" does not exist` 500 when a request
finally hit the missing column.

This guard reads schema_migrations vs migrations/*.sql at startup and logs a
LOUD warning if the DB is drifted — so it shows up in
`journalctl -u ... | grep -iE "warn|error"` the moment a service (re)starts,
instead of as a runtime 500 hours later.

Drift the guard reports (each also refuses/flags in scripts/apply_migrations.py):
- pending           — a migration file not recorded success=TRUE (never applied
                      OR its last attempt failed; Codex #545).
- checksum mismatch — an applied migration whose file was edited afterwards
                      (apply_migrations refuses to run in this state; Codex #545).
- no files found    — migrations/ is empty (e.g. the Docker API image strips
                      *.sql); the guard can't verify, so it says so rather than
                      falsely reporting "up to date" (Codex #545).

Scope: this guard covers the ROOT `migrations/` set (the shared schema_migrations
ledger). The separate `website/migrations/` set has no tracking table in the DB,
so it can't be filename-checked here without false positives — covering it needs
its own ledger first (follow-up).

Design: READ-ONLY and NON-FATAL. A check failure (fresh DB, permissions, no
schema_migrations) never blocks boot — it warns instead.
"""
from __future__ import annotations

import hashlib
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


def _discover_paths() -> dict[str, Path]:
    try:
        return {p.name: p for p in _MIGRATIONS_DIR.glob("*.sql")}
    except OSError:
        return {}


def _file_checksum(path: Path) -> str:
    """SHA-256 hex digest — same algorithm as apply_migrations._file_checksum."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def get_migration_drift(db) -> dict:
    """Return {'discovered': int, 'pending': [...], 'checksum_mismatch': [...]}.

    `db` is any adapter exposing async ``fetch_all(query, params)``.
    - pending: discovered files not recorded ``success = TRUE`` (a ``success =
      FALSE`` / failed row is NOT applied and stays pending — Codex #545).
    - checksum_mismatch: applied files whose on-disk SHA-256 differs from the
      recorded checksum (a migration edited after being applied). NULL recorded
      checksums are skipped (unknown), matching apply_migrations.
    """
    paths = _discover_paths()
    result: dict = {"discovered": len(paths), "pending": [], "checksum_mismatch": []}
    if not paths:
        return result
    names = sorted(paths, key=_sort_key)
    rows = await db.fetch_all(
        "SELECT filename, checksum FROM schema_migrations WHERE success = TRUE", ()
    )
    applied = {r[0]: r[1] for r in (rows or [])}
    for name in names:
        if name not in applied:
            result["pending"].append(name)
            continue
        stored = applied[name]
        if stored:  # only a recorded (non-NULL) checksum can mismatch
            try:
                if _file_checksum(paths[name]) != stored:
                    result["checksum_mismatch"].append(name)
            except OSError:
                # Unreadable migration file → can't hash it, so skip the
                # checksum compare for this one (non-fatal; a genuinely missing
                # file is already covered by discovery). CodeQL empty-except.
                continue
    return result


async def get_pending_migrations(db) -> list[str]:
    """Migration files present on disk but not recorded as SUCCESSFULLY applied.

    Thin wrapper over get_migration_drift for callers that only want the pending
    list (kept for backwards-compatible use / tests).
    """
    return (await get_migration_drift(db))["pending"]


async def warn_if_pending_migrations(db, logger: logging.Logger, component: str) -> list[str]:
    """Log loudly on migration drift. Never raises. Returns the pending list
    (empty when up to date or when the check could not run)."""
    try:
        drift = await get_migration_drift(db)
    except Exception as exc:  # noqa: BLE001 - a guard must never break startup
        # WARNING, not DEBUG (Copilot/Codex #545): a guard that fails silently
        # defeats its own purpose. Still non-fatal — startup continues.
        logger.warning(
            "⚠️ migration-drift check could NOT run [%s]: %s — schema drift "
            "would go unnoticed; verify `python scripts/apply_migrations.py --status`.",
            component, exc,
        )
        return []

    if drift["discovered"] == 0:
        # e.g. the Docker API image strips *.sql — an empty on-disk set must not
        # read as "fully applied" (Codex #545).
        logger.warning(
            "⚠️ no migration files discoverable [%s] — cannot verify DB drift "
            "(is migrations/ present in this build?).",
            component,
        )
        return []

    pending = drift["pending"]
    mismatch = drift["checksum_mismatch"]
    if pending or mismatch:
        logger.error(
            "⚠️ DB MIGRATION DRIFT [%s] — run `python scripts/apply_migrations.py "
            "--validate`: %d pending%s%s%s. Drift causes UndefinedColumn 500s at "
            "request time.",
            component,
            len(pending),
            f" ({', '.join(pending)})" if pending else "",
            f"; {len(mismatch)} checksum-mismatch" if mismatch else "",
            f" ({', '.join(mismatch)})" if mismatch else "",
        )
    else:
        logger.info("✅ DB migrations up to date [%s]", component)
    return pending
