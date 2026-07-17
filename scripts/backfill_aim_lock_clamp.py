#!/usr/bin/env python3
"""Clamp historical proximity_aim_lock.duration_ms inflated before the Lua fix.

The pre-fix Lua flushed open locks at round-END time instead of last_seen,
inflating duration_ms (the headline lock-time leaderboard) by ~20%. The fix
(proximity_tracker.lua) closes at last_seen AND clamps duration to
samples*interval + interval. This one-off applies the same clamp to historical
rows so the leaderboard isn't skewed by the pre-fix data; end_time is realigned
to start_time + clamped duration to stay consistent.

DRY-RUN by default: prints candidate count, total phantom ms, newest violation
session_date, and a SHA-256 fingerprint of the ordered candidate id list.

--apply is guarded (audit remediation plan U3): it requires the operator to
pass the expected count, phantom ms, newest date, and fingerprint from a fresh
dry-run. Any mismatch — e.g. new violating rows appeared since the dry-run, or
the script targets a different database — aborts before writing anything.
The UPDATE is scoped to exactly the fingerprinted candidate ids.

Usage:
    python -m scripts.backfill_aim_lock_clamp                 # dry-run
    python -m scripts.backfill_aim_lock_clamp --apply \\
        --expect-count 56 --expect-phantom-ms 726050 \\
        --expect-latest-date 2026-06-11 --expect-fingerprint <sha256> \\
        --expect-db <host:port/dbname>

--expect-db binds the apply to the intended database (host:port/dbname printed
by the dry-run): a clone/snapshot of production commonly has IDENTICAL candidate
rows and fingerprint, so without it the guard could mutate the wrong DB.

Run scripts/db_backup.sh first.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
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


def fingerprint_ids(ids: list[int]) -> str:
    """SHA-256 over the newline-joined ordered id list."""
    return hashlib.sha256("\n".join(str(i) for i in ids).encode()).hexdigest()


def check_expectations(stats: dict, args) -> list[str]:
    """Compare measured candidate stats against --expect-* args.

    Returns a list of human-readable mismatch descriptions (empty = safe).
    """
    problems = []
    checks = [
        ("count", stats["count"], args.expect_count),
        ("phantom-ms", stats["phantom_ms"], args.expect_phantom_ms),
        ("latest-date", str(stats["latest_date"]), args.expect_latest_date),
        ("fingerprint", stats["fingerprint"], args.expect_fingerprint),
        ("db", stats.get("db_identity"), args.expect_db),
    ]
    for name, measured, expected in checks:
        if expected is None:
            problems.append(f"--expect-{name} is required with --apply")
        elif str(measured) != str(expected):
            problems.append(
                f"--expect-{name} mismatch: expected {expected}, measured {measured}"
            )
    return problems


def measure(cur, iv: int) -> dict:
    """Collect candidate rows above the clamp with a stable fingerprint."""
    cur.execute(
        "SELECT id, session_date, duration_ms - (GREATEST(samples,1)*%s + %s) AS overage "
        "FROM proximity_aim_lock WHERE duration_ms > GREATEST(samples,1)*%s + %s "
        "ORDER BY id",
        (iv, iv, iv, iv),
    )
    rows = cur.fetchall()
    ids = [r[0] for r in rows]
    return {
        "ids": ids,
        "count": len(rows),
        "phantom_ms": int(sum(r[2] for r in rows)),
        "latest_date": max((r[1] for r in rows), default=None),
        "fingerprint": fingerprint_ids(ids),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write changes (else dry-run)")
    ap.add_argument("--interval-ms", type=int, default=400,
                    help="aim_lock sample interval (default 400, matches Lua config)")
    ap.add_argument("--expect-count", type=int, default=None,
                    help="required with --apply: candidate count from dry-run")
    ap.add_argument("--expect-phantom-ms", type=int, default=None,
                    help="required with --apply: phantom ms sum from dry-run")
    ap.add_argument("--expect-latest-date", default=None,
                    help="required with --apply: newest violation date (YYYY-MM-DD)")
    ap.add_argument("--expect-fingerprint", default=None,
                    help="required with --apply: candidate-id SHA-256 from dry-run")
    ap.add_argument("--expect-db", default=None,
                    help="required with --apply: target DB identity host:port/dbname "
                         "from dry-run — binds the guard to the intended database so a "
                         "clone/snapshot with identical candidate rows can't be mutated")
    args = ap.parse_args()
    iv = max(1, args.interval_ms)

    conn = _connect()
    conn.autocommit = False
    cur = conn.cursor()

    # Target DB identity: candidate count/fingerprint alone are commonly IDENTICAL
    # on a restored clone of production, so bind the guard to WHICH database this
    # is (Codex #509). host:port come from the connection env; current_database()
    # is authoritative for the name.
    cur.execute("SELECT current_database()")
    db_identity = "{}:{}/{}".format(
        os.getenv("POSTGRES_HOST", "localhost"),
        os.getenv("POSTGRES_PORT", "5432"),
        cur.fetchone()[0],
    )

    stats = measure(cur, iv)
    stats["db_identity"] = db_identity

    print("=" * 60)
    print("aim-lock duration CLAMP BACKFILL — " + ("APPLY" if args.apply else "DRY-RUN"))
    print("=" * 60)
    print(f"target database: {db_identity}")
    print(f"interval={iv}ms  clamp = samples*{iv} + {iv}")
    print(f"  rows above clamp: {stats['count']}")
    if stats["count"]:
        print(f"  phantom ms to remove (sum of overage): {stats['phantom_ms']}")
        print(f"  newest violation session_date: {stats['latest_date']}")
        print(f"  candidate fingerprint: {stats['fingerprint']}")

    if not args.apply:
        if not stats["count"]:
            print("\nNo rows above the clamp — already consistent. ✅")
        else:
            print("\nDRY-RUN — no changes written. Run scripts/db_backup.sh, then re-run with:")
            print(f"  --apply --expect-count {stats['count']} "
                  f"--expect-phantom-ms {stats['phantom_ms']} "
                  f"--expect-latest-date {stats['latest_date']} "
                  f"--expect-fingerprint {stats['fingerprint']} "
                  f"--expect-db {stats['db_identity']}")
        cur.close()
        conn.close()
        return 0

    # --apply: verify the measured candidate set matches the dry-run's --expect-*
    # values BEFORE any success return — even for a zero-row measurement. Pointing
    # --apply at the wrong DB, or one already mutated since the dry-run, otherwise
    # no-ops to 0 rows and exits 0 without ever checking --expect-count 56 / the
    # fingerprint, masking a failed correction (Codex review on #509).
    problems = check_expectations(stats, args)
    if problems:
        print("\nABORTED — preconditions not met, nothing written:")
        for p in problems:
            print(f"  ✗ {p}")
        print("Re-run the dry-run and pass its exact values with --apply.")
        cur.close()
        conn.close()
        return 1

    if not stats["count"]:
        print("\nExpectations matched but no rows are above the clamp — nothing to write. ✅")
        cur.close()
        conn.close()
        return 0

    cur.execute(
        "UPDATE proximity_aim_lock "
        "SET duration_ms = GREATEST(samples,1)*%s + %s, "
        "    end_time = start_time + (GREATEST(samples,1)*%s + %s) "
        "WHERE id = ANY(%s) AND duration_ms > GREATEST(samples,1)*%s + %s",
        (iv, iv, iv, iv, stats["ids"], iv, iv),
    )
    if cur.rowcount != stats["count"]:
        conn.rollback()
        print(f"\nABORTED — UPDATE matched {cur.rowcount} rows, expected {stats['count']}; "
              "rolled back, nothing written.")
        cur.close()
        conn.close()
        return 1

    # Verify residual BEFORE committing: measure() runs inside the still-open
    # transaction, so it sees our scoped UPDATE plus any row a concurrent session
    # committed since the initial measurement. If a NEW violating row appeared,
    # roll back rather than commit a partial correction — honoring the guard's
    # promise that a changed candidate set aborts before writing (Codex #509).
    residual = measure(cur, iv)
    if residual["count"]:
        conn.rollback()
        print(f"\nABORTED — {residual['count']} row(s) above the clamp after the scoped "
              "UPDATE (candidate set changed concurrently); rolled back, nothing written.")
        cur.close()
        conn.close()
        return 1

    conn.commit()
    print(f"\n✅ Committed. {stats['count']} aim-lock rows clamped. "
          "Pre-commit re-check: 0 rows above the clamp. ✅")
    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
