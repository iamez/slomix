#!/usr/bin/env python3
"""Fill time_played_percent (TAB[8], engine alive%) where the import path left
a zero, by re-parsing the archived stats file for that round.

Why the column is empty
-----------------------
`postgresql_database_manager`'s INSERT never listed the column, so every row
the live path wrote took the schema DEFAULT 0. From the 2026-03-24 session
onward that is 100% of rows. The non-zero values in history came from a
one-off backfill, not from the import.

The consequence is not the column. `sessions_router` computes `survival_rate`
engine-first from this field and falls back to dead-time when it is missing,
so `survivability`, `consistency`, `aggression`, `discipline_score` and
`alive_pct` have all silently run on the fallback. And `alive_pct_drift` --
the check that compares the two sources -- can only fire when both exist, so
the guard that would have reported this was disabled by the omission itself.

Why not tools/slomix_backfill.py time-played-percent
----------------------------------------------------
That subcommand exists and is what produced the historical values, but it is
not safe to re-run against a populated database:

  * its UPDATE has no `WHERE time_played_percent = 0` gate, so it rewrites
    every matched row -- 13,731 rows on this database, including the 8,800
    that already hold good values;
  * its R2 differential is a second bulk UPDATE that is *skipped entirely in
    dry-run*, so the most dangerous part of the run cannot be previewed;
  * there is no transaction, so an interruption between the two phases leaves
    R2 rows holding the raw CUMULATIVE percentage -- silently inflated;
  * there is no backup.

This script writes only zeros, previews everything it would do, writes both a
backup and a portable repair artifact before touching anything, and runs in
one transaction.

R2 is cumulative
----------------
TAB[8] in an R2 file covers R1+R2. We do not redo that arithmetic here:
`parse_stats_file` dispatches R2 files to `parse_round_2_with_differential`,
which is the same code the importer uses. Rounds whose R1 file cannot be
found come back flagged `is_orphan_r2` -- those carry raw cumulative values
and are skipped, never written.

Usage
-----
    python scripts/backfill_time_played_percent.py                # preview
    python scripts/backfill_time_played_percent.py --apply        # write
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Only this column is ever written. Pinned by the unit test so a future edit
# cannot quietly widen the blast radius of a data repair.
REPAIRED_COLUMNS = ("time_played_percent",)

# An alive share cannot exceed the round. 0.5pp of slack absorbs rounding in
# the R2 differential; anything past that is reported, never written.
IMPLAUSIBLE_ABOVE = 100.5

# Rows the import path never filled. `time_played_seconds > 0` keeps out rows
# with no playtime at all, where a percentage would be meaningless.
# R0 rows are excluded: 6,773 of them also hold zero, nothing reads them
# (docs/CLAUDE.md), and writing there would lend them the look of a real
# source.
TARGET_SQL = """
    SELECT p.id, r.id AS round_id, r.round_date, r.round_time, r.map_name,
           r.round_number, p.player_guid, p.player_name, p.time_played_percent
    FROM player_comprehensive_stats p
    JOIN rounds r ON r.id = p.round_id
    WHERE p.time_played_percent = 0
      AND p.time_played_seconds > 0
      AND r.round_number IN (1, 2)
      AND r.is_valid IS DISTINCT FROM FALSE
      AND COALESCE(r.round_status, '') NOT IN ('orphan_r2', 'cancelled')
    ORDER BY r.round_date, r.round_time, p.player_guid
"""


def _sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def _connect(readonly: bool):
    import psycopg2

    required = ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DATABASE",
                "POSTGRES_USER", "POSTGRES_PASSWORD")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise SystemExit(f"Missing database env vars: {', '.join(missing)}")
    conn = psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        dbname=os.environ["POSTGRES_DATABASE"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    # A preview must not be able to write even by mistake, so the guarantee is
    # the session itself rather than a branch we could forget to take.
    conn.set_session(readonly=readonly, autocommit=False)
    return conn


def _write_artifact(path: Path, statements: list[str]) -> Path:
    """Write and fsync. The backup is the only way back from an --apply run,
    so 'the OS will get to it eventually' is not good enough."""
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(statements) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return path


def stats_file_for(stats_dir: Path, round_date: str, round_time: str,
                   map_name: str, round_number: int) -> Path | None:
    """`rounds.round_date` + `round_time` reproduce the capture filename stamp
    exactly (verified against 2026-03-29 133257 -> sw_goldrush_te round 1)."""
    stem = f"{round_date}-{round_time}-{map_name}-round-{round_number}"
    candidate = stats_dir / f"{stem}.txt"
    return candidate if candidate.exists() else None


def parsed_percentages(path: Path) -> tuple[str, dict[str, float]]:
    """Return (reason, GUID -> time_played_percent), using the importer's parser.

    Three outcomes, kept apart on purpose. Collapsing "orphan R2" and "could
    not parse" into a single None would report every parse failure as an
    orphan and hide it in a line of the preview that reads as expected --
    the same absent-vs-empty conflation this whole repair exists to undo.

      "ok"        -- percentages usable
      "orphan_r2" -- R2 whose R1 partner is missing. The parser flags it, and
                     its percentages are raw cumulative R1+R2, which would be
                     written as if they described R2 alone.
      "unparsed"  -- the file did not yield players at all. Not expected; if
                     the count is non-zero, something is wrong upstream.
    """
    from bot.community_stats_parser import C0RNP0RN3StatsParser

    result = C0RNP0RN3StatsParser().parse_stats_file(str(path))
    if not result or not result.get("players"):
        return "unparsed", {}
    if result.get("is_orphan_r2"):
        return "orphan_r2", {}

    out: dict[str, float] = {}
    for player in result["players"]:
        guid = (player.get("guid") or "").strip().upper()
        percent = (player.get("objective_stats") or {}).get("time_played_percent")
        if guid and percent:
            out[guid] = float(percent)
    return "ok", out


def build_artifacts(updates, stamp: str) -> tuple[list[str], list[str]]:
    """Generate the rollback and repair SQL.

    Both sides are guarded on the value, not just the id. The repair only
    fires while the row is still zero, and the rollback only reverts while the
    row still holds what this run wrote -- an unconditional rollback, run
    later, would clobber a legitimate value back to zero.
    """
    backup = [f"-- rollback for backfill_time_played_percent {stamp}", "BEGIN;"]
    repair = [f"-- backfill_time_played_percent {stamp}", "BEGIN;"]
    for row_id, percent, *_ in updates:
        written = _sql_literal(round(percent, 1))
        backup.append(
            "UPDATE player_comprehensive_stats SET time_played_percent = 0 "
            f"WHERE id = {row_id} AND time_played_percent = {written};")
        repair.append(
            "UPDATE player_comprehensive_stats SET time_played_percent = "
            f"{written} WHERE id = {row_id} AND time_played_percent = 0;")
    backup.append("COMMIT;")
    repair.append("COMMIT;")
    return backup, repair


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true",
                        help="write the changes (default: preview only)")
    parser.add_argument("--stats-dir", default="local_stats",
                        help="directory holding the archived capture files")
    parser.add_argument("--artifact-dir", default="tpp_backfill_artifacts",
                        help="where backup-<stamp>.sql and repair-<stamp>.sql go")
    parser.add_argument("--limit", type=int, default=0,
                        help="stop after N rows (for a quick look)")
    args = parser.parse_args()

    stats_dir = Path(args.stats_dir)
    if not stats_dir.is_dir():
        raise SystemExit(f"stats dir not found: {stats_dir}")

    # Fail on the artifact directory BEFORE opening a writable transaction --
    # a permissions problem must stop the run, not surface after the write.
    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    conn = _connect(readonly=not args.apply)
    cursor = conn.cursor()
    cursor.execute(TARGET_SQL)
    rows = cursor.fetchall()

    file_cache: dict[Path, tuple[str, dict[str, float]]] = {}
    updates: list[tuple[int, float, str, str, str]] = []
    implausible: list[tuple[int, float, str, str, str]] = []
    missing_file = missing_player = orphan_r2 = unparsed = 0
    rounds_seen: set[int] = set()

    for (row_id, round_id, round_date, round_time, map_name, round_number,
         guid, name, _current) in rows:
        if args.limit and len(updates) >= args.limit:
            break
        path = stats_file_for(stats_dir, round_date, round_time, map_name, round_number)
        if path is None:
            missing_file += 1
            continue
        if path not in file_cache:
            file_cache[path] = parsed_percentages(path)
        reason, percentages = file_cache[path]
        if reason == "orphan_r2":
            orphan_r2 += 1
            continue
        if reason == "unparsed":
            unparsed += 1
            continue
        percent = percentages.get((guid or "").strip().upper())
        if not percent:
            missing_player += 1
            continue
        if percent > IMPLAUSIBLE_ABOVE:
            # An alive share above 100% is not a value this column can carry.
            # Two rows out of 4,668 land at 101.2 -- rounding in the R2
            # differential, not corruption. They are left alone rather than
            # clamped: a clamped 100.0 would be indistinguishable from a
            # measured 100.0, and leaving the zero keeps them on the same
            # fallback they already use.
            implausible.append((row_id, percent, name, round_date, map_name))
            continue
        updates.append((row_id, percent, name, round_date, map_name))
        rounds_seen.add(round_id)

    print(f"candidate rows      : {len(rows)}")
    print(f"resolvable          : {len(updates)}  in {len(rounds_seen)} rounds")
    print(f"capture file missing: {missing_file}")
    print(f"orphan R2 (skipped) : {orphan_r2}")
    print(f"unparsed (skipped)  : {unparsed}")
    print(f"player not in file  : {missing_player}")
    if implausible:
        print(f"above {IMPLAUSIBLE_ABOVE}% (skipped): {len(implausible)}")
        for row_id, percent, name, round_date, map_name in implausible:
            print(f"  id={row_id} {round_date} {map_name} {name} -> {percent:.1f}")

    if updates:
        values = sorted(percent for _, percent, _, _, _ in updates)
        middle = values[len(values) // 2]
        print(f"percent to be written: min={values[0]:.1f} "
              f"median={middle:.1f} max={values[-1]:.1f}")
        print("\nfirst 5:")
        for row_id, percent, name, round_date, map_name in updates[:5]:
            print(f"  id={row_id} {round_date} {map_name:<18} "
                  f"{name:<14} 0.0 -> {percent:.1f}")

    if not updates:
        print("\nnothing to do")
        conn.rollback()
        conn.close()
        return 0

    backup, repair = build_artifacts(updates, stamp)

    if not args.apply:
        print(f"\npreview only -- nothing written. {len(updates)} rows would change.")
        print("re-run with --apply to write.")
        conn.rollback()
        conn.close()
        return 0

    # Artifacts land before the first UPDATE, never after.
    backup_path = _write_artifact(artifact_dir / f"backup-{stamp}.sql", backup)
    repair_path = _write_artifact(artifact_dir / f"repair-{stamp}.sql", repair)
    print(f"\nbackup: {backup_path}\nrepair: {repair_path}")

    changed = 0
    for row_id, percent, _, _, _ in updates:
        # Guarded: a row someone else filled in the meantime is left alone
        # rather than overwritten.
        cursor.execute(
            "UPDATE player_comprehensive_stats SET time_played_percent = %s "
            "WHERE id = %s AND time_played_percent = 0",
            (round(percent, 1), row_id))
        changed += cursor.rowcount

    if changed != len(updates):
        conn.rollback()
        print(f"ABORTED: expected to change {len(updates)} rows, changed {changed}. "
              "Nothing written.")
        conn.close()
        return 1

    conn.commit()
    print(f"committed: {changed} rows")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
