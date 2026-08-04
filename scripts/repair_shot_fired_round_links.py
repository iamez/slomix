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

Method: propagate a VERIFIED sibling link, never re-derive. For each orphan we
look for a sibling row in proximity_kill_outcome carrying the SAME four
identity columns (session_date, map_name, round_number, round_start_unix) and
a non-NULL round_id.

A sibling link is not trusted on its own. The relinker exists partly because
proximity rows can end up pointing at the WRONG round (proximity arrives before
stats, round_linker picks the nearest neighbour, the real round is created
later) — that is what its mismatch leg catches. Unanimous siblings can
therefore be unanimously stale, so every candidate is checked against the
rounds row it names: same map_name, round_number, round_start_unix and date.
This is the relinker's own mismatch criterion, applied before copying instead
of after.

Rounds with no linked sibling, with siblings disagreeing, or whose candidate
fails that check are left alone and reported — those need the round_linker,
not a copy.

Follows scripts/repair_lua_round_links.py: dry-run by default, --apply to
write, and the historical mutation deliberately lives here rather than in a
migration so a normal deploy cannot perform it unattended.

Usage:
    # 1. preview, and note the repairable row count it reports
    python scripts/repair_shot_fired_round_links.py

    # 2. write, restating that count and the target database
    python scripts/repair_shot_fired_round_links.py --apply \
        --expect-repairable-rows 57854 --expect-db etlegacy

--apply requires both expectations. A candidate set that shifted between
preview and apply (a session landed, someone else relinked) is no longer what
was reviewed, and the wrong database is the other way this goes badly.
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
       CASE WHEN s.distinct_round_ids = 1 AND r.id IS NOT NULL
            THEN s.round_id END AS resolved_round_id,
       COALESCE(s.distinct_round_ids, 0) AS distinct_round_ids,
       (s.round_id IS NOT NULL AND s.distinct_round_ids = 1
        AND r.id IS NULL) AS sibling_link_is_stale
FROM orphans o
LEFT JOIN siblings s USING (session_date, map_name, round_number, round_start_unix)
-- Verify the sibling's round_id actually names a round with this identity.
-- Unanimous siblings can be unanimously wrong: that is exactly the state the
-- relinker's mismatch leg is built to detect, so it must not be propagated.
--
-- round_start_unix is the load-bearing check and is compared exactly: it IS
-- the relinker's mismatch criterion (relinker_mixin compares
-- pko.round_start_unix != r.round_start_unix), and it is timezone- and
-- calendar-free.
--
-- Deliberately NOT comparing round_date. round_linker relaxes the date filter
-- on purpose (round_linker.py:196-199): a round starting 23:5x is stored with
-- the NEXT day's round_date while proximity recorded the previous one, so an
-- exact date match would report correctly-linked midnight rounds as stale.
-- round_start_unix already pins the round to the second, so the date adds no
-- safety — only false negatives.
--
-- map_name is compared case- and whitespace-insensitively for the same
-- reason: a difference there is a spelling difference, not a different round.
LEFT JOIN rounds r
       ON r.id = s.round_id
      AND s.distinct_round_ids = 1
      AND r.round_start_unix = o.round_start_unix
      AND r.round_number = o.round_number
      AND LOWER(TRIM(r.map_name)) = LOWER(TRIM(o.map_name))
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
    # get_connection_kwargs() speaks asyncpg/psycopg2 ("database"), but psycopg 3
    # only takes the libpq keyword and rejects the unexpected one, so the
    # fallback import path would fail on connect (Codex review on #599).
    # Translated unconditionally rather than sniffing the driver: psycopg2
    # accepts "dbname" too, and this is what repair_lua_round_links.py:67
    # already does.
    connection_kwargs = get_connection_kwargs()
    connection_kwargs["dbname"] = connection_kwargs.pop("database")
    return _pg.connect(**connection_kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    parser.add_argument(
        "--expect-repairable-rows",
        type=int,
        help="row count the dry run reported; REQUIRED with --apply",
    )
    parser.add_argument(
        "--expect-db",
        help="database name this must be run against; REQUIRED with --apply",
    )
    args = parser.parse_args()

    # --apply must restate what the dry run saw. A candidate set that shifted
    # between preview and apply (a session landed, someone else relinked) means
    # the operator is no longer approving what they reviewed, and the wrong
    # database is the other way this goes badly (Codex review on #599).
    if args.apply and (args.expect_repairable_rows is None or not args.expect_db):
        parser.error(
            "--apply requires --expect-repairable-rows and --expect-db "
            "(run without --apply first and pass back what it reports)"
        )

    target = get_target_dsn_parts()
    print(f"Target: {target['database']} @ {target['host']}:{target['port']}")

    if args.expect_db and args.expect_db != target["database"]:
        print(f"ABORT: --expect-db={args.expect_db!r} but target is {target['database']!r}")
        return 1

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
            print("\nLeft alone (needs the round_linker, not a copy):")
            for r in skipped:
                if r[7]:
                    why = "sibling link is stale — points at a round with a different identity"
                elif r[6] > 1:
                    why = "siblings disagree"
                else:
                    why = "no linked sibling"
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
