#!/usr/bin/env python3
"""Rebuild pre-2026-03-24 time_dead_minutes from the engine's own alive%.

WHY
---
Until roughly 2026-03-20 the game server's `c0rnp0rn8.lua` re-added the whole
running limbo time to `death_time_total` on every 5-second tick without
resetting it, so a 20-second death was counted as 5+10+15+20. Measured against
the engine's alive% (`time_played_percent`, TAB[8], which the Lua computes from
`et.gentity_get` fields and NOT from that accumulator), the capture files of
that era are inflated by a factor of **2.17-2.24, uniformly** across R1, R2,
bulk-imported and live-captured rounds.

The stored rows are the capture-file value verbatim -- with ONE exception. The
2025-12-20 bulk import treated the R2 file's dead time as a match cumulative
and split it in proportion to playtime:

    stored_R2 = file_R2 x played_R2 / (played_R1 + played_R2)

measured at median 1.000 with 97.8% of rows within +-10% (n=2,625). That
halving nearly cancels the Lua's doubling, which is why those rows LOOK
correct in aggregate (median stored/reconstructed 1.058) while only 18.2% of
them land within +-10% of the truth and 35.5% sit below 0.9. They are not a
competing measurement; they are a doubly-derived number.

So every pre-fix row has one truth source and one correction:

    dead_minutes = time_played_seconds / 60 x (1 - time_played_percent / 100)
    dead_ratio   = 100 - time_played_percent

VALIDATION (measured 2026-09-02/03, three independent arbiters)
---------------------------------------------------------------
* Post-fix rows, where the Lua no longer inflates: reconstructed vs measured
  median **1.0000** (R1) / 0.9993 (R2), n=4,447, 95.7% within +-10%.
* `round_awards` -- written by endstats.lua, which keeps its OWN dead-time
  accumulator and flushes it once at intermission, so it does not carry the
  bug: reconstruction/award median **1.0020** (R1) / 1.0053 (R2), n=126,
  against stored/award 1.96 / 1.74.
* `player_track` -- the proximity tracker's spawn/death gaps, a completely
  separate code path: reconstruction/track 0.9166 / 0.9335 (the gap method
  underestimates ~8% by construction, since the last death of a round has no
  following spawn), against stored/track 1.94 / 2.00.
* Against `player_track` row by row, the reconstruction is closer on **80.7%**
  of rows and the median absolute error falls from 1.125 min to 0.289 min.

Both external arbiters only cover 2026-01..03. For the bulk-imported era there
is no independent source; what carries it there is the mechanism (read out of
the old Lua) plus the fact that the file/reconstruction ratio is the same
2.17-2.24 in all four provenance cells.

REVERSIBILITY
-------------
The previous value goes to `time_dead_minutes_original` (which has been NULL
on every row since migration 037 reserved it for exactly this), and the row is
stamped `time_dead_reconstructed = TRUE` (migration 081) so a consumer can ASK
whether a number is a measurement instead of inferring it from a date range.
`--apply` additionally writes a row-level rollback script before touching
anything.

USAGE
-----
    python scripts/repair_dead_time_reconstruction.py                # preview
    python scripts/repair_dead_time_reconstruction.py --apply \
        --backup-manifest backups/<stamp>.manifest \
        --expect-count N --expect-fingerprint <sha256>
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# The columns this repair is allowed to touch. Pinned by a test: a repair that
# can quietly grow its own blast radius is not a repair.
REPAIRED_COLUMNS = (
    "time_dead_minutes",
    "time_dead_ratio",
    "time_dead_minutes_original",
    "time_dead_reconstructed",
)

# The first day whose rounds carry the FIXED Lua. Rows on or after it are
# measurements and must never be touched by this script.
DEFAULT_CUTOFF = "2026-03-24"

# Below a minute of playtime the alive% is too coarse to derive minutes from
# (one engine tick is a large share of the denominator).
DEFAULT_MIN_SECONDS = 60


def _load_manifest_check():
    """Reuse the apply-gate from scripts/repair_lua_round_links.py.

    Copying those 80 lines would give this repair a second, drifting copy of
    the rule that decides whether a backup is real -- the exact "one fact, two
    copies" shape the project keeps paying for.
    """
    path = _REPO_ROOT / "scripts" / "repair_lua_round_links.py"
    spec = importlib.util.spec_from_file_location("repair_lua_round_links", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["repair_lua_round_links"] = mod
    spec.loader.exec_module(mod)
    return mod.backup_manifest_problems


def reconstruct(time_played_seconds: int, time_played_percent: float) -> tuple[float, float]:
    """(dead_minutes, dead_ratio) from playtime and the engine's alive%.

    The ratio is not recomputed from the minutes -- it IS 100 - alive%, and
    deriving it a second way would let the two disagree by rounding.
    """
    minutes = time_played_seconds / 60.0
    dead = minutes * (1.0 - time_played_percent / 100.0)
    return round(dead, 4), round(100.0 - time_played_percent, 4)


@dataclass(frozen=True)
class Change:
    row_id: int
    round_date: str
    round_number: int
    player_name: str
    played_minutes: float
    old_dead: float
    old_ratio: float
    new_dead: float
    new_ratio: float

    @property
    def was_impossible(self) -> bool:
        """The row claimed more dead time than the player spent in the round."""
        return self.old_dead > self.played_minutes + 0.05 or self.old_ratio > 100.5

    @property
    def factor(self) -> float:
        return self.old_dead / self.new_dead if self.new_dead > 0 else float("inf")


SCOPE_SQL = """
    SELECT pcs.id, pcs.round_date, pcs.round_number, pcs.player_name,
           pcs.time_played_seconds, pcs.time_played_percent,
           pcs.time_dead_minutes, pcs.time_dead_ratio
    FROM player_comprehensive_stats pcs
    WHERE pcs.round_number IN (1, 2)
      AND pcs.round_date < %(cutoff)s
      AND pcs.time_played_seconds > %(min_seconds)s
      AND pcs.time_played_percent > 0
      AND pcs.time_dead_reconstructed IS NULL
      AND NOT EXISTS (
            SELECT 1 FROM rounds rr
            WHERE rr.id = pcs.round_id
              AND (rr.is_valid IS FALSE OR rr.round_status = 'orphan_r2'))
    ORDER BY pcs.id
"""


def _connect(readonly: bool):
    import psycopg2

    required = ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DATABASE",
                "POSTGRES_USER", "POSTGRES_PASSWORD")
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"Missing database env vars: {', '.join(missing)}")
    conn = psycopg2.connect(
        host=os.environ["POSTGRES_HOST"], port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DATABASE"], user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"])
    conn.autocommit = False
    if readonly:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
    return conn


def db_identity() -> str:
    return (f"{os.environ.get('POSTGRES_HOST', '?')}:"
            f"{os.environ.get('POSTGRES_PORT', '?')}/"
            f"{os.environ.get('POSTGRES_DATABASE', '?')}")


def collect(conn, cutoff: str, min_seconds: int) -> list[Change]:
    changes: list[Change] = []
    with conn.cursor() as cur:
        cur.execute(SCOPE_SQL, {"cutoff": cutoff, "min_seconds": min_seconds})
        for row in cur.fetchall():
            row_id, date, rnum, name, tps, tpp, dead, ratio = row
            new_dead, new_ratio = reconstruct(int(tps), float(tpp))
            changes.append(Change(row_id=int(row_id), round_date=str(date),
                                  round_number=int(rnum), player_name=str(name),
                                  played_minutes=int(tps) / 60.0,
                                  old_dead=float(dead or 0.0), old_ratio=float(ratio or 0.0),
                                  new_dead=new_dead, new_ratio=new_ratio))
    return changes


def fingerprint(changes: list[Change]) -> str:
    payload = "\n".join(f"{c.row_id}:{c.old_dead:.4f}:{c.new_dead:.4f}"
                        for c in sorted(changes, key=lambda c: c.row_id))
    return hashlib.sha256(payload.encode()).hexdigest()


def _artifacts(changes: list[Change], stamp: str) -> tuple[list[str], list[str]]:
    """(rollback, repair) statement lists, each guarded on the value it expects."""
    rollback = [f"-- rollback for repair_dead_time_reconstruction {stamp}", "BEGIN;"]
    repair = [f"-- repair_dead_time_reconstruction {stamp}", "BEGIN;"]
    for c in changes:
        rollback.append(
            "UPDATE player_comprehensive_stats SET "
            f"time_dead_minutes = {c.old_dead}, time_dead_ratio = {c.old_ratio}, "
            "time_dead_minutes_original = NULL, time_dead_reconstructed = NULL "
            f"WHERE id = {c.row_id} AND time_dead_reconstructed IS TRUE;")
        repair.append(
            "UPDATE player_comprehensive_stats SET "
            f"time_dead_minutes = {c.new_dead}, time_dead_ratio = {c.new_ratio}, "
            f"time_dead_minutes_original = {c.old_dead}, time_dead_reconstructed = TRUE "
            f"WHERE id = {c.row_id} AND time_dead_reconstructed IS NULL;")
    rollback.append("COMMIT;")
    repair.append("COMMIT;")
    return rollback, repair


def _write_artifact(path: Path, statements: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(statements) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return path


def summarize(changes: list[Change]) -> list[str]:
    if not changes:
        return ["nothing to do"]
    factors = sorted(c.factor for c in changes if c.new_dead > 0)
    lines = [
        f"rows in scope       : {len(changes)}",
        f"dead minutes before : {sum(c.old_dead for c in changes):,.0f}",
        f"dead minutes after  : {sum(c.new_dead for c in changes):,.0f}",
        f"inflation factor    : p10 {factors[len(factors)//10]:.2f} "
        f"median {factors[len(factors)//2]:.2f} "
        f"p90 {factors[len(factors)*9//10]:.2f}",
        f"impossible rows it fixes: "
        f"{sum(1 for c in changes if c.was_impossible)} "
        f"(none may remain — the run rolls back if any do)",
        f"rows the repair RAISES: "
        f"{sum(1 for c in changes if c.new_dead > c.old_dead + 0.05)}",
    ]
    worst = sorted(changes, key=lambda c: c.old_dead - c.new_dead, reverse=True)[:3]
    lines.append("largest reductions:")
    lines.extend(
        f"  id={c.row_id} {c.round_date} R{c.round_number} {c.player_name}: "
        f"{c.old_dead:.2f} -> {c.new_dead:.2f} min (x{c.factor:.2f})" for c in worst)
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="write the repair (default: preview only, read-only connection)")
    ap.add_argument("--cutoff", default=DEFAULT_CUTOFF,
                    help=f"repair rounds strictly before this date (default: {DEFAULT_CUTOFF})")
    ap.add_argument("--min-seconds", type=int, default=DEFAULT_MIN_SECONDS)
    ap.add_argument("--artifact-dir", default=str(_REPO_ROOT / "dead_time_repair_artifacts"))
    ap.add_argument("--backup-manifest", default=None,
                    help="manifest emitted by scripts/db_backup.sh (required with --apply)")
    ap.add_argument("--expect-count", type=int, default=None)
    ap.add_argument("--expect-fingerprint", default=None)
    args = ap.parse_args(argv)

    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")

    conn = _connect(readonly=not args.apply)
    try:
        changes = collect(conn, args.cutoff, args.min_seconds)
        print("\n".join(summarize(changes)))
        print(f"fingerprint         : {fingerprint(changes)}")
        if not changes:
            return 0
        if not args.apply:
            print("\npreview only — pass --apply with a verified backup manifest to write")
            return 0

        problems = _load_manifest_check()(args.backup_manifest, db_identity())
        if args.expect_count is not None and args.expect_count != len(changes):
            problems.append(f"--expect-count {args.expect_count} != {len(changes)} rows in scope")
        if args.expect_fingerprint and args.expect_fingerprint != fingerprint(changes):
            problems.append("--expect-fingerprint does not match the current scope")
        if problems:
            print("\nREFUSING TO WRITE:")
            print("\n".join(f"  - {p}" for p in problems))
            return 2

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        rollback, repair = _artifacts(changes, stamp)
        art = Path(args.artifact_dir)
        # The rollback goes to disk, fsynced, BEFORE the first UPDATE.
        back_path = _write_artifact(art / f"backup-{stamp}.sql", rollback)
        rep_path = _write_artifact(art / f"repair-{stamp}.sql", repair)
        print(f"\nrollback written    : {back_path}")
        print(f"repair written      : {rep_path}")

        with conn.cursor() as cur:
            cur.execute("LOCK TABLE player_comprehensive_stats IN SHARE ROW EXCLUSIVE MODE")
            written = 0
            for c in changes:
                cur.execute(
                    "UPDATE player_comprehensive_stats SET time_dead_minutes = %s, "
                    "time_dead_ratio = %s, time_dead_minutes_original = %s, "
                    "time_dead_reconstructed = TRUE "
                    "WHERE id = %s AND time_dead_reconstructed IS NULL",
                    (c.new_dead, c.new_ratio, c.old_dead, c.row_id))
                written += cur.rowcount
            if written != len(changes):
                conn.rollback()
                print(f"\nROLLED BACK: wrote {written} of {len(changes)} rows — "
                      f"a row changed under us")
                return 3
            # Postcondition, measured inside the same transaction: nothing in
            # scope may still claim more dead time than the round lasted.
            cur.execute(
                "SELECT COUNT(*) FROM player_comprehensive_stats "
                "WHERE time_dead_reconstructed IS TRUE "
                "  AND time_dead_minutes > time_played_seconds / 60.0 + 0.05")
            impossible = int(cur.fetchone()[0])
            if impossible:
                conn.rollback()
                print(f"\nROLLED BACK: {impossible} repaired rows still impossible")
                return 4
        conn.commit()
        print(f"\ncommitted           : {written} rows")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
