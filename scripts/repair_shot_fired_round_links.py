#!/usr/bin/env python3
"""Backfill round_id on historical proximity_shot_fired orphans.

proximity_shot_fired was absent from BOTH relinker lists (the fanout update
targets in ProximityCog._PROXIMITY_ROUND_ID_TABLES and the detection UNION in
relinker_mixin._DETECTION_TABLES) from its creation in migration 055 until
2026-08-04. A round whose shot_fired rows failed to link at import time was
therefore never retried: no leg reported it, so the fanout never ran for it.

Adding it to both lists fixes new rounds, but not old ones — the relinker
skips anything older than _PERMANENT_ORPHAN_AGE_HOURS (6h). This repairs the
backlog.

Method: propagate, never re-derive. For each orphan we look for a sibling row
in proximity_kill_outcome carrying the SAME four identity columns
(session_date, map_name, round_number, round_start_unix) and a non-NULL
round_id. kill_outcome was in the fanout the whole time, so its link is the
one the relinker already agreed on for that round. Copying it cannot invent a
link the system would not have made itself.

Rounds with no linked sibling, or with siblings disagreeing on round_id, are
left alone and reported — those need the round_linker, not a copy.

Follows scripts/repair_lua_round_links.py: dry-run by default, --apply to
write, and the historical mutation deliberately lives here rather than in a
migration so a normal deploy cannot perform it unattended.

Usage:
    python scripts/repair_shot_fired_round_links.py            # preview
    python scripts/repair_shot_fired_round_links.py --apply    # write
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


# One row per orphan round, with the sibling's verdict attached. A round is
# repairable only when its linked siblings agree unanimously — HAVING COUNT
# (DISTINCT round_id) = 1 — so a round whose kill_outcome rows are themselves
# split across two round_ids is reported rather than propagated.
_SURVEY_SQL = """
WITH orphans AS (
    SELECT session_date, map_name, round_number, round_start_unix,
           COUNT(*) AS orphan_rows
    FROM proximity_shot_fired
    WHERE round_id IS NULL
    GROUP BY 1, 2, 3, 4
),
siblings AS (
    SELECT session_date, map_name, round_number, round_start_unix,
           MIN(round_id) AS round_id,
           COUNT(DISTINCT round_id) AS distinct_round_ids
    FROM proximity_kill_outcome
    WHERE round_id IS NOT NULL
    GROUP BY 1, 2, 3, 4
)
SELECT o.session_date, o.map_name, o.round_number, o.round_start_unix,
       o.orphan_rows,
       CASE WHEN s.distinct_round_ids = 1 THEN s.round_id END AS resolved_round_id,
       COALESCE(s.distinct_round_ids, 0) AS distinct_round_ids
FROM orphans o
LEFT JOIN siblings s USING (session_date, map_name, round_number, round_start_unix)
ORDER BY o.session_date, o.map_name, o.round_number
"""

_APPLY_SQL = """
UPDATE proximity_shot_fired sf
SET round_id = %(round_id)s
WHERE sf.round_id IS NULL
  AND sf.session_date = %(session_date)s
  AND sf.map_name = %(map_name)s
  AND sf.round_number = %(round_number)s
  AND sf.round_start_unix = %(round_start_unix)s
"""


def _connect():
    if _pg is None:
        raise SystemExit("psycopg2/psycopg not installed")
    return _pg.connect(**get_connection_kwargs())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    parser.add_argument(
        "--expect-repairable-rows",
        type=int,
        help="abort unless the survey finds exactly this many repairable rows",
    )
    args = parser.parse_args()

    target = get_target_dsn_parts()
    print(f"Target: {target['database']} @ {target['host']}:{target['port']}")

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(_SURVEY_SQL)
            rows = cur.fetchall()

        repairable = [r for r in rows if r[5] is not None]
        skipped = [r for r in rows if r[5] is None]
        repairable_rows = sum(r[4] for r in repairable)
        skipped_rows = sum(r[4] for r in skipped)

        print(f"\nOrphan rounds: {len(rows)}  ({sum(r[4] for r in rows):,} rows)")
        print(f"  repairable:  {len(repairable):>3}  ({repairable_rows:,} rows)")
        print(f"  no verdict:  {len(skipped):>3}  ({skipped_rows:,} rows)")

        if skipped:
            print("\nLeft alone (no linked kill_outcome sibling, or siblings disagree):")
            for r in skipped:
                why = "siblings disagree" if r[6] > 1 else "no linked sibling"
                print(f"  {r[0]}  {r[1]:<16} R{r[2]}  {r[4]:>6,} rows  — {why}")

        if args.expect_repairable_rows is not None and args.expect_repairable_rows != repairable_rows:
            print(
                f"\nABORT: expected {args.expect_repairable_rows:,} repairable rows, "
                f"survey found {repairable_rows:,}"
            )
            return 1

        if not args.apply:
            print("\nDry run — nothing written. Re-run with --apply to write.")
            return 0

        written = 0
        with conn.cursor() as cur:
            for r in repairable:
                cur.execute(
                    _APPLY_SQL,
                    {
                        "round_id": r[5],
                        "session_date": r[0],
                        "map_name": r[1],
                        "round_number": r[2],
                        "round_start_unix": r[3],
                    },
                )
                written += cur.rowcount
        conn.commit()
        print(f"\nWrote round_id on {written:,} rows across {len(repairable)} rounds.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
