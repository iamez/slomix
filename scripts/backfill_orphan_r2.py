#!/usr/bin/env python3
"""Backfill round_status='orphan_r2' + is_valid=FALSE for historical orphan R2 rounds.

An "orphan R2" is a Round-2 row with no matching Round-1 *for the same match* — its
stats are RAW CUMULATIVE (R1+R2), not a differential, so they inflate aggregates.
New imports are flagged at parse/import time (community_stats_parser +
stats_import_mixin, the 2026-06 Wave-2 fix); this one-off marks the history so the
same central `is_valid` filter excludes them too.

Pairing is keyed on `match_id` (the canonical R1<->R2 pairing key, 100% populated
and deterministic since the stopwatch-pairer backfill, PR #370). A map+session
predicate would miss orphans in sessions where the same map is played more than
once: an unrelated R1 of that map exists, so the broken R2 looks "paired". Keying
on match_id pairs each R2 to its own R1 and catches those (e.g. an adlernest R2 at
21:40 whose R1 is missing, while a separate adlernest R1 at 21:48 exists).

DRY-RUN by default (prints what would change). Pass --apply to write.
Idempotent: rows already round_status='orphan_r2' are skipped.

Usage:
    python -m scripts.backfill_orphan_r2            # dry-run
    python -m scripts.backfill_orphan_r2 --apply

Run scripts/db_backup.sh first.
"""
from __future__ import annotations

import argparse
import contextlib
import os
import sys

try:
    import psycopg2 as _pg
except ImportError:  # pragma: no cover - environment-dependent
    try:
        import psycopg as _pg  # psycopg3
    except ImportError:  # pragma: no cover
        raise SystemExit(
            "This script needs a PostgreSQL driver: pip install psycopg2-binary"
        ) from None

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# An R2 with no R1 sharing its match_id. Scoped to rows that actually carry a
# match_id (skip the unpairable rather than mis-flag it). Both statements below
# are fully static SQL literals (no parameters, no string building) — the orphan
# predicate is duplicated verbatim rather than concatenated so there is provably
# no dynamic query construction.
_COUNT_QUERY = """
    SELECT r2.map_name, COUNT(*)
    FROM rounds r2
    WHERE r2.round_number = 2
      AND r2.match_id IS NOT NULL
      AND r2.match_id <> ''
      AND r2.round_status IS DISTINCT FROM 'orphan_r2'
      AND NOT EXISTS (
          SELECT 1 FROM rounds r1
          WHERE r1.round_number = 1
            AND r1.match_id = r2.match_id
      )
    GROUP BY r2.map_name
    ORDER BY COUNT(*) DESC
"""

_UPDATE_QUERY = """
    UPDATE rounds SET round_status = 'orphan_r2', is_valid = FALSE
    WHERE id IN (
        SELECT r2.id
        FROM rounds r2
        WHERE r2.round_number = 2
          AND r2.match_id IS NOT NULL
          AND r2.match_id <> ''
          AND r2.round_status IS DISTINCT FROM 'orphan_r2'
          AND NOT EXISTS (
              SELECT 1 FROM rounds r1
              WHERE r1.round_number = 1
                AND r1.match_id = r2.match_id
          )
    )
"""


def _connect():
    with contextlib.suppress(Exception):
        from dotenv import load_dotenv
        load_dotenv()
    return _pg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DATABASE", "etlegacy"),
        user=os.getenv("POSTGRES_USER", "etlegacy_user"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write changes (else dry-run)")
    args = ap.parse_args()

    conn = _connect()
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute(_COUNT_QUERY)
    pending = cur.fetchall()

    print("=" * 60)
    print("orphan-R2 BACKFILL — " + ("APPLY" if args.apply else "DRY-RUN"))
    print("=" * 60)
    total = sum(n for _m, n in pending)
    if not pending:
        print("No orphan R2 rounds found — already consistent. ✅")
        cur.close()
        conn.close()
        return 0
    for map_name, n in pending:
        print(f"  would mark orphan_r2 + is_valid=FALSE: {map_name}  ({n} rounds)")
    print(f"Total R2 rounds to mark: {total}")

    if not args.apply:
        print("\nDRY-RUN — no changes written. Run scripts/db_backup.sh, then re-run with --apply.")
        cur.close()
        conn.close()
        return 0

    cur.execute(_UPDATE_QUERY)
    conn.commit()
    print(f"\n✅ Committed. {cur.rowcount} R2 rounds marked orphan_r2 / is_valid=FALSE.")
    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
