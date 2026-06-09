#!/usr/bin/env python3
"""Backfill `rounds.match_id` using the deterministic stopwatch pairer.

## Problem

937 legacy rounds (2025-01-01 → 2026-02-21) carry a `match_id` that is the raw
stats *filename* (`YYYY-MM-DD-HHMMSS-map-round-N`). Because the filename embeds
the per-file timestamp, R1 and R2 of the same match got **different**
`match_id`s and never paired — inflating "lonely round" / incomplete-correlation
counts and feeding the round-linker orphan log spam. The live path
(`stats_import_mixin`) already writes the correct "R1 `date-HHMMSS`" key; this
script re-derives that key for the legacy rows via `bot.core.stopwatch_pairing`.

## Safety

* **DRY-RUN by default** — prints exactly what *would* change (counts, a sample
  before→after, lonely classification, and how many `lua_round_teams` /
  `round_correlations` rows reference the old ids). Nothing is written.
* `--apply` performs the UPDATE inside a single transaction. Take a DB backup
  first (the script prints the reminder and refuses `--apply` unless
  `--i-have-a-backup` is also passed).
* **Idempotent**: rounds whose current `match_id` already equals the derived
  key are skipped, so re-running is a no-op on already-correct data.

Usage:
    python -m scripts.backfill_match_id_stopwatch                 # dry-run
    python -m scripts.backfill_match_id_stopwatch --apply --i-have-a-backup
    python -m scripts.backfill_match_id_stopwatch --session 91    # scope to one
"""
from __future__ import annotations

import argparse
import os
import sys

import psycopg2

# Allow `python scripts/backfill_match_id_stopwatch.py` as well as `-m`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.core.stopwatch_pairing import RoundRec, pair_rounds  # noqa: E402


def _load_env() -> None:
    # dotenv is a convenience only — env vars may already be exported.
    import contextlib

    with contextlib.suppress(Exception):
        from dotenv import load_dotenv

        load_dotenv()


def _connect():
    _load_env()
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DATABASE", "etlegacy"),
        user=os.getenv("POSTGRES_USER", "etlegacy_user"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def _fetch_rounds(cur, session: int | None) -> tuple[list[RoundRec], dict[int, str]]:
    where = "WHERE round_number IN (1,2)"
    params: tuple = ()
    if session is not None:
        where += " AND gaming_session_id = %s"
        params = (session,)
    cur.execute(
        f"""
        SELECT id, gaming_session_id, map_name, round_number,
               round_start_unix, round_end_unix, round_date, round_time, match_id
        FROM rounds
        {where}
        """,
        params,
    )
    recs: list[RoundRec] = []
    current: dict[int, str] = {}
    for row in cur.fetchall():
        (rid, gsid, mapn, rn, su, eu, rdate, rtime, mid) = row
        recs.append(
            RoundRec(
                id=rid,
                gaming_session_id=gsid,
                map_name=mapn,
                round_number=rn,
                round_start_unix=int(su) if su is not None else None,
                round_end_unix=int(eu) if eu is not None else None,
                round_date=str(rdate) if rdate is not None else None,
                round_time=str(rtime) if rtime is not None else None,
            )
        )
        current[rid] = mid
    return recs, current


def _desired_map(result) -> dict[int, str]:
    """round_id -> desired match_id (each present round of each match)."""
    desired: dict[int, str] = {}
    for m in result.matches:
        if m.r1 is not None:
            desired[m.r1.id] = m.match_id
        if m.r2 is not None:
            desired[m.r2.id] = m.match_id
    return desired


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="actually write changes (else dry-run)")
    ap.add_argument("--i-have-a-backup", action="store_true", help="required with --apply")
    ap.add_argument("--session", type=int, default=None, help="limit to one gaming_session_id")
    ap.add_argument("--window-minutes", type=int, default=45)
    args = ap.parse_args()

    conn = _connect()
    conn.autocommit = False
    cur = conn.cursor()

    rounds, current = _fetch_rounds(cur, args.session)
    result = pair_rounds(rounds, window_minutes=args.window_minutes)
    desired = _desired_map(result)

    # Compute the change set: rounds whose match_id would change.
    changes: list[tuple[int, str, str]] = []  # (round_id, old, new)
    old_to_new: dict[str, str] = {}
    for rid, new_mid in desired.items():
        old_mid = current.get(rid)
        if old_mid != new_mid:
            changes.append((rid, old_mid, new_mid))
            if old_mid:
                old_to_new[old_mid] = new_mid

    summary = result.summary()
    print("=" * 64)
    print("STOPWATCH match_id BACKFILL — " + ("APPLY" if args.apply else "DRY-RUN"))
    print("=" * 64)
    print(f"Play-rounds scanned : {len([r for r in rounds if r.round_number in (1, 2)])}")
    print(f"Matches derived     : {summary['matches_total']}")
    print(f"  complete (R1+R2)  : {summary['complete']}")
    print(f"  abandoned_r1      : {summary['abandoned_r1']}  (R1 played, no R2 — map not finished)")
    print(f"  orphan_r2         : {summary['orphan_r2']}  (R2 with no R1 — lost/never-imported R1)")
    print(f"rounds whose match_id CHANGES: {len(changes)}")

    if changes:
        print("\nSample (old → new):")
        for rid, old, new in changes[:15]:
            print(f"  round {rid:>6}: {old}  →  {new}")

        # How many downstream rows reference the OLD ids (consistency check).
        old_ids = list(old_to_new.keys())
        # lua_round_teams is keyed by (match_id, round_number) so re-keying
        # R1 and R2 to a shared match_id cannot collide — safe to update.
        try:
            cur.execute(
                "SELECT COUNT(*) FROM lua_round_teams WHERE match_id = ANY(%s)", (old_ids,)
            )
            print(f"  lua_round_teams: {cur.fetchone()[0]} rows reference an old match_id "
                  "(safe to update — keyed by match_id+round_number)")
        except Exception as e:  # noqa: BLE001 — report-only, never fatal
            print(f"  lua_round_teams: could not check ({e})")
            conn.rollback()
        # round_correlations has NO unique(match_id): two legacy rows (one
        # R1-only, one R2-only) would collapse onto the same new match_id and
        # silently duplicate. It is a *derived* completeness ledger, so this
        # backfill deliberately LEAVES IT UNTOUCHED — regenerate it via
        # round_correlation_service after re-keying rounds, not by blind
        # re-keying here.
        try:
            cur.execute(
                "SELECT COUNT(*) FROM round_correlations WHERE match_id = ANY(%s)", (old_ids,)
            )
            print(f"  round_correlations: {cur.fetchone()[0]} legacy rows reference an old "
                  "match_id — LEFT UNTOUCHED (derived ledger; regenerate separately)")
        except Exception as e:  # noqa: BLE001 — report-only, never fatal
            print(f"  round_correlations: could not check ({e})")
            conn.rollback()

    if not args.apply:
        print("\nDRY-RUN — no changes written. Re-run with --apply --i-have-a-backup to commit.")
        cur.close()
        conn.close()
        return 0

    if not args.i_have_a_backup:
        print("\nREFUSING --apply without --i-have-a-backup.")
        print("Take a backup first, e.g.:")
        print("  pg_dump -h localhost -U etlegacy_user etlegacy | gzip > etlegacy_pre_matchid.sql.gz")
        cur.close()
        conn.close()
        return 2

    if not changes:
        print("\nNothing to change — already consistent. ✅")
        cur.close()
        conn.close()
        return 0

    # Apply inside one transaction.
    print(f"\nApplying {len(changes)} round match_id updates …")
    cur.executemany(
        "UPDATE rounds SET match_id = %s WHERE id = %s",
        [(new, rid) for rid, _old, new in changes],
    )
    # lua_round_teams is collision-safe (match_id + round_number); update it
    # so the lua↔rounds join stays consistent. round_correlations is left
    # untouched on purpose (see dry-run note) — regenerate it separately.
    lua_updated = 0
    for old, new in old_to_new.items():
        cur.execute(
            "UPDATE lua_round_teams SET match_id = %s WHERE match_id = %s", (new, old)
        )
        lua_updated += cur.rowcount
    conn.commit()
    print(f"✅ Committed. {len(changes)} rounds re-keyed, {lua_updated} lua_round_teams rows updated.")
    print("   round_correlations left untouched — regenerate via round_correlation_service.")
    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
