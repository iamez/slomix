#!/usr/bin/env python3
"""Restore winner_team / defender_team from the raw endstats files.

245 rounds — almost all from the 2025-12 bulk import — carry winner_team = 0 or
defender_team = 0. Sides are the foundation of scoring: without them a fullhold
cannot be told from an objective completion, so those rounds fall back to the
parser's time heuristic and score wrong. Worse, 17 of them hold a winner that is
the exact inverse of the file's (audit 2026-08-14).

The endstats file the round was imported from is still on disk and states both
sides in its header:

    ^a#^7p^au^7rans^a.^7only\\supply\\legacy3\\1\\1\\2\\12:00\\11:57\\716261
                                            ^  ^  ^
                                    round --'  |  '-- winner
                                          defender

So this copies a fact, it never derives one. Rounds whose sides already parsed
are NEVER touched: their data is trusted, and one such row (a duplicate file
from a forced map change) legitimately disagrees with its file while the
database holds the Lua-verified truth.

Once the sides are restored, round_outcome is re-derived with the shared rule
(round_contract.derive_round_outcome) so the repaired rounds stop relying on
the +-30s heuristic.

Usage:
    python scripts/repair_round_sides_from_stats_files.py
    python scripts/repair_round_sides_from_stats_files.py --apply \
        --expect-rows 245 --expect-db localhost:5432/etlegacy
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.core.round_contract import derive_round_outcome  # noqa: E402
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

_FILENAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{6})-(.+)-round-([12])\.txt$")


def _connect():
    if _pg is None:
        raise SystemExit("psycopg2/psycopg not installed")
    kwargs = get_connection_kwargs()
    kwargs["dbname"] = kwargs.pop("database")
    return _pg.connect(**kwargs)


def read_headers(stats_dir: Path) -> dict[tuple, tuple[int, int, str, str]]:
    """Filename identity -> (defender, winner, time_limit, actual_time)."""
    out: dict[tuple, tuple[int, int, str, str]] = {}
    for path in sorted(stats_dir.glob("*-round-*.txt")):
        match = _FILENAME.match(path.name)
        if not match:
            continue
        date, time_str, map_name, round_number = match.groups()
        try:
            with path.open(encoding="utf-8", errors="replace") as handle:
                fields = handle.readline().rstrip("\n").split("\\")
            defender, winner = int(fields[4]), int(fields[5])
            limit, actual = fields[6], fields[7]
        except (OSError, ValueError, IndexError):
            continue
        if defender not in (1, 2) or winner not in (1, 2):
            continue        # the file itself is unusable — nothing to copy
        out[(date, time_str, map_name, int(round_number))] = (defender, winner, limit, actual)
    return out


def collect(cur, headers) -> list[tuple]:
    """Rounds with untrusted sides whose file states them. One row per round."""
    cur.execute(
        """
        SELECT id, round_date, round_time, map_name, round_number,
               winner_team, defender_team, round_outcome
        FROM rounds
        WHERE round_number IN (1, 2)
          AND (winner_team IS NULL OR winner_team = 0
               OR defender_team IS NULL OR defender_team = 0)
        """
    )
    rows = cur.fetchall()
    # Guard the identity: if two rounds share (date, time, map, number) the file
    # cannot say which one it belongs to, so both are skipped rather than guessed.
    identities = Counter(
        (str(r[1]), str(r[2]), r[3], int(r[4])) for r in rows
    )
    plan = []
    for rid, date, time_str, map_name, round_number, winner, defender, outcome in rows:
        key = (str(date), str(time_str), map_name, int(round_number))
        if identities[key] != 1 or key not in headers:
            continue
        file_defender, file_winner, limit, actual = headers[key]
        new_outcome = derive_round_outcome(
            file_winner, file_defender, limit, actual, round_number, sides_trusted=True
        )
        plan.append((rid, winner, defender, outcome, file_winner, file_defender, new_outcome))
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    parser.add_argument("--expect-rows", type=int, help="row count the dry run reported")
    parser.add_argument("--expect-db", help="server as host:port/database")
    parser.add_argument("--stats-dir", type=Path, default=ROOT / "local_stats")
    args = parser.parse_args()

    if args.apply and (args.expect_rows is None or not args.expect_db):
        parser.error("--apply requires --expect-rows and --expect-db")

    target = get_target_dsn_parts()
    identity = f"{target['host']}:{target['port']}/{target['database']}"
    print(f"Target: {identity}")
    if args.expect_db and args.expect_db != identity:
        print(f"ABORT: --expect-db={args.expect_db!r} but target is {identity!r}")
        return 1

    headers = read_headers(args.stats_dir)
    print(f"Stats files with usable sides: {len(headers):,} (from {args.stats_dir})")
    if not headers:
        print("Nothing to read — is --stats-dir right for this host?")
        return 2

    with _connect() as conn, conn.cursor() as cur:
        plan = collect(cur, headers)

    by_era: Counter = Counter()
    flipped = 0
    for _, winner, _, _, file_winner, _, _ in plan:
        if winner not in (None, 0) and winner != file_winner:
            flipped += 1
    with _connect() as conn, conn.cursor() as cur:
        for rid, *_ in plan:
            cur.execute("SELECT substr(round_date, 1, 7) FROM rounds WHERE id = %s", (rid,))
            by_era[cur.fetchone()[0]] += 1

    print("\nRounds whose sides the file can restore:")
    for era, count in sorted(by_era.items()):
        print(f"  {era}  {count:>4,}")
    print(f"  total {len(plan):>4,}")
    print(f"  of those, {flipped} currently hold the INVERSE of the file's winner")

    if not args.apply:
        print("\nDry run — nothing written. Re-run with --apply to write.")
        return 0

    if args.expect_rows != len(plan):
        print(f"ABORT: --expect-rows={args.expect_rows} but the plan is {len(plan)}")
        return 1

    with _connect() as conn, conn.cursor() as cur:
        for rid, _, _, _, file_winner, file_defender, new_outcome in plan:
            cur.execute(
                """
                UPDATE rounds
                SET winner_team = %s, defender_team = %s, round_outcome = %s
                WHERE id = %s
                  AND (winner_team IS NULL OR winner_team = 0
                       OR defender_team IS NULL OR defender_team = 0)
                """,
                (file_winner, file_defender, new_outcome, rid),
            )
        cur.execute(
            """
            SELECT COUNT(*) FROM rounds
            WHERE round_number IN (1, 2)
              AND winner_team IN (1, 2) AND defender_team IN (1, 2)
              AND COALESCE(round_outcome, '') <> ''
              AND round_outcome IS DISTINCT FROM
                  (CASE WHEN winner_team = defender_team THEN 'Fullhold' ELSE 'Completed' END)
            """
        )
        remaining = cur.fetchone()[0]
        if remaining:
            conn.rollback()
            print(f"\nABORT: {remaining} outcome contradictions remain — rolled back.")
            return 1
        conn.commit()
    print(f"\nApplied — sides restored on {len(plan):,} rounds, outcomes re-derived.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
