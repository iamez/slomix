#!/usr/bin/env python3
"""Backfill proximity_spawn_timing.killer_reinf for pre-F1-fix history.

The F1 Lua bug (fixed live 2026-06-10, PR #376) read non-existent offset
fields, so killer_reinf was computed with offset 0 for every historical row —
wrong by up to a full spawn wave (15 s on frostbite).

Recompute method (mirrors proximity_tracker.lua:1678 with the fixed offset):
  killer_reinf_ms = interval_K - ((offset_K + kill_time) % interval_K)
where (interval_K, offset_K) for the killer's team are derived per round from
VICTIM-side rows of that team — time_to_next_spawn there used the correct
offset all along, so:
  offset_T = (interval_T - time_to_next_spawn - kill_time) mod interval_T
is constant per round per team; the modal value (25 ms grid) absorbs the
0.1 s storage rounding. Same derivation as
website/backend/routers/proximity_competitive.py:_implied_offsets, validated
against the E2E audit clocks (docs/PROXIMITY_E2E_AUDIT_2026-06-10.md §3).

Rows whose killer team never appears as a victim in the round have no
derivable clock and are left untouched (reported as skipped).

DRY-RUN by default (prints what would change). Pass --apply to write.
Idempotent: recomputing already-correct rows yields the same value.

Usage:
    python3 -m scripts.backfill_killer_reinf                 # dry-run
    python3 -m scripts.backfill_killer_reinf --apply
    python3 -m scripts.backfill_killer_reinf --before 2026-06-10
"""
from __future__ import annotations

import argparse
import contextlib
import os
import sys
from collections import Counter, defaultdict

try:
    import psycopg2 as _pg
    from psycopg2.extras import execute_values
except ImportError:  # pragma: no cover - environment-dependent
    raise SystemExit(
        "This script needs a PostgreSQL driver: pip install psycopg2-binary"
    ) from None

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Last session date whose rows predate the live F1 fix (deployed 2026-06-10
# ~23:45 CEST, after that day's session).
DEFAULT_BEFORE = "2026-06-10"

OFFSET_GRID_MS = 25
# A 0.1 s storage step means recomputed values can legitimately differ from a
# correct stored value by one step; only count/update beyond that.
TOLERANCE_S = 0.05


def implied_team_clocks(rows: list[tuple]) -> dict[str, tuple[int, int]]:
    """Per-team (offset_ms, interval_ms) from victim-side rows of one round.

    rows: (victim_team, kill_time, enemy_spawn_interval, time_to_next_spawn)
    """
    candidates: dict[str, Counter] = defaultdict(Counter)
    intervals: dict[str, int] = {}
    for victim_team, kill_time, interval, ttn in rows:
        interval = int(interval or 0)
        if interval <= 0:
            continue
        offset = (interval - int(ttn or 0) - int(kill_time or 0)) % interval
        candidates[victim_team][round(offset / OFFSET_GRID_MS) * OFFSET_GRID_MS] += 1
        intervals[victim_team] = interval
    return {
        team: (counter.most_common(1)[0][0], intervals[team])
        for team, counter in candidates.items()
        if counter
    }


def recompute_killer_reinf(kill_time: int, offset_ms: int, interval_ms: int) -> float:
    """Mirror of proximity_tracker.lua:1678 (post-F1), in seconds (0.1 step)."""
    reinf_ms = interval_ms - ((offset_ms + int(kill_time)) % interval_ms)
    return round(reinf_ms / 1000, 1)


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
    ap.add_argument(
        "--before",
        default=DEFAULT_BEFORE,
        help=f"only rows with session_date <= this date (default {DEFAULT_BEFORE})",
    )
    args = ap.parse_args()

    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, session_date, map_name, round_number, round_start_unix,
               killer_team, victim_team, kill_time, enemy_spawn_interval,
               time_to_next_spawn, killer_reinf
        FROM proximity_spawn_timing
        WHERE session_date <= %s
        ORDER BY session_date, map_name, round_number, round_start_unix
        """,
        (args.before,),
    )
    rows = cur.fetchall()

    by_round: dict[tuple, list[tuple]] = defaultdict(list)
    for r in rows:
        by_round[(r[1], r[2], r[3], r[4])].append(r)

    updates: list[tuple[float, int]] = []  # (new_killer_reinf, id)
    skipped_no_clock = 0
    unchanged = 0
    diffs: list[float] = []
    for round_rows in by_round.values():
        clocks = implied_team_clocks(
            [(r[6], r[7], r[8], r[9]) for r in round_rows]
        )
        for r in round_rows:
            clock = clocks.get(r[5])
            if clock is None:
                skipped_no_clock += 1
                continue
            offset_ms, interval_ms = clock
            new = recompute_killer_reinf(r[7], offset_ms, interval_ms)
            old = float(r[10] or 0)
            if abs(new - old) <= TOLERANCE_S:
                unchanged += 1
                continue
            diffs.append(abs(new - old))
            updates.append((new, r[0]))

    print(f"Rows scanned        : {len(rows)} (session_date <= {args.before})")
    print(f"Rounds              : {len(by_round)}")
    print(f"Would update        : {len(updates)}")
    print(f"Already correct     : {unchanged}")
    print(f"Skipped (no clock)  : {skipped_no_clock}")
    if diffs:
        diffs.sort()
        mid = diffs[len(diffs) // 2]
        print(f"|Δ| median / max    : {mid:.1f}s / {diffs[-1]:.1f}s")

    if not updates:
        print("Nothing to do.")
        return 0
    if not args.apply:
        print("\nDRY-RUN — no changes written. Re-run with --apply to write.")
        return 0

    execute_values(
        cur,
        """
        UPDATE proximity_spawn_timing AS pst
        SET killer_reinf = v.new_reinf
        FROM (VALUES %s) AS v(new_reinf, id)
        WHERE pst.id = v.id
        """,
        updates,
        page_size=1000,
    )
    conn.commit()
    print(f"\nApplied: {cur.rowcount if cur.rowcount != -1 else len(updates)} rows updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
