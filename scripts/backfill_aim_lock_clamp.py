#!/usr/bin/env python3
"""Clamp historical proximity_aim_lock.duration_ms inflated before the Lua fix.

The pre-fix Lua flushed open locks at round-END time instead of last_seen,
inflating duration_ms (the headline lock-time leaderboard) by ~20%. The fix
(proximity_tracker.lua) closes at last_seen AND clamps duration to
samples*interval + interval. This one-off applies the same clamp to historical
rows so the leaderboard isn't skewed by the pre-fix data; end_time is realigned
to start_time + clamped duration to stay consistent.

DRY-RUN by default. Pass --apply to write. Idempotent (only touches rows still
above the clamp). interval defaults to 400ms (config.aim_lock.interval_ms);
override with --interval-ms.

Usage:
    python -m scripts.backfill_aim_lock_clamp                 # dry-run
    python -m scripts.backfill_aim_lock_clamp --apply
    python -m scripts.backfill_aim_lock_clamp --interval-ms 400 --apply

Run scripts/db_backup.sh first.
"""
from __future__ import annotations

import argparse
import contextlib
import os
import sys

try:
    import psycopg2 as _pg
except ImportError:  # pragma: no cover
    try:
        import psycopg as _pg  # psycopg3
    except ImportError:  # pragma: no cover
        raise SystemExit(
            "This script needs a PostgreSQL driver: pip install psycopg2-binary"
        ) from None

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
    ap.add_argument("--interval-ms", type=int, default=400,
                    help="aim_lock sample interval (default 400, matches Lua config)")
    args = ap.parse_args()
    iv = max(1, args.interval_ms)

    conn = _connect()
    conn.autocommit = False
    cur = conn.cursor()

    # max legitimate duration = samples*interval + interval (one grace interval).
    cur.execute(
        "SELECT COUNT(*), COALESCE(SUM(duration_ms - (GREATEST(samples,1)*%s + %s)),0) "
        "FROM proximity_aim_lock WHERE duration_ms > GREATEST(samples,1)*%s + %s",
        (iv, iv, iv, iv),
    )
    n_over, phantom = cur.fetchone()

    print("=" * 60)
    print("aim-lock duration CLAMP BACKFILL — " + ("APPLY" if args.apply else "DRY-RUN"))
    print("=" * 60)
    print(f"interval={iv}ms  clamp = samples*{iv} + {iv}")
    if not n_over:
        print("No rows above the clamp — already consistent. ✅")
        cur.close()
        conn.close()
        return 0
    print(f"  rows above clamp: {n_over}")
    print(f"  phantom ms to remove (sum of overage): {int(phantom)}")

    if not args.apply:
        print("\nDRY-RUN — no changes written. Run scripts/db_backup.sh, then re-run with --apply.")
        cur.close()
        conn.close()
        return 0

    cur.execute(
        "UPDATE proximity_aim_lock "
        "SET duration_ms = GREATEST(samples,1)*%s + %s, "
        "    end_time = start_time + (GREATEST(samples,1)*%s + %s) "
        "WHERE duration_ms > GREATEST(samples,1)*%s + %s",
        (iv, iv, iv, iv, iv, iv),
    )
    conn.commit()
    print(f"\n✅ Committed. {cur.rowcount} aim-lock rows clamped.")
    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
