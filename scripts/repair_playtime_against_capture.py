#!/usr/bin/env python3
"""repair_ms_playtime_rows.py — heal rows whose playtime was stored in MILLISECONDS.

Header field 9 of a c0rnp0rn8 stats file is the measured playtime in
MILLISECONDS (trap_Milliseconds deltas minus pauses). Before PR #770 the
parser's `parse_regular_stats_file` path read it as SECONDS, so every player
row of such a round got `time_played_seconds` ~1000x too large, and the two
values derived from it went with it:

    time_played_minutes = tps / 60      -> ~1000x too large
    dpm = damage_given / minutes        -> ~1000x too small (0.3 instead of 300)

RCA 2026-08-19: on production this hit 52 rows in 8 rounds, all from the
2026-02-24 session (R1 rounds 9943/9946/9949/9952 plus their R0 match
aggregates 9945/9948/9951/9954). The dev database holds the correct values
for the same rows, and re-parsing the ORIGINAL stats file with today's parser
reproduces them exactly — two independent paths agreeing on the same numbers.

The repair does NOT guess. For a round-1/round-2 row it re-parses the original
stats file with the production parser and takes that player's
`time_played_seconds` (which comes from the per-player TAB field, not from the
millisecond header). For a round-0 match-aggregate row it uses the invariant
every healthy R0 row in the database satisfies: R0 = R1 + R2 per player.

ONLY these three columns are written:
    time_played_seconds, time_played_minutes, dpm
Identity, kills, damage, xp and everything else are never touched — in
particular the separate R0 xp divergence (a known, unrelated R0-aggregate
issue) is deliberately left alone.

    python scripts/repair_ms_playtime_rows.py            # dry-run (default)
    python scripts/repair_ms_playtime_rows.py --apply    # write

Every run writes two artifacts to --artifact-dir: a backup of the pre-repair
rows as INSERT statements, and a portable repair .sql with literal values so
the identical fix can be replayed on a host without the stats files.

DB connection comes from POSTGRES_* env vars (same names as the bot/.env).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import glob
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bot.community_stats_parser import (  # noqa: E402 (needs the sys.path bootstrap above)
    C0RNP0RN3StatsParser,
    normalize_header_playtime,
)

# Same threshold normalize_header_playtime() uses to tell ms from seconds: no
# real round lasts 10 000 s, and every real round lasts more than 10 s
# (= 10 000 ms), so a stored playtime above it is unambiguously milliseconds.
MS_THRESHOLD = 10_000

# The three columns the millisecond bug corrupts, and nothing else.
REPAIRED_COLUMNS = ("time_played_seconds", "time_played_minutes", "dpm")


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


def find_affected_rows(cur) -> list[dict]:
    """Every row whose stored playtime is unambiguously a millisecond value."""
    cur.execute(  # nosemgrep: fixed column list, literal threshold
        """
        SELECT p.round_id, p.player_guid, p.player_name, p.round_number,
               p.time_played_seconds, p.time_played_minutes, p.dpm,
               p.damage_given, r.match_id, r.map_name, r.round_date::date::text
        FROM player_comprehensive_stats p
        JOIN rounds r ON r.id = p.round_id
        WHERE p.time_played_seconds > %s
        ORDER BY p.round_id, p.player_guid
        """,
        (MS_THRESHOLD,),
    )
    cols = ("round_id", "player_guid", "player_name", "round_number", "tps",
            "tpm", "dpm", "damage_given", "match_id", "map_name", "round_date")
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def locate_stats_file(stats_dir: Path, row: dict) -> Path | None:
    """The original capture for a round. A round's match_id is its R1 file's
    timestamp prefix, so the name is fully determined except for the
    '-endstats' variant; both carry the same TAB player lines."""
    pattern = f"{row['match_id']}-*-round-{row['round_number']}*.txt"
    hits = sorted(Path(c) for c in glob.glob(str(stats_dir / pattern)))
    # Prefer the plain capture; the -endstats twin is the fallback.
    plain = [h for h in hits if not h.name.endswith("-endstats.txt")]
    return (plain or hits or [None])[0]


def truth_from_stats_file(path: Path) -> dict[str, int]:
    """player_guid -> measured seconds, straight from the original capture."""
    parser = C0RNP0RN3StatsParser()
    parsed = parser.parse_stats_file(str(path))
    if not parsed or not parsed.get("players"):
        return {}
    return {
        p["guid"]: int(p["time_played_seconds"])
        for p in parsed["players"]
        if p.get("guid") and p.get("time_played_seconds")
    }


def r0_sibling_rounds(cur, r0_round_id: int) -> list[int] | None:
    """The R1+R2 rounds an R0 match-aggregate row summarizes.

    An R0 round does NOT share its siblings' match_id (it carries the R2
    capture's own timestamp, sometimes with the file-name suffix attached),
    so the link runs through the identity the importer does preserve: an R0
    round is stamped with the same date, time-of-day and map as the R2 that
    closed the match. Verified on production 2026-08-19: 519 of 532 live R0
    rounds resolve to exactly one R2 and none to more than one; the 13
    without a match are left alone rather than guessed at.
    """
    cur.execute(  # nosemgrep: fixed column list, %s params
        """
        SELECT r2.id, r2.match_id
        FROM rounds r0
        JOIN rounds r2 ON r2.round_number = 2
             AND r2.round_date = r0.round_date
             AND r2.round_time = r0.round_time
             AND r2.map_name = r0.map_name
        WHERE r0.id = %s
        """,
        (r0_round_id,),
    )
    hits = cur.fetchall()
    if len(hits) != 1:
        return None
    r2_id, match_id = hits[0]
    cur.execute(  # nosemgrep: fixed column list, %s params
        "SELECT id FROM rounds WHERE match_id = %s AND round_number IN (1, 2)",
        (match_id,),
    )
    siblings = sorted({r2_id} | {row[0] for row in cur.fetchall()})
    return siblings or None


def r0_target_seconds(cur, r0_round_id: int, guid: str, repaired: dict) -> int | None:
    """R0 is the match aggregate: the sum of that player's R1 and R2 rows.
    Every healthy R0 row in the database satisfies this; the corrupted ones
    hold a single round's millisecond value instead. Rows repaired earlier in
    this same run count with their NEW value, so a dry-run and an --apply run
    produce identical numbers."""
    siblings = r0_sibling_rounds(cur, r0_round_id)
    if not siblings:
        return None
    total = 0
    for round_id in siblings:
        cur.execute(  # nosemgrep: fixed column list, %s params
            "SELECT time_played_seconds FROM player_comprehensive_stats "
            "WHERE round_id = %s AND player_guid = %s",
            (round_id, guid),
        )
        row = cur.fetchone()
        if row is None:
            continue  # player did not take part in that half
        seconds = repaired.get((round_id, guid), row[0])
        if seconds is None or seconds > MS_THRESHOLD:
            return None  # a component is still corrupt — refuse to guess
        total += int(seconds)
    return total or None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="write the repair (default: dry-run, no writes)")
    ap.add_argument("--stats-dir", default=str(_REPO_ROOT / "local_stats"),
                    help="directory holding the original stats captures")
    ap.add_argument("--artifact-dir", default=str(_REPO_ROOT / "ms_playtime_repair_artifacts"),
                    help="where to write the backup + portable repair SQL")
    args = ap.parse_args()

    stats_dir = Path(args.stats_dir)
    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005 artifact naming only

    conn = _connect(readonly=not args.apply)
    backup_lines: list[str] = []
    repair_lines: list[str] = []
    repaired: dict[tuple[int, str], int] = {}
    healed = skipped = 0

    try:
        with conn.cursor() as cur:
            rows = find_affected_rows(cur)
            if not rows:
                print("No millisecond playtime rows found — nothing to repair.")
                return 0

            print(f"Affected rows: {len(rows)} in "
                  f"{len({r['round_id'] for r in rows})} rounds\n")
            truth_cache: dict[int, dict[str, int]] = {}

            # Round 1/2 rows first: their repaired values feed the R0 sums.
            for row in sorted(rows, key=lambda r: (r["round_number"] == 0, r["round_id"])):
                key = (row["round_id"], row["player_guid"])
                if row["round_number"] in (1, 2):
                    if row["round_id"] not in truth_cache:
                        path = locate_stats_file(stats_dir, row)
                        if path is None:
                            print(f"  round {row['round_id']}: no stats file in "
                                  f"{stats_dir} — SKIPPED (cannot prove the truth)")
                            truth_cache[row["round_id"]] = {}
                        else:
                            truth_cache[row["round_id"]] = truth_from_stats_file(path)
                            print(f"  round {row['round_id']} ({row['map_name']}, "
                                  f"R{row['round_number']}) <- {path.name}  "
                                  f"header ms: {normalize_header_playtime(row['tps'])}s")
                    new_seconds = truth_cache[row["round_id"]].get(row["player_guid"])
                else:
                    new_seconds = r0_target_seconds(cur, row["round_id"],
                                                    row["player_guid"], repaired)

                if new_seconds is None or new_seconds <= 0 or new_seconds > MS_THRESHOLD:
                    print(f"    {row['player_name']:<12} SKIPPED (no provable value)")
                    skipped += 1
                    continue

                minutes, dpm = derive_minutes_and_dpm(new_seconds, row["damage_given"])
                print(f"    {row['player_name']:<12} tps {row['tps']:>7} -> {new_seconds:<6}"
                      f" tpm {row['tpm']:>9.2f} -> {minutes:<7.2f}"
                      f" dpm {row['dpm']:>8.3f} -> {dpm}")

                backup_lines.append(
                    "UPDATE player_comprehensive_stats SET "
                    f"time_played_seconds = {_sql_literal(row['tps'])}, "
                    f"time_played_minutes = {_sql_literal(row['tpm'])}, "
                    f"dpm = {_sql_literal(row['dpm'])} "
                    f"WHERE round_id = {row['round_id']} "
                    f"AND player_guid = {_sql_literal(row['player_guid'])};"
                )
                update = (
                    "UPDATE player_comprehensive_stats SET "
                    f"time_played_seconds = {_sql_literal(new_seconds)}, "
                    f"time_played_minutes = {_sql_literal(minutes)}, "
                    f"dpm = {_sql_literal(dpm)} "
                    f"WHERE round_id = {row['round_id']} "
                    f"AND player_guid = {_sql_literal(row['player_guid'])};"
                )
                repair_lines.append(update)
                repaired[key] = new_seconds
                healed += 1

                if args.apply:
                    cur.execute(  # nosemgrep: fixed column list, %s params
                        "UPDATE player_comprehensive_stats "
                        "SET time_played_seconds = %s, time_played_minutes = %s, dpm = %s "
                        "WHERE round_id = %s AND player_guid = %s",
                        (new_seconds, minutes, dpm, row["round_id"], row["player_guid"]),
                    )

        if args.apply:
            conn.commit()
    finally:
        conn.close()

    backup_path = artifact_dir / f"backup-{stamp}.sql"
    repair_path = artifact_dir / f"repair-{stamp}.sql"
    backup_path.write_text("\n".join(backup_lines) + "\n", encoding="utf-8")
    repair_path.write_text("\n".join(repair_lines) + "\n", encoding="utf-8")

    print(f"\nRows repaired: {healed}   skipped: {skipped}")
    print(f"Backup of pre-repair rows: {backup_path}")
    print(f"Portable repair SQL:       {repair_path}")
    if not args.apply:
        print("\nDRY-RUN — nothing was written. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
