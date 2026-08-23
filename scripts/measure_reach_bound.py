#!/usr/bin/env python3
"""§6.3: how far a player can actually get in N seconds. READ-ONLY.

Layer 3 hands a holder a belief about where an enemy was. The belief ages, and
the region it names has to widen with it — §6.3 line 594 requires it: *"a region
... whose uncertainty grows with time"*. This script measures the widening.

⭐ IT MEASURES DISPLACEMENT, NOT SPEED. The obvious model is `p99_speed x age`,
and it is wrong by 50-80%. The stored `speed` samples put p99 at 533 units/s
over 703,000 samples, which across 8 seconds would be 4,266 units; the players
themselves cover 2,371. Nobody holds top speed in a straight line for eight
seconds — they turn, stop, fight and die. Multiplying an instantaneous
percentile by a duration measures a player who does not exist.

So the question asked here is the one the model needs, directly: take a real
position, look forward N seconds in the SAME life, and record how far they
actually got.

TWO INDEPENDENT SOURCES, REPORTED SEPARATELY

  track  `player_track.path` samples — dense, and the same rows Layer 1 draws.
  shot   `proximity_shot_fired.origin_x/y/z` — written by a different code path
         at different instants, so agreement is evidence and a split is a bug
         in one of them.

⛔ NEVER ACROSS LIVES. A player who dies at one end of the map and spawns at the
other did not travel; joining two lives would measure the respawn and inflate
every band. Pairs are drawn within one `player_track.id` (and for shots, within
one round between consecutive-enough events with no death in between, which is
approximated by capping the window — see `--window-ms`).

⭐ THE OUTPUT IS p99 PER BAND, NOT A MEAN. The region is a containment claim: it
must hold the true position, so it is sized by the tail. A mean would be wrong
about exactly the players who moved.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from website.backend.dependencies import get_db_pool, init_db_pool  # noqa: E402

#: Upper edge of each band, in ms. One second each, out to the longest life a
#: positional belief can have (`contact_hit` decays to the floor at 8 s), plus
#: an open-ended last band so nothing falls outside the table.
REACH_BANDS_MS = (1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, None)

_TRACK_PAIRS = """
WITH r AS (SELECT id FROM rounds ORDER BY id DESC LIMIT $1),
     p AS (
       SELECT pt.id AS tid, (e->>'time')::int AS t,
              (e->>'x')::float AS x, (e->>'y')::float AS y, (e->>'z')::float AS z
       FROM player_track pt JOIN r ON r.id = pt.round_id,
            jsonb_array_elements(pt.path) e
       -- ⚠️ jsonb_exists, not `e ? 'x'`: the adapter rewrites `?` into a
       -- positional placeholder, so the jsonb operator would be swallowed as
       -- a parameter and the numbering after it would shift.
       WHERE jsonb_exists(e, 'x') AND jsonb_exists(e, 'time'))
SELECT b.t - a.t AS dt,
       sqrt(power(b.x-a.x,2) + power(b.y-a.y,2) + power(b.z-a.z,2)) AS dist
FROM p a JOIN p b ON b.tid = a.tid AND b.t > a.t AND b.t <= a.t + $2
WHERE a.t %% $3 = 0
"""

_SHOT_PAIRS = """
-- ⚠️ Rounds come from the SHOT table, not from `rounds`. `shot_fired` has been
-- off in production since 2026-08-11, so the newest rounds carry none and
-- selecting by round id silently produced zero pairs — a second source that
-- measures nothing looks exactly like a second source that agrees.
WITH r AS (SELECT DISTINCT round_id AS id FROM proximity_shot_fired
           WHERE round_id IS NOT NULL ORDER BY id DESC LIMIT $1),
     s AS (
       SELECT sf.round_id, sf.guid, sf.event_time AS t,
              sf.origin_x AS x, sf.origin_y AS y, sf.origin_z AS z
       FROM proximity_shot_fired sf JOIN r ON r.id = sf.round_id
       WHERE sf.origin_x IS NOT NULL)
SELECT b.t - a.t AS dt,
       sqrt(power(b.x-a.x,2) + power(b.y-a.y,2) + power(b.z-a.z,2)) AS dist
FROM s a JOIN s b
  ON b.round_id = a.round_id AND b.guid = a.guid
 AND b.t > a.t AND b.t <= a.t + $2
WHERE a.t %% $3 = 0
"""


def band_of(dt_ms: int) -> str:
    lower = 0
    for upper in REACH_BANDS_MS:
        if upper is None or dt_ms < upper:
            return f"<{upper}ms" if upper else f">={lower}ms"
        lower = upper
    raise AssertionError("unreachable: the last band is open-ended")


def percentile(values: list[float], q: float) -> float:
    return sorted(values)[int(q * (len(values) - 1))]


def report(title: str, by_band: dict[str, list[float]]) -> dict[str, dict]:
    print(f"\n  === {title} ===")
    print(f"    {'pas':>12s} {'parov':>9s} {'p50':>8s} {'p90':>8s} {'p99':>8s} {'max':>8s}")
    out: dict[str, dict] = {}
    for upper in REACH_BANDS_MS:
        band = band_of((upper - 1) if upper else 10 ** 9)
        vals = by_band.get(band)
        if not vals:
            continue
        # ⚠️ A band under a few thousand pairs cannot state a p99 honestly; it
        # is reported so the reader sees the gap, and flagged rather than hidden.
        row = {
            "n": len(vals),
            "p50": round(percentile(vals, 0.50), 1),
            "p90": round(percentile(vals, 0.90), 1),
            "p99": round(percentile(vals, 0.99), 1),
            "max": round(max(vals), 1),
            "well_sampled": len(vals) >= 2000,
        }
        out[band] = row
        flag = "" if row["well_sampled"] else "  ⚠️ premalo vzorcev"
        print(f"    {band:>12s} {row['n']:>9d} {row['p50']:>8.0f} {row['p90']:>8.0f} "
              f"{row['p99']:>8.0f} {row['max']:>8.0f}{flag}")
    return out


async def measure(db, sql: str, params: tuple) -> dict[str, list[float]]:
    rows = await db.fetch_all(sql, params)
    by_band: dict[str, list[float]] = {}
    for dt, dist in (rows or []):
        by_band.setdefault(band_of(int(dt)), []).append(float(dist))
    return by_band


async def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--rounds", type=int, default=60)
    ap.add_argument("--window-ms", type=int, default=8500,
                    help="longest forward pair to draw; one band beyond the last edge")
    ap.add_argument("--stride-ms", type=int, default=1000,
                    help="only start pairs at multiples of this, to bound the join")
    ap.add_argument("--json-out", type=Path,
                    help="write the measured bands here, for freezing into code")
    args = ap.parse_args()

    await init_db_pool()
    db = get_db_pool()

    results: dict[str, dict] = {}
    results["track"] = report(
        f"VIR: track  ({args.rounds} rund)",
        await measure(db, _TRACK_PAIRS % (),
                      (args.rounds, args.window_ms, args.stride_ms)))
    results["shot"] = report(
        f"VIR: shot  ({args.rounds} rund)",
        await measure(db, _SHOT_PAIRS % (),
                      (args.rounds, args.window_ms, args.stride_ms)))

    print("\n  ═══ ⭐ DVE POTI, ISTO VPRAŠANJE ═══")
    print("    Vira sta pisana po različnih kodnih poteh. Če se p99 po pasovih")
    print("    bistveno razideta, je ena od poti pokvarjena — ujemanje je dokaz.")
    print(f"    {'pas':>12s} {'track p99':>12s} {'shot p99':>10s}")
    for band in results["track"]:
        t = results["track"].get(band, {}).get("p99")
        s = results["shot"].get(band, {}).get("p99")
        print(f"    {band:>12s} {str(t):>12s} {str(s):>10s}")

    if args.json_out:
        args.json_out.write_text(json.dumps({
            "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reach_bands_ms": list(REACH_BANDS_MS),
            "rounds": args.rounds,
            "sources": results,
        }, indent=1))
        print(f"\n  zapisano: {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
