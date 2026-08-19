#!/usr/bin/env python3
"""repair_playtime_against_capture.py — reconcile stored playtime with the original capture.

`parse_regular_stats_file` gives every player of a round the ROUND's duration
and only then overrides it with that player's own TAB playtime field. That
override line landed on 2026-02-21 (commit 64d6f570); every round imported
before it kept the round-level number, which took one of two shapes:

  * 9-field header -> the raw MILLISECOND measurement (trap_Milliseconds), so
    time_played_seconds came out ~1000x too large (599327 for a 10-minute
    round). PR #770 fixed the ms reading itself.
  * 8-field header -> the stopwatch clock, i.e. the full timelimit (720s for a
    12:00 map) even though the round ended earlier.

Both shapes drag two derived columns with them:

    time_played_minutes = tps / 60
    dpm = damage_given / minutes        (0.3 instead of 300 in the ms case)

RCA 2026-08-19: the class is CLOSED — every round captured after the override
landed matches its capture file exactly (475 verified). What remains is
historical residue, and production and dev hold identical rows for it.

The repair does NOT guess. For a round-1/round-2 row it re-parses the ORIGINAL
capture with the production parser and takes that player's
`time_played_seconds`; a row is only rewritten when it disagrees with the
capture by more than --tolerance seconds. For a round-0 match-aggregate row it
uses the invariant every healthy R0 row satisfies: R0 = R1 + R2 per player.

ONLY these three columns are written:
    time_played_seconds, time_played_minutes, dpm
Identity, kills, damage, xp and everything else are never touched — in
particular the separate R0 xp divergence (a known, unrelated R0-aggregate
issue) is deliberately left alone.

    python scripts/repair_playtime_against_capture.py            # dry-run (default)
    python scripts/repair_playtime_against_capture.py --apply    # write

Every run writes two artifacts to --artifact-dir: a backup of the pre-repair
rows as INSERT statements, and a portable repair .sql with literal values so
the identical fix can be replayed on a host that does not hold the capture
files (production keeps a smaller local_stats corpus than dev).

DB connection comes from POSTGRES_* env vars (same names as the bot/.env).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import glob
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bot.community_stats_parser import (  # noqa: E402 (needs the sys.path bootstrap above)
    C0RNP0RN3StatsParser,
)

# Same threshold normalize_header_playtime() uses to tell ms from seconds: no
# real round lasts 10 000 s, and every real round lasts more than 10 s
# (= 10 000 ms). A repaired value above it would mean the capture itself is
# corrupt, so it is refused rather than written.
MS_THRESHOLD = 10_000

# The three columns this bug corrupts, and nothing else.
REPAIRED_COLUMNS = ("time_played_seconds", "time_played_minutes", "dpm")

# Rounding slack, in seconds, between the stored row and the capture. The
# parser stores whole seconds from a one-decimal minute field, so ±5s is
# arithmetic noise; the residue this heals sits 12-138s out.
DEFAULT_TOLERANCE = 5


def _sql_literal(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(round(v, 6) if isinstance(v, float) else v)
    return "'" + str(v).replace("'", "''") + "'"


def _connect(readonly: bool):
    import psycopg2

    required = ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DATABASE",
                "POSTGRES_USER", "POSTGRES_PASSWORD")
    missing = [n for n in required if not os.getenv(n)]
    if missing:
        raise SystemExit(f"Missing database env vars: {', '.join(missing)}")
    conn = psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        dbname=os.environ["POSTGRES_DATABASE"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    conn.set_session(readonly=readonly, autocommit=False)
    return conn


def derive_minutes_and_dpm(seconds: int, damage_given: int) -> tuple[float, float]:
    """minutes = s/60 (stored rounded, as the parser stores it), dpm = damage
    per minute computed from the UNROUNDED seconds — rounding the denominator
    first would shift dpm by up to 0.1 on rounds whose minute value does not
    terminate (e.g. the 1013 s aggregates)."""
    minutes = round(seconds / 60.0, 2)
    dpm = round(damage_given / (seconds / 60.0), 1) if seconds > 0 else 0.0
    return minutes, dpm


def capture_candidates(stats_dir: Path, round_row: dict) -> list[Path]:
    """Capture files that could belong to a round, best first.

    A capture is named `<date>-<time-of-day>-<map>-round-<n>.txt`, and the
    importer stamps the round with exactly that date, time and map — so the
    name is fully determined. The `-endstats` twin carries the same TAB player
    lines and stands in when the plain file is gone. The match_id glob is a
    last resort for rows whose round_time drifted from the file name.
    """
    date = round_row["round_date"]
    time_of_day = str(round_row["round_time"] or "").zfill(6)
    stem = f"{date}-{time_of_day}-{round_row['map_name']}-round-{round_row['round_number']}"
    ordered = [stats_dir / f"{stem}.txt", stats_dir / f"{stem}-endstats.txt"]
    found = [p for p in ordered if p.exists()]
    if found:
        return found
    pattern = f"{round_row['match_id']}-*-round-{round_row['round_number']}*.txt"
    return sorted(Path(c) for c in glob.glob(str(stats_dir / pattern)))


def truth_from_capture(paths: list[Path]) -> tuple[dict[str, int], Path | None]:
    """player_guid -> measured seconds, straight from the original capture."""
    parser = C0RNP0RN3StatsParser()
    for path in paths:
        try:
            parsed = parser.parse_stats_file(str(path))
        except Exception:  # a corrupt capture is "unknown", never a repair basis
            logging.warning("unreadable capture %s — skipped as a repair basis", path)
            continue
        truth = {
            p["guid"]: int(p["time_played_seconds"])
            for p in (parsed or {}).get("players", [])
            if p.get("guid") and p.get("time_played_seconds")
        }
        if truth:
            return truth, path
    return {}, None


def find_rounds(cur, since: str) -> list[dict]:
    """Rounds carrying the clock-fallback SIGNATURE, from `since` onwards.

    Reconciling every round against its capture is NOT safe: an orphan R2's
    capture holds raw cumulative values, a bot round's TAB field holds 29
    minutes of warmup, and the 2026-02-06 R2s were already healed by an
    earlier backfill against `time_limit`. Rewriting those from the capture
    would undo decisions someone already made (measured on dev 2026-08-19:
    the blanket form proposed 232 rows across 40 rounds, most of them wrong).

    The signature of THIS bug is exact and narrow: the stored playtime is
    literally the round's own stopwatch clock — the value the pre-2026-02-21
    parser assigned when it had no per-player TAB field to override it — and
    it is identical for every player of the round.
    """
    cur.execute(  # nosemgrep: fixed column list, %s params
        """
        SELECT r.id, r.match_id, r.round_number, r.map_name,
               r.round_date::date::text, r.round_time
        FROM rounds r
        WHERE r.round_number IN (1, 2) AND r.round_date >= %s
          AND r.round_status = 'completed' AND r.is_valid = TRUE
          AND r.actual_time ~ '^[0-9]+:[0-9]{2}$'
          AND EXISTS (
              SELECT 1 FROM player_comprehensive_stats p
              WHERE p.round_id = r.id
                AND p.time_played_seconds = split_part(r.actual_time, ':', 1)::int * 60
                                          + split_part(r.actual_time, ':', 2)::int
          )
        ORDER BY r.id
        """,
        (since,),
    )
    cols = ("round_id", "match_id", "round_number", "map_name", "round_date", "round_time")
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def clock_seconds(cur, round_id: int) -> int | None:
    """The round's own stopwatch clock (`actual_time`) in seconds — the value
    the pre-fix parser handed to every player. NOT a duration: see
    shared/round_time and RCA 2026-08-18."""
    cur.execute(  # nosemgrep: fixed column list, %s params
        "SELECT CASE WHEN actual_time ~ '^[0-9]+:[0-9]{2}$' "
        "THEN split_part(actual_time, ':', 1)::int * 60 "
        "   + split_part(actual_time, ':', 2)::int END "
        "FROM rounds WHERE id = %s",
        (round_id,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def rows_of_round(cur, round_id: int) -> list[dict]:
    cur.execute(  # nosemgrep: fixed column list, %s params
        "SELECT player_guid, player_name, time_played_seconds, time_played_minutes, "
        "dpm, damage_given FROM player_comprehensive_stats WHERE round_id = %s "
        "ORDER BY player_guid",
        (round_id,),
    )
    cols = ("player_guid", "player_name", "tps", "tpm", "dpm", "damage_given")
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def r0_round_for_match(cur, r2_round_id: int) -> int | None:
    """The R0 match-aggregate round that belongs to an R2 round.

    An R0 round does NOT share its siblings' match_id (it carries the R2
    capture's own timestamp, sometimes with the file-name suffix attached), so
    the link runs through the identity the importer does preserve: same date,
    same time-of-day, same map. Verified on production 2026-08-19: 519 of 532
    live R0 rounds resolve to exactly one R2 and none to more than one.
    """
    cur.execute(  # nosemgrep: fixed column list, %s params
        """
        SELECT r0.id
        FROM rounds r2
        JOIN rounds r0 ON r0.round_number = 0
             AND r0.round_date = r2.round_date
             AND r0.round_time = r2.round_time
             AND r0.map_name = r2.map_name
        WHERE r2.id = %s AND r2.round_number = 2
        """,
        (r2_round_id,),
    )
    hits = cur.fetchall()
    return hits[0][0] if len(hits) == 1 else None


def sibling_seconds(cur, match_id: str, guid: str, repaired: dict) -> int | None:
    """Sum of a player's R1 and R2 playtime for a match, honouring repairs made
    earlier in this same run so a dry-run and an --apply run agree."""
    cur.execute(  # nosemgrep: fixed column list, %s params
        """
        SELECT p.round_id, p.time_played_seconds
        FROM player_comprehensive_stats p
        JOIN rounds r ON r.id = p.round_id
        WHERE r.match_id = %s AND p.player_guid = %s AND p.round_number IN (1, 2)
        """,
        (match_id, guid),
    )
    parts = cur.fetchall()
    if not parts or len(parts) > 2:
        return None  # more than one R1/R2 pair under this match_id — refuse to sum
    total = 0
    for round_id, seconds in parts:
        seconds = repaired.get((round_id, guid), seconds)
        if seconds is None or seconds <= 0 or seconds > MS_THRESHOLD:
            return None  # a component is still unknown — refuse to guess
        total += int(seconds)
    return total or None


class Repair:
    """One row's before/after, and the SQL both ways."""

    def __init__(self, round_id: int, row: dict, new_seconds: int, basis: str):
        self.round_id = round_id
        self.guid = row["player_guid"]
        self.name = row["player_name"]
        self.old = (row["tps"], row["tpm"], row["dpm"])
        self.new = (new_seconds, *derive_minutes_and_dpm(new_seconds, row["damage_given"]))
        self.basis = basis

    def _update(self, values) -> str:
        seconds, minutes, dpm = values
        return (
            "UPDATE player_comprehensive_stats SET "
            f"time_played_seconds = {_sql_literal(seconds)}, "
            f"time_played_minutes = {_sql_literal(minutes)}, "
            f"dpm = {_sql_literal(dpm)} "
            f"WHERE round_id = {self.round_id} "
            f"AND player_guid = {_sql_literal(self.guid)};"
        )

    def backup_sql(self) -> str:
        return self._update(self.old)

    def repair_sql(self) -> str:
        return self._update(self.new)

    def line(self) -> str:
        return (f"    {self.name:<12} tps {self.old[0]:>7} -> {self.new[0]:<6}"
                f" tpm {self.old[1]:>9.2f} -> {self.new[1]:<7.2f}"
                f" dpm {self.old[2]:>8.3f} -> {self.new[2]:<7.1f} [{self.basis}]")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="write the repair (default: dry-run, no writes)")
    ap.add_argument("--since", default="2026-01-01",
                    help="earliest round_date to reconcile (default: the live-capture cutover)")
    ap.add_argument("--tolerance", type=int, default=DEFAULT_TOLERANCE,
                    help=f"seconds of slack before a row counts as wrong (default: {DEFAULT_TOLERANCE})")
    ap.add_argument("--with-r0", action="store_true",
                    help="also rewrite the R0 match aggregates of the repaired matches to the "
                         "R1+R2 sum. OFF by default: an R0 row that holds one round's value "
                         "instead of the sum is the separate, DB-wide R0-aggregate issue "
                         "(391 live rows on prod 2026-08-19), not this bug — healing it here "
                         "would move far more than the clock-fallback residue.")
    ap.add_argument("--stats-dir", default=str(_REPO_ROOT / "local_stats"),
                    help="directory holding the original stats captures")
    ap.add_argument("--artifact-dir", default=str(_REPO_ROOT / "playtime_repair_artifacts"),
                    help="where to write the backup + portable repair SQL")
    args = ap.parse_args()

    stats_dir = Path(args.stats_dir)
    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005 artifact naming only

    conn = _connect(readonly=not args.apply)
    repairs: list[Repair] = []
    repaired: dict[tuple[int, str], int] = {}
    seen = matched = no_capture = 0
    touched_r2: list[tuple[int, str]] = []  # (r2_round_id, match_id)

    try:
        with conn.cursor() as cur:
            # ── pass 1: R1/R2 rows against their capture ──────────────────
            for rnd in find_rounds(cur, args.since):
                seen += 1
                truth, path = truth_from_capture(capture_candidates(stats_dir, rnd))
                if not truth:
                    no_capture += 1
                    continue
                matched += 1
                round_repairs = []
                clock = clock_seconds(cur, rnd["round_id"])
                for row in rows_of_round(cur, rnd["round_id"]):
                    src = truth.get(row["player_guid"])
                    if src is None or src <= 0 or src > MS_THRESHOLD:
                        continue
                    if row["tps"] != clock:
                        continue  # not the fallback signature — leave it alone
                    if src >= row["tps"] or row["tps"] - src <= args.tolerance:
                        continue  # the clock can only OVERstate; anything else is another bug
                    round_repairs.append(Repair(rnd["round_id"], row, src, path.name[:24]))
                if not round_repairs:
                    continue
                print(f"  round {rnd['round_id']} ({rnd['round_date']} {rnd['map_name']} "
                      f"R{rnd['round_number']}) <- {path.name}")
                for rep in round_repairs:
                    print(rep.line())
                    repaired[(rep.round_id, rep.guid)] = rep.new[0]
                repairs.extend(round_repairs)
                if rnd["round_number"] == 2:
                    touched_r2.append((rnd["round_id"], rnd["match_id"]))
                else:
                    cur.execute(  # nosemgrep: fixed column list, %s params
                        "SELECT id FROM rounds WHERE match_id = %s AND round_number = 2",
                        (rnd["match_id"],),
                    )
                    for (r2_id,) in cur.fetchall():
                        touched_r2.append((r2_id, rnd["match_id"]))

            # ── pass 2 (opt-in): R0 aggregates of the matches pass 1 touched ──
            for r2_id, match_id in (dict.fromkeys(touched_r2) if args.with_r0 else {}):
                r0_id = r0_round_for_match(cur, r2_id)
                if r0_id is None:
                    print(f"  match {match_id}: no unique R0 aggregate — left alone")
                    continue
                r0_repairs = []
                for row in rows_of_round(cur, r0_id):
                    total = sibling_seconds(cur, match_id, row["player_guid"], repaired)
                    if total is None or abs(row["tps"] - total) <= args.tolerance:
                        continue
                    r0_repairs.append(Repair(r0_id, row, total, "R1+R2 sum"))
                if not r0_repairs:
                    continue
                print(f"  round {r0_id} (R0 aggregate of {match_id})")
                for rep in r0_repairs:
                    print(rep.line())
                repairs.extend(r0_repairs)

            print(f"\nRounds seen: {seen}   with a capture: {matched}   "
                  f"without: {no_capture}")
            print(f"Rows to repair: {len(repairs)} in "
                  f"{len({r.round_id for r in repairs})} rounds")

            if args.apply:
                for rep in repairs:
                    seconds, minutes, dpm = rep.new
                    cur.execute(  # nosemgrep: fixed column list, %s params
                        "UPDATE player_comprehensive_stats "
                        "SET time_played_seconds = %s, time_played_minutes = %s, dpm = %s "
                        "WHERE round_id = %s AND player_guid = %s",
                        (seconds, minutes, dpm, rep.round_id, rep.guid),
                    )
                conn.commit()
    finally:
        conn.close()

    backup_path = artifact_dir / f"backup-{stamp}.sql"
    repair_path = artifact_dir / f"repair-{stamp}.sql"
    backup_path.write_text("\n".join(r.backup_sql() for r in repairs) + "\n", encoding="utf-8")
    repair_path.write_text("\n".join(r.repair_sql() for r in repairs) + "\n", encoding="utf-8")
    print(f"Backup of pre-repair rows: {backup_path}")
    print(f"Portable repair SQL:       {repair_path}")
    if not args.apply:
        print("\nDRY-RUN — nothing was written. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
