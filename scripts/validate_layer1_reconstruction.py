#!/usr/bin/env python3
"""§12 A1: how far Layer 1's reconstructed position is from a recorded one. READ-ONLY.

Layer 1 answers "where was everyone at time t" by taking the last position
sample at or before t. That answer is only as good as the sampling, and nothing
so far has measured the gap. The page draws a player whose last sample is 76
seconds old exactly as confidently as one sampled 100 ms ago, which is the
single thing the spider-web prototype could not defend.

TWO INDEPENDENT SOURCES, REPORTED SEPARATELY

  attacker  `proximity_combat_position.attacker_x/y/z` at `event_time` — where
            the tracker recorded the killer standing when the obituary fired.
  shot      `proximity_shot_fired.origin_x/y/z` at non-death shot times — a
            much denser sample of ordinary play, and written by a different
            code path, so agreement between the two is evidence and
            disagreement is a bug in one of them.

⛔ THE VICTIM COORDINATE IS EXCLUDED. §12 A1 is explicit: the victim position in
`proximity_combat_position` and the death coordinate in the track are copied
from the same `death_pos` local, so comparing them measures the writer, not the
reconstruction. Including it would inflate the result with a guaranteed match.

⭐ THE OUTPUT IS A DISTRIBUTION PER STALENESS BAND, NOT ONE NUMBER. A pilot over
25 rounds put the median at 13 units (a player is about 40 wide) with a p99 of
1,566 and a maximum of 5,357 — and the tail tracked sample age, up to 76,850 ms.
A single headline figure would hide exactly the cases where the drawing is
least trustworthy, which are the ones a reader needs flagged.

⭐⭐ AND IT SPLITS ON `overlap_conflict`. Measuring the fresh band first showed a
p99 of 2,036 units on samples under 200 ms old — impossible for a player who can
cover about 64 units in that time. Checking every life instead of the chosen one
showed why: of 88 such outliers, 71 would have been right had a DIFFERENT life
been picked, and 64 of those were already flagged `overlap_conflict` by Layer 1.

So the tail is not diffuse uncertainty. It is concentrated in cases the
reconstruction already knows are disputed, which means the page can say "this
position is contested" instead of drawing the player confidently in the wrong
place. Reporting one blended number would have destroyed exactly that signal.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from website.backend.dependencies import get_db_pool, init_db_pool  # noqa: E402
from website.backend.services.replay_service import _ensure_path_list  # noqa: E402
from website.backend.services.round_web_service import (  # noqa: E402
    find_position_floor,
    load_round_tracks,
    select_life,
)

#: Upper edge of each band, in ms. The first covers a single 200 ms capture
#: interval, and the last is open-ended because a stale sample has no natural
#: ceiling — a player who disconnects mid-round can leave one arbitrarily old.
STALENESS_BANDS = (200, 500, 1000, 2000, 5000, None)

PATH_INDEX = 6  # load_round_tracks column order; see its docstring


def band_of(stale_ms: int) -> str:
    previous = 0
    for edge in STALENESS_BANDS:
        if edge is None:
            return f"{previous}+"
        if stale_ms < edge:
            return f"{previous}-{edge}"
        previous = edge
    raise AssertionError("unreachable: the last band is open-ended")


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return float("nan")
    index = min(int(len(values) * fraction), len(values) - 1)
    return values[index]


async def _reconstruct(tracks: dict, guid: str, t_ms: int, skipped: Counter):
    """Layer 1's own answer for one player at one moment, or None with a reason."""
    lives = tracks.get(guid)
    if not lives:
        skipped["no_track_for_guid"] += 1
        return None
    life, _alive, conflict = select_life(lives, t_ms)
    if life is None:
        skipped["no_life_at_or_before_t"] += 1
        return None
    path = _ensure_path_list(life[PATH_INDEX])
    if not path:
        skipped["empty_path"] += 1
        return None
    sample, stale_ms, _index = find_position_floor(path, t_ms)
    if sample is None:
        skipped["no_sample_at_or_before_t"] += 1
        return None
    if sample.get("x") is None or sample.get("y") is None:
        skipped["sample_without_xy"] += 1
        return None
    return sample, stale_ms, conflict


async def measure(db, source: str, rounds: list[int], limit_per_round: int):
    """Distances and sample ages for one source, over the given rounds."""
    by_band: dict[tuple[str, bool], list[float]] = defaultdict(list)
    stale_all: list[int] = []
    skipped: Counter[str] = Counter()
    compared = 0
    seen = 0
    conflicted = 0

    for round_id in rounds:
        tracks = await load_round_tracks(db, round_id)
        if not tracks:
            skipped["round_without_tracks"] += 1
            continue

        if source == "attacker":
            rows = await db.fetch_all("""
                SELECT attacker_guid, event_time, attacker_x, attacker_y, attacker_z
                FROM proximity_combat_position
                WHERE round_id = $1 AND attacker_guid IS NOT NULL
                  AND attacker_x IS NOT NULL AND event_time IS NOT NULL
                ORDER BY event_time
                LIMIT $2
            """, (round_id, limit_per_round))
        else:
            # Non-death shots only: a shot fired at the instant of a kill shares
            # its position with the obituary writer, which would quietly turn
            # this into a second copy of the attacker source instead of an
            # independent one.
            rows = await db.fetch_all("""
                SELECT s.guid, s.event_time, s.origin_x, s.origin_y, s.origin_z
                FROM proximity_shot_fired s
                WHERE s.round_id = $1 AND s.guid IS NOT NULL
                  AND s.origin_x IS NOT NULL AND s.event_time IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM proximity_combat_position c
                      WHERE c.round_id = s.round_id
                        AND c.attacker_guid = s.guid
                        AND abs(c.event_time - s.event_time) <= 50
                  )
                ORDER BY s.event_time
                LIMIT $2
            """, (round_id, limit_per_round))

        for guid, t_ms, x, y, z in (rows or []):
            seen += 1
            result = await _reconstruct(tracks, str(guid), int(t_ms), skipped)
            if result is None:
                continue
            sample, stale_ms, conflict = result
            distance = math.dist(
                (float(sample["x"]), float(sample["y"]), float(sample.get("z") or 0.0)),
                (float(x), float(y), float(z or 0.0)),
            )
            by_band[(band_of(stale_ms), bool(conflict))].append(distance)
            stale_all.append(stale_ms)
            compared += 1
            conflicted += bool(conflict)

    return by_band, stale_all, skipped, compared, seen, conflicted


def band_names() -> list[str]:
    edges = [0, *STALENESS_BANDS[:-1]]
    return [f"{a}-{b}" for a, b in zip(edges, STALENESS_BANDS[:-1])] + [f"{edges[-1]}+"]


def report(title, by_band, stale_all, skipped, compared, seen, conflicted) -> dict:
    print(f"\n  ═══ {title} ═══")
    print(f"    dogodkov: {seen}   primerjanih: {compared}"
          f"   ({100.0 * compared / max(seen, 1):.1f} % pokritost)"
          f"   od tega spornih življenj: {conflicted}")
    if skipped:
        print(f"    izpuščeni: {dict(skipped)}")
    if not compared:
        return {}

    stale_all.sort()
    print(f"    zastarelost vzorca: p50={percentile(stale_all, 0.5):.0f} ms"
          f"  p90={percentile(stale_all, 0.9):.0f} ms  max={stale_all[-1]:.0f} ms")

    bands: dict[str, dict] = {}
    for conflict in (False, True):
        label = "SPORNO ŽIVLJENJE" if conflict else "nesporno"
        print(f"\n    ── {label} ──")
        print(f"    {'pas zastarelosti':>18s} {'n':>7s} {'p50':>7s} {'p75':>7s}"
              f" {'p90':>7s} {'p99':>8s} {'max':>8s}  {'<50 enot':>9s}")
        for band in band_names():
            values = sorted(by_band.get((band, conflict), []))
            if not values:
                continue
            under_50 = 100.0 * sum(v < 50 for v in values) / len(values)
            bands[f"{band}|{'conflict' if conflict else 'clean'}"] = {
                "n": len(values),
                "p50": round(percentile(values, 0.5), 1),
                "p90": round(percentile(values, 0.9), 1),
                "p99": round(percentile(values, 0.99), 1),
                "max": round(values[-1], 1),
                "under_50_units_pct": round(under_50, 1),
            }
            print(f"    {band:>18s} {len(values):7d} {percentile(values, 0.5):7.0f}"
                  f" {percentile(values, 0.75):7.0f} {percentile(values, 0.9):7.0f}"
                  f" {percentile(values, 0.99):8.0f} {values[-1]:8.0f}  {under_50:8.1f} %")
    return bands


async def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--rounds", type=int, default=120)
    ap.add_argument("--per-round", type=int, default=400,
                    help="events sampled per round per source")
    ap.add_argument("--json-out", type=Path,
                    help="write the measured bands here, for freezing into code")
    args = ap.parse_args()

    await init_db_pool()
    db = get_db_pool()

    results: dict[str, dict] = {}
    for source, table in (("attacker", "proximity_combat_position"),
                          ("shot", "proximity_shot_fired")):
        rows = await db.fetch_all(f"""
            SELECT DISTINCT round_id FROM {table}
            WHERE round_id IS NOT NULL
            ORDER BY round_id DESC LIMIT $1
        """, (args.rounds,))  # nosec B608 - table name is from a literal tuple
        rounds = [int(r[0]) for r in (rows or [])]
        measured = await measure(db, source, rounds, args.per_round)
        results[source] = {
            "rounds": len(rounds),
            "bands": report(f"VIR: {source}  ({len(rounds)} rund)", *measured),
        }

    print("\n  ═══ ⭐ DVE POTI, ISTO VPRAŠANJE ═══")
    print("    Vira sta pisana po različnih kodnih poteh. Če se p50 po pasovih")
    print("    bistveno razideta, je ena od poti pokvarjena — ujemanje je dokaz.")
    print(f"    {'pas|stanje':>24s} {'attacker p50':>14s} {'shot p50':>10s}")
    for band in sorted(set(results["attacker"]["bands"]) | set(results["shot"]["bands"])):
        a = results["attacker"]["bands"].get(band, {}).get("p50")
        s = results["shot"]["bands"].get(band, {}).get("p50")
        print(f"    {band:>24s} {str(a):>14s} {str(s):>10s}")

    if args.json_out:
        args.json_out.write_text(json.dumps({
            "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "staleness_bands_ms": list(STALENESS_BANDS),
            "sources": results,
        }, indent=1))
        print(f"\n  zapisano: {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
