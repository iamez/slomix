#!/usr/bin/env python3
"""Backfill rounds.is_valid for existing filler rounds.

Flips is_valid = FALSE for rounds whose map is in the configured blocklist
(EXCLUDED_MAPS, default mp_sillyctf) — the non-competitive "filler" maps run
while waiting for a substitution. New rounds are flagged at import time
(bot/services/stats_import_mixin); this one-off handles history.

DRY-RUN by default (prints what would change). Pass --apply to write.
Idempotent: re-running is a no-op once flagged.

Usage:
    python -m scripts.backfill_rounds_is_valid            # dry-run
    python -m scripts.backfill_rounds_is_valid --apply
"""
from __future__ import annotations

import argparse
import contextlib
import os
import sys

# Accept psycopg2 or psycopg(v3); fail with an actionable hint otherwise.
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


def _excluded_maps() -> list[str]:
    with contextlib.suppress(Exception):
        from dotenv import load_dotenv

        load_dotenv()
    raw = os.getenv("EXCLUDED_MAPS", "mp_sillyctf") or ""
    return [m.strip().lower() for m in raw.split(",") if m.strip()]


def _connect():
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

    excluded = _excluded_maps()
    if not excluded:
        print("EXCLUDED_MAPS is empty — nothing to do.")
        return 0

    conn = _connect()
    conn.autocommit = False
    cur = conn.cursor()

    # Count rounds currently is_valid=TRUE that are on a filler map.
    cur.execute(
        "SELECT map_name, COUNT(*) FROM rounds "
        "WHERE LOWER(map_name) = ANY(%s) AND is_valid = TRUE "
        "GROUP BY map_name ORDER BY map_name",
        (excluded,),
    )
    pending = cur.fetchall()

    print("=" * 56)
    print("rounds.is_valid BACKFILL — " + ("APPLY" if args.apply else "DRY-RUN"))
    print("=" * 56)
    print(f"Blocklist (EXCLUDED_MAPS): {', '.join(excluded)}")
    total = sum(n for _m, n in pending)
    if not pending:
        print("Nothing to flag — already consistent. ✅")
        cur.close()
        conn.close()
        return 0
    for map_name, n in pending:
        print(f"  would flag is_valid=FALSE: {map_name}  ({n} rounds)")
    print(f"Total rounds to flag: {total}")

    if not args.apply:
        print("\nDRY-RUN — no changes written. Re-run with --apply to commit.")
        cur.close()
        conn.close()
        return 0

    cur.execute(
        "UPDATE rounds SET is_valid = FALSE "
        "WHERE LOWER(map_name) = ANY(%s) AND is_valid = TRUE",
        (excluded,),
    )
    conn.commit()
    print(f"\n✅ Committed. {cur.rowcount} rounds flagged is_valid=FALSE.")
    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
