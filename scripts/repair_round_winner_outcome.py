#!/usr/bin/env python3
"""repair_round_winner_outcome.py — historical repair of rounds.winner_team
(pre-Lua R2 rows) and rounds.round_outcome (time-heuristic mislabels).

Two distinct historical defects (audit 2026-08-14), which MUST be repaired in
this order because the second derives from the first:

PHASE W — pre-2026-02 R2 rows carry R1's winner. Before the Lua webhook
override (first lua_round_teams capture 2026-01-24), the import left the R1
winner on the R2 row: R1winner == R2winner on ~99% of pre-Lua matches, which
is statistically impossible for stopwatch. The correct R2 winner survives
in-DB on the round_number=0 match-summary row, which is written from the R2
file's own header and shares round_date + round_time + map_name with the R2
row. This phase copies that known-correct value; rows with a lua_round_teams
link are never touched (the webhook already wrote the truth there).

PHASE O — round_outcome was a pure time heuristic (map_time - actual_time <=
30s → 'Fullhold'), mislabeling every objective completed in the final 30
seconds; 31% of stored 'Fullhold' rows contradicted their own winner_team.
The live import now derives the outcome from winner/defender
(round_contract.derive_round_outcome, PR #728); this phase applies the same
rule to history: Fullhold iff winner_team == defender_team, both sides known.
Rows whose sides are unknown (defender_team/winner_team = 0 — includes the
2025-12→2026-02 bulk-import era) and rows with a blank outcome are left
alone: there is nothing trustworthy to derive from.

Follows scripts/repair_proximity_orphan_round_links.py: dry-run by default,
--apply guarded by --expect-rows (the total the dry run reported) and
--expect-db (the exact server), single transaction, rollback on any drift.

Usage:
    # 1. preview, note the total it reports
    python scripts/repair_round_winner_outcome.py

    # 2. write, restating that total and the server identity
    python scripts/repair_round_winner_outcome.py --apply \
        --expect-rows 417 --expect-db localhost:5432/etlegacy
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

# Phase W candidates: pre-Lua R2 rows whose summary row disagrees. BOTH sides
# of the timestamp-tuple identity are `= 1`-guarded (CodeRabbit on #729): the
# summary-side guard skips an ambiguous source, and the symmetric R2-side
# guard skips the case where two R2 rows share (date, time, map) — otherwise
# both would receive the same summary winner and one of them would be wrong.
# (match_id cannot serve as the join key here: pre-Lua summary rows carry a
# filename-based match_id that matches their R2 row on only 44/278 candidates.)
_W_FROM = """
    FROM rounds r2
    JOIN rounds s
      ON s.round_number = 0
     AND s.round_date = r2.round_date
     AND s.round_time = r2.round_time
     AND s.map_name = r2.map_name
    WHERE r2.round_number = 2
      AND r2.round_date < '2026-02-01'
      AND s.winner_team IN (1, 2)
      AND r2.winner_team IS DISTINCT FROM s.winner_team
      AND NOT EXISTS (SELECT 1 FROM lua_round_teams l WHERE l.round_id = r2.id)
      AND (
        SELECT COUNT(*) FROM rounds s2
        WHERE s2.round_number = 0
          AND s2.round_date = r2.round_date
          AND s2.round_time = r2.round_time
          AND s2.map_name = r2.map_name
      ) = 1
      AND (
        SELECT COUNT(*) FROM rounds r3
        WHERE r3.round_number = 2
          AND r3.round_date = r2.round_date
          AND r3.round_time = r2.round_time
          AND r3.map_name = r2.map_name
      ) = 1
"""

_W_PREVIEW = f"SELECT substr(r2.round_date, 1, 7) AS era, COUNT(*) {_W_FROM} GROUP BY 1 ORDER BY 1"
_W_APPLY = f"UPDATE rounds x SET winner_team = w.new_winner FROM (SELECT r2.id, s.winner_team AS new_winner {_W_FROM}) w WHERE x.id = w.id"

# Phase O: derive the outcome from (post-W) winner/defender. Only rows where
# both sides are known and a non-blank outcome disagrees with the derivation.
_O_WHERE = """
    WHERE round_number IN (1, 2)
      AND winner_team IN (1, 2)
      AND defender_team IN (1, 2)
      AND COALESCE(round_outcome, '') <> ''
      AND round_outcome IS DISTINCT FROM
          (CASE WHEN winner_team = defender_team THEN 'Fullhold' ELSE 'Completed' END)
"""

# Dry-run must count Phase O AS IF Phase W had run (W changes winners, which
# changes O's candidate set), so the simulated winner is COALESCE(summary fix,
# stored value).
_O_PREVIEW_SIMULATED = f"""
    WITH w AS (SELECT r2.id, s.winner_team AS new_winner {_W_FROM})
    SELECT substr(r.round_date, 1, 7) AS era,
           CASE WHEN COALESCE(w.new_winner, r.winner_team) = r.defender_team
                THEN 'Fullhold' ELSE 'Completed' END AS derived,
           COUNT(*)
    FROM rounds r
    LEFT JOIN w ON w.id = r.id
    WHERE r.round_number IN (1, 2)
      AND COALESCE(w.new_winner, r.winner_team) IN (1, 2)
      AND r.defender_team IN (1, 2)
      AND COALESCE(r.round_outcome, '') <> ''
      AND r.round_outcome IS DISTINCT FROM
          (CASE WHEN COALESCE(w.new_winner, r.winner_team) = r.defender_team
                THEN 'Fullhold' ELSE 'Completed' END)
    GROUP BY 1, 2 ORDER BY 1, 2
"""

_O_APPLY = f"""
    UPDATE rounds
    SET round_outcome = CASE WHEN winner_team = defender_team
                             THEN 'Fullhold' ELSE 'Completed' END
    {_O_WHERE}
"""

# Post-apply invariant: on the gated set (both sides known, non-blank outcome)
# there must be zero remaining contradictions.
_POST_CHECK = f"SELECT COUNT(*) FROM rounds {_O_WHERE}"


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
        "--expect-rows", type=int,
        help="total (W+O) row count the dry run reported; REQUIRED with --apply",
    )
    parser.add_argument(
        "--expect-db",
        help="server this must run against as host:port/database; REQUIRED with --apply",
    )
    args = parser.parse_args()

    if args.apply and (args.expect_rows is None or not args.expect_db):
        parser.error(
            "--apply requires --expect-rows and --expect-db "
            "(run without --apply first and pass back what it reports)"
        )

    target = get_target_dsn_parts()
    identity = f"{target['host']}:{target['port']}/{target['database']}"
    print(f"Target: {identity}")
    if args.expect_db and args.expect_db != identity:
        print(f"ABORT: --expect-db={args.expect_db!r} but target is {identity!r}")
        return 1

    with _connect() as conn, conn.cursor() as cur:
        print("\nPHASE W — pre-Lua R2 winner repaired from the match-summary row:")
        cur.execute(_W_PREVIEW)
        w_rows = cur.fetchall()
        w_total = sum(r[1] for r in w_rows)
        for era, n in w_rows:
            print(f"  {era}  {n:>5,} rows")
        print(f"  total {w_total:>5,} rows")

        print("\nPHASE O — outcome re-derived from winner/defender (post-W state):")
        cur.execute(_O_PREVIEW_SIMULATED)
        o_rows = cur.fetchall()
        o_total = sum(r[2] for r in o_rows)
        for era, derived, n in o_rows:
            print(f"  {era}  → {derived:<10} {n:>5,} rows")
        print(f"  total {o_total:>5,} rows")

    total = w_total + o_total
    print(f"\nTotal rows to change: {total:,} (W {w_total:,} + O {o_total:,})")

    if not args.apply:
        print("\nDry run — nothing written. Re-run with --apply to write.")
        return 0

    if args.expect_rows != total:
        print(
            f"ABORT: --expect-rows={args.expect_rows} but the current candidate "
            f"set is {total} (it shifted since the preview)."
        )
        return 1

    with _connect() as conn, conn.cursor() as cur:
        cur.execute(_W_APPLY)
        w_written = cur.rowcount
        print(f"\n  Phase W: repaired winner_team on {w_written:,} R2 rows")
        cur.execute(_O_APPLY)
        o_written = cur.rowcount
        print(f"  Phase O: re-derived round_outcome on {o_written:,} rows")
        if w_written != w_total or o_written != o_total:
            conn.rollback()
            print(
                f"\nABORT: wrote W={w_written:,}/O={o_written:,} but the preview "
                f"counted W={w_total:,}/O={o_total:,} — rolled back, nothing committed."
            )
            return 1
        cur.execute(_POST_CHECK)
        remaining = cur.fetchone()[0]
        if remaining != 0:
            conn.rollback()
            print(
                f"\nABORT: {remaining} contradictions remain on the gated set "
                "after apply — rolled back, nothing committed."
            )
            return 1
        conn.commit()
    print(f"\nApplied — {w_written + o_written:,} rows repaired; gated set is contradiction-free.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
