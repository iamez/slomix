#!/usr/bin/env python3
"""
Relink lua_round_teams.round_id using the round_linker algorithm.

Fixes the race condition where Lua webhook data was linked to the wrong round
because the correct round hadn't been imported yet at insert time.

Usage:
    python scripts/relink_lua_round_teams.py                    # Dry run (default)
    python scripts/relink_lua_round_teams.py --apply            # Apply changes
    python scripts/relink_lua_round_teams.py --session 9973     # Specific session
    python scripts/relink_lua_round_teams.py --since 2026-02-26 # Since date

Environment:
    Reads DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD from .env or environment.
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)
# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    import psycopg2 as psycopg
except ImportError:
    try:
        import psycopg
    except ImportError:
        print("ERROR: Neither psycopg2 nor psycopg installed. Run: pip install psycopg2-binary")
        sys.exit(1)


def load_env():
    """Load .env file if present."""
    env_path = project_root / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def get_db_params():
    """Get PostgreSQL connection parameters from environment.

    Supports both naming conventions:
    - POSTGRES_HOST / POSTGRES_PORT / POSTGRES_DATABASE / POSTGRES_USER / POSTGRES_PASSWORD
    - DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD
    """
    return {
        "host": os.environ.get("POSTGRES_HOST", os.environ.get("DB_HOST", "localhost")),
        "port": int(os.environ.get("POSTGRES_PORT", os.environ.get("DB_PORT", "5432"))),
        "dbname": os.environ.get("POSTGRES_DATABASE", os.environ.get("DB_NAME", "etlegacy")),
        "user": os.environ.get("POSTGRES_USER", os.environ.get("DB_USER", "etlegacy_user")),
        "password": os.environ.get("POSTGRES_PASSWORD", os.environ.get("DB_PASSWORD", "")),
    }


def parse_round_datetime(round_date, round_time):
    """Parse round_date + round_time into a datetime (mirrors round_linker logic)."""
    if not round_date or not round_time:
        return None
    clean_time = str(round_time).replace(":", "")
    if len(clean_time) != 6:
        return None
    try:
        return datetime.strptime(f"{round_date} {clean_time}", "%Y-%m-%d %H%M%S")
    except ValueError:
        return None


def resolve_best_round(cursor, map_name, round_number, lua_end_unix, lua_start_unix, window_minutes=45):
    """
    Find the best matching round for a lua_round_teams record.
    Mirrors bot/core/round_linker.py logic.
    """
    lua_ts = lua_end_unix or lua_start_unix
    if not lua_ts:
        return None, None

    try:
        target_dt = datetime.fromtimestamp(int(lua_ts))
    except (OSError, ValueError):
        return None, None

    cursor.execute(
        """
        SELECT id, round_date, round_time, created_at
        FROM rounds
        WHERE map_name = %s AND round_number = %s
        ORDER BY created_at DESC
        LIMIT 20
        """,
        (map_name, round_number),
    )
    candidates = cursor.fetchall()
    if not candidates:
        return None, None

    max_diff_seconds = window_minutes * 60
    best_id = None
    best_diff = float("inf")

    for row in candidates:
        rid, r_date, r_time, created_at = row
        candidate_dt = parse_round_datetime(r_date, r_time)
        if not candidate_dt and created_at:
            if isinstance(created_at, str):
                try:
                    candidate_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00")).replace(tzinfo=None)
                except ValueError:
                    continue
            else:
                candidate_dt = created_at.replace(tzinfo=None) if hasattr(created_at, "tzinfo") and created_at.tzinfo else created_at

        if not candidate_dt:
            continue

        diff = abs((candidate_dt - target_dt).total_seconds())
        if diff <= max_diff_seconds and diff < best_diff:
            best_diff = diff
            best_id = rid

    return best_id, best_diff if best_id else None


def main():
    logger.info("Script started: %s", __file__)
    parser = argparse.ArgumentParser(description="Relink lua_round_teams round_id values")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry run)")
    parser.add_argument("--session", type=int, help="Only process rounds from this gaming_session_id")
    parser.add_argument("--since", type=str, help="Only process records captured after this date (YYYY-MM-DD)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all records, not just changes")
    args = parser.parse_args()

    load_env()
    db_params = get_db_params()

    print(f"{'=' * 70}")
    print("Lua Round Teams Re-Linker")
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print(f"Database: {db_params['user']}@{db_params['host']}:{db_params['port']}/{db_params['dbname']}")
    if args.session:
        print(f"Filter: gaming_session_id = {args.session}")
    if args.since:
        print(f"Filter: captured_at >= {args.since}")
    print(f"{'=' * 70}\n")

    conn = psycopg.connect(**db_params)
    cursor = conn.cursor()

    # Build query for lua records to check
    query = """
        SELECT lrt.id, lrt.match_id, lrt.round_number, lrt.map_name,
               lrt.round_end_unix, lrt.round_start_unix,
               lrt.round_id, lrt.actual_duration_seconds, lrt.captured_at
        FROM lua_round_teams lrt
        WHERE lrt.map_name IS NOT NULL
    """
    params = []

    if args.session:
        # Filter by rounds in this session
        query += """
          AND (lrt.round_id IS NULL OR lrt.round_id IN (
              SELECT id FROM rounds WHERE gaming_session_id = %s
          ))
        """
        params.append(args.session)

    if args.since:
        query += " AND lrt.captured_at >= %s"
        params.append(args.since)

    query += " ORDER BY lrt.id"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    total = len(rows)
    changed = 0
    unchanged = 0
    unresolved = 0

    print(f"Processing {total} lua_round_teams records...\n")
    print(f"{'ID':>6} {'match_id':<22} {'R#':>2} {'map':<20} {'dur':>5} {'old_rid':>8} {'new_rid':>8} {'diff_s':>7} {'status'}")
    print(f"{'-' * 100}")

    for row in rows:
        lua_id, match_id, rn, map_name, end_unix, start_unix, current_rid, dur, captured = row

        best_rid, best_diff = resolve_best_round(cursor, map_name, rn, end_unix, start_unix)

        if best_rid is None:
            unresolved += 1
            if args.verbose:
                print(f"{lua_id:>6} {match_id or '?':<22} {rn:>2} {map_name:<20} {dur or 0:>5} {current_rid or 'NULL':>8} {'?':>8} {'':>7} UNRESOLVED")
            continue

        if best_rid == current_rid:
            unchanged += 1
            if args.verbose:
                print(f"{lua_id:>6} {match_id or '?':<22} {rn:>2} {map_name:<20} {dur or 0:>5} {current_rid or 'NULL':>8} {best_rid:>8} {best_diff:>7.0f} OK")
            continue

        changed += 1
        old_display = str(current_rid) if current_rid else "NULL"
        print(f"{lua_id:>6} {match_id or '?':<22} {rn:>2} {map_name:<20} {dur or 0:>5} {old_display:>8} {best_rid:>8} {best_diff:>7.0f} RELINK")

        if args.apply:
            cursor.execute(
                "UPDATE lua_round_teams SET round_id = %s WHERE id = %s",
                (best_rid, lua_id),
            )

    print(f"\n{'=' * 70}")
    print(f"Summary: {total} records checked")
    print(f"  Changed:    {changed}")
    print(f"  Unchanged:  {unchanged}")
    print(f"  Unresolved: {unresolved}")

    if args.apply and changed > 0:
        conn.commit()
        print(f"\n✅ {changed} records updated in database.")
    elif changed > 0:
        conn.rollback()
        print(f"\n⚠️  DRY RUN: {changed} records would be changed. Run with --apply to commit.")
    else:
        print("\n✅ No changes needed.")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
