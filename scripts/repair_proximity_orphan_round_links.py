#!/usr/bin/env python3
"""repair_proximity_orphan_round_links.py — link orphaned combat_engagement /
player_track rows to the round they provably belong to.

Unlike proximity_shot_fired (which has its own relinker and whose orphans are
almost all stranded on rounds whose stats file never landed), combat_engagement
and player_track have NO relinker, so ~5k rows sit at round_id IS NULL even
though their own four identity columns — session_date, map_name, round_number,
round_start_unix — name exactly one existing round. round_start_unix makes the
match deterministic: it is the engine's own round clock, so a 4-column hit that
resolves to exactly ONE row in `rounds` is that round with no guessing.

Only NULL round_id is ever written, and only when the identity resolves to a
single round (the `= 1` guard skips the identity-drift cases the shot_fired
relinker also refuses). This is a copy of a known-correct fact, never a
re-derivation.

Follows scripts/repair_shot_fired_round_links.py: dry-run by default, --apply to
write, and the historical mutation lives here rather than in a migration so a
normal deploy cannot perform it unattended.

Usage:
    # 1. preview, and note the repairable row count it reports
    python scripts/repair_proximity_orphan_round_links.py

    # 2. write, restating that count and the exact server the preview ran on
    python scripts/repair_proximity_orphan_round_links.py --apply \
        --expect-repairable-rows 4964 \
        --expect-db localhost:5432/etlegacy
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.apply_migrations import (  # noqa: E402
    get_connection_kwargs,
    get_target_dsn_parts,
)

try:
    import psycopg2 as _pg
except ImportError:  # pragma: no cover
    try:
        import psycopg as _pg  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover
        _pg = None  # type: ignore[assignment]

# Tables with orphan rows carrying the four identity columns but no relinker.
_TABLES = ("combat_engagement", "player_track")

# Rows relinkable now: NULL round_id whose identity resolves to exactly one
# round. The scalar sub-select is the deterministic guard.
_PREVIEW_SQL = """
    SELECT COUNT(*) AS rows,
           COUNT(DISTINCT (t.session_date, t.map_name, t.round_number, t.round_start_unix)) AS identities
    FROM {table} t
    WHERE t.round_id IS NULL
      AND (
        SELECT COUNT(*) FROM rounds r
        WHERE r.round_date = t.session_date::text
          AND r.map_name = t.map_name
          AND r.round_number = t.round_number
          AND r.round_start_unix = t.round_start_unix
      ) = 1
"""

# Same predicate, as an UPDATE ... FROM. The `= 1` guard is repeated so a second
# round sharing the identity (should never happen — round_start_unix is unique
# per round) can never turn one orphan into an ambiguous write.
_APPLY_SQL = """
    UPDATE {table} t
    SET round_id = r.id
    FROM rounds r
    WHERE t.round_id IS NULL
      AND r.round_date = t.session_date::text
      AND r.map_name = t.map_name
      AND r.round_number = t.round_number
      AND r.round_start_unix = t.round_start_unix
      AND (
        SELECT COUNT(*) FROM rounds r2
        WHERE r2.round_date = t.session_date::text
          AND r2.map_name = t.map_name
          AND r2.round_number = t.round_number
          AND r2.round_start_unix = t.round_start_unix
      ) = 1
"""


def _connect():
    if _pg is None:
        raise SystemExit("psycopg2/psycopg not installed")
    connection_kwargs = get_connection_kwargs()
    connection_kwargs["dbname"] = connection_kwargs.pop("database")
    return _pg.connect(**connection_kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    parser.add_argument(
        "--expect-repairable-rows",
        type=int,
        help="total row count the dry run reported; REQUIRED with --apply",
    )
    parser.add_argument(
        "--expect-db",
        help="server this must run against as host:port/database; REQUIRED with --apply",
    )
    args = parser.parse_args()

    if args.apply and (args.expect_repairable_rows is None or not args.expect_db):
        parser.error(
            "--apply requires --expect-repairable-rows and --expect-db "
            "(run without --apply first and pass back what it reports)"
        )

    target = get_target_dsn_parts()
    identity = f"{target['host']}:{target['port']}/{target['database']}"
    print(f"Target: {identity}")
    if args.expect_db and args.expect_db != identity:
        print(f"ABORT: --expect-db={args.expect_db!r} but target is {identity!r}")
        return 1

    total = 0
    with _connect() as conn, conn.cursor() as cur:
        for table in _TABLES:
            cur.execute(_PREVIEW_SQL.format(table=table))
            rows, identities = cur.fetchone()
            total += rows
            print(f"  {table:<20} {rows:>6,} rows  ({identities} round identities)")
    print(f"\nDeterministically relinkable: {total:,} rows")

    if not args.apply:
        print("\nDry run — nothing written. Re-run with --apply to write.")
        return 0

    if args.expect_repairable_rows != total:
        print(
            f"ABORT: --expect-repairable-rows={args.expect_repairable_rows} but "
            f"the current candidate set is {total} (it shifted since the preview)."
        )
        return 1

    written = 0
    with _connect() as conn, conn.cursor() as cur:
        for table in _TABLES:
            cur.execute(_APPLY_SQL.format(table=table))
            n = cur.rowcount
            written += n
            print(f"  {table:<20} linked {n:,} rows")
        # The UPDATE predicate is the same as the preview's, but assert it —
        # if the row count drifted mid-transaction, roll back rather than
        # commit a write the operator never reviewed.
        if written != total:
            conn.rollback()
            print(
                f"\nABORT: updated {written:,} rows but the preview counted "
                f"{total:,} — rolled back, nothing committed."
            )
            return 1
        conn.commit()
    print(f"\nApplied — {written:,} rows linked to their round.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
