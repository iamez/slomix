#!/usr/bin/env python3
"""Link Lua captures that arrived after their round was already imported.

Sibling script, different job: ``repair_lua_round_links.py`` repairs rows whose
``round_id`` points at the WRONG round. This one only ever fills rows that have
NO ``round_id`` at all, and never rebinds an existing link.

`lua_round_teams` rows carry the engine's own round timing — the data behind
the "TIMING COMPARISON" report and behind `rounds.round_start_unix` itself.
A row that lands after its round was imported could never be linked:

* the exact path needs `rounds.round_start_unix`, which is only ever filled
  FROM a linked Lua row (circular, so it cannot bootstrap);
* the fuzzy path runs when a ROUND is imported and only looks at Lua rows
  already present, so a later arrival is never reconsidered.

Since 2026-08-11, when the v1.7.2 retry buffer started flushing captures in a
late burst, that became the normal case: 2026-08-12 stored 13 captures and
linked 0, and the timing comparison answers "NO LUA DATA" for those rounds.
The bot now links late arrivals as they land (`_link_late_lua_row`); this
repairs the ones already in the database.

Matching rule, identical to the bot's:
  same map, same round number, the round has no Lua row yet, and the round's
  filename timestamp is within 30 s of the capture's round end. A tie, or
  anything further away, is left alone — measured on the live database, every
  orphan whose nearest round was further than 30 s belonged to a neighbouring
  replay that already had its own Lua row.

Usage:
    python scripts/repair_lua_late_links.py
    python scripts/repair_lua_late_links.py --apply \
        --expect-rows 27 --expect-db localhost:5432/etlegacy
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
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

TOLERANCE_SECONDS = 30


def _connect():
    if _pg is None:
        raise SystemExit("psycopg2/psycopg not installed")
    kwargs = get_connection_kwargs()
    kwargs["dbname"] = kwargs.pop("database")
    return _pg.connect(**kwargs)


def _filename_unix(round_date, round_time) -> int | None:
    """Round filename timestamp -> epoch, local-naive like the bot's parser."""
    if not round_date or not round_time:
        return None
    clean = str(round_time).replace(":", "")
    if len(clean) != 6 or not clean.isdigit():
        return None
    try:
        return int(
            datetime.strptime(f"{str(round_date)[:10]} {clean}", "%Y-%m-%d %H%M%S").timestamp()  # noqa: DTZ007
        )
    except ValueError:
        return None


def collect(cur) -> tuple[list[tuple], dict[str, int]]:
    """Orphan Lua rows with exactly one round within tolerance."""
    cur.execute(
        """
        SELECT id, map_name, round_number,
               COALESCE(round_end_unix, round_start_unix) AS ts
        FROM lua_round_teams
        WHERE round_id IS NULL
          AND COALESCE(round_end_unix, round_start_unix) IS NOT NULL
        ORDER BY id
        """
    )
    orphans = cur.fetchall()

    # Candidate rounds: unclaimed only. Loaded once, matched in Python so the
    # timestamp convention cannot drift between SQL and the bot's parser.
    cur.execute(
        """
        SELECT r.id, r.map_name, r.round_number, r.round_date, r.round_time
        FROM rounds r
        WHERE r.round_number IN (1, 2)
          AND NOT EXISTS (SELECT 1 FROM lua_round_teams l WHERE l.round_id = r.id)
        """
    )
    rounds_by_key: dict[tuple, list[tuple[int, int]]] = {}
    for rid, map_name, round_number, round_date, round_time in cur.fetchall():
        stamp = _filename_unix(round_date, round_time)
        if stamp is None or not map_name:
            continue
        rounds_by_key.setdefault((map_name.strip().lower(), int(round_number)), []).append(
            (rid, stamp)
        )

    plan: list[tuple] = []
    stats = {"orphans": len(orphans), "no_candidate": 0, "tie": 0, "linkable": 0}
    for lua_id, map_name, round_number, ts in orphans:
        if not map_name or ts is None:
            stats["no_candidate"] += 1
            continue
        candidates = [
            (rid, abs(stamp - int(ts)))
            for rid, stamp in rounds_by_key.get((map_name.strip().lower(), int(round_number)), [])
            if abs(stamp - int(ts)) <= TOLERANCE_SECONDS
        ]
        if not candidates:
            stats["no_candidate"] += 1
            continue
        best = min(d for _, d in candidates)
        tied = [rid for rid, d in candidates if d == best]
        if len(tied) > 1:
            stats["tie"] += 1
            continue
        stats["linkable"] += 1
        plan.append((lua_id, tied[0], best, map_name, int(round_number)))
    return plan, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    parser.add_argument("--expect-rows", type=int, help="row count the dry run reported")
    parser.add_argument("--expect-db", help="server as host:port/database")
    args = parser.parse_args()

    if args.apply and (args.expect_rows is None or not args.expect_db):
        parser.error("--apply requires --expect-rows and --expect-db")

    dsn = get_target_dsn_parts()
    target = f"{dsn['host']}:{dsn['port']}/{dsn['database']}"
    print(f"database: {target}")
    if args.expect_db and args.expect_db != target:
        print(f"REFUSED: --expect-db {args.expect_db} != {target}")
        return 2

    conn = _connect()
    try:
        with conn.cursor() as cur:
            plan, stats = collect(cur)

            print(
                f"orphan Lua rows: {stats['orphans']} | "
                f"linkable: {stats['linkable']} | "
                f"no round within {TOLERANCE_SECONDS}s: {stats['no_candidate']} | "
                f"ambiguous ties: {stats['tie']}"
            )
            for lua_id, round_id, distance, map_name, round_number in plan[:20]:
                print(f"  lua {lua_id:>5} -> round {round_id:<6} {map_name} R{round_number} ({distance}s)")
            if len(plan) > 20:
                print(f"  … {len(plan) - 20} more")

            if not args.apply:
                print("\nDry run — nothing written. Re-run with --apply to write.")
                return 0

            if args.expect_rows != len(plan):
                print(f"REFUSED: --expect-rows {args.expect_rows} != {len(plan)} found now")
                return 2

            for lua_id, round_id, _distance, _map_name, _round_number in plan:
                # Re-assert both preconditions at write time: another process
                # may have linked either side since the plan was built.
                cur.execute(
                    """
                    UPDATE lua_round_teams SET round_id = %s
                    WHERE id = %s AND round_id IS NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM lua_round_teams o
                        WHERE o.round_id = %s AND o.id <> %s
                      )
                    """,
                    (round_id, lua_id, round_id, lua_id),
                )
        conn.commit()
        print(f"\nApplied: {len(plan)} Lua rows linked.")
        print(
            "rounds.round_start_unix / actual_duration_seconds follow on the bot's "
            "next timing reconcile pass."
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
