#!/usr/bin/env python3
"""Renormalize historical session_results scores to the BOX point scale.

Owner rule (2026-07-05): every map is worth 2 points — win 2-0, draw 1-1.
Rows saved before the scale switch carry 1-per-map totals (and the old time
fallback scored double fullholds 0-0), so summed displays like !h2h would mix
scales. The stored per-map results in `round_details` make the transform
EXACT per map:  (1,0)->(2,0)  (0,1)->(0,2)  (1,1)->(1,1)  (0,0)->(1,1).
Rows already on the BOX scale (any 2 present, or totals == 2*maps) are left
untouched, so the script is idempotent. winning_team never changes (the
transform is order-preserving).

DRY-RUN by default. Usage:
    python -m scripts.backfill_box_scale_session_results          # dry-run
    python -m scripts.backfill_box_scale_session_results --apply

Run scripts/db_backup.sh first. Needs psycopg2 (dev) — on prod run the
printed UPDATEs via psql, or install psycopg2-binary into a venv.
"""
from __future__ import annotations

import argparse
import json
import os

import psycopg2


def _transform(map_results: list[dict]) -> tuple[int, int, bool]:
    """Return (new_t1, new_t2, was_old_scale) from per-map point pairs.

    round_details rows come in two shapes: the with_teams path stores
    team_a_points/team_b_points (+ counted=False for roster-ambiguous maps
    that never entered the tally), the date-based path team1_points/
    team2_points. Uncounted maps stay uncounted.
    """
    new_t1 = new_t2 = 0
    saw_two = False
    for m in map_results:
        if m.get("counted") is False:
            continue
        if "team_a_points" in m or "team_b_points" in m:
            p1 = int(m.get("team_a_points", 0) or 0)
            p2 = int(m.get("team_b_points", 0) or 0)
        else:
            p1 = int(m.get("team1_points", 0) or 0)
            p2 = int(m.get("team2_points", 0) or 0)
        if p1 == 2 or p2 == 2:
            saw_two = True
            new_t1 += p1
            new_t2 += p2
        elif (p1, p2) == (1, 0):
            new_t1 += 2
        elif (p1, p2) == (0, 1):
            new_t2 += 2
        else:
            # (1,1) header-path draw or (0,0) old time-fallback draw -> 1-1
            new_t1 += 1
            new_t2 += 1
    return new_t1, new_t2, not saw_two


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write changes (else dry-run)")
    args = ap.parse_args()

    conn = psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PGPASSWORD", ""),
    )
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute(
        "SELECT id, session_date, team_1_score, team_2_score, round_details "
        "FROM session_results ORDER BY id"
    )
    rows = cur.fetchall()

    changes = []
    skipped_no_details = 0
    for rid, sdate, t1, t2, details in rows:
        try:
            maps = json.loads(details) if isinstance(details, str) else (details or [])
        except (TypeError, ValueError):
            maps = []
        if not maps:
            skipped_no_details += 1
            continue
        new_t1, new_t2, was_old = _transform(maps)
        if not was_old or (new_t1, new_t2) == (t1, t2):
            continue
        changes.append((rid, sdate, t1, t2, new_t1, new_t2))

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== BOX-scale session_results backfill — {mode} ===")
    print(f"rows={len(rows)} to_update={len(changes)} no_round_details={skipped_no_details}")
    for rid, sdate, t1, t2, n1, n2 in changes:
        print(f"  id={rid} {sdate}: {t1}-{t2} -> {n1}-{n2}")

    if not args.apply:
        print("\nDRY-RUN — nothing written. Run scripts/db_backup.sh, then --apply.")
        conn.close()
        return 0

    for rid, _sdate, _t1, _t2, n1, n2 in changes:
        cur.execute(
            "UPDATE session_results SET team_1_score = %s, team_2_score = %s WHERE id = %s",
            (n1, n2, rid),
        )
    conn.commit()
    print(f"\nCommitted {len(changes)} rows.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
