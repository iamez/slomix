#!/usr/bin/env python3
"""§12 A2: rebuild the tracker's team aggregates from Layer 1 and compare. READ-ONLY.

`proximity_team_cohesion` is 1.14 million samples the Lua tracker wrote while
the round was live, from the engine's own view of who was alive and where. Layer
1 reconstructs the same thing afterwards from `player_track`. Where the two
disagree, one of them is wrong — and since the tracker was there and Layer 1 was
not, a disagreement is Layer 1's to explain.

⭐ `alive_count` IS THE REAL TEST, not the centroid. A centroid is an average of
positions and survives one player being wrong; the count is a direct read of
whether Layer 1 picked the right lives. A pilot found it matching only 69.7% of
the time, which is why this script reports the disagreement broken down by
cause rather than as one percentage.

WHAT THE TRACKER ACTUALLY DID, checked in the Lua rather than assumed:

  * `analyzeTeamCohesion` builds its roster from `getAliveTeamMembers`, which
    walks every client slot and asks the ENGINE whether they are alive. It does
    NOT filter bots — so this script must not filter them either, or the two
    sides are counting different populations.
  * A sample is written only when the team has at least `min_team_size` (2)
    alive members, so moments below that are absent by design, not missing.
  * `straggler_distance` is 800 units and the maths is 2D (x, y only).
  * The sampler runs every 500 ms, throttled to 1000 ms past 6000 samples.

⚠️ §13.2b names the likeliest source of disagreement in advance: a revived
player's track ends at their death and never reopens, so Layer 1 counts them
dead while the engine counted them alive. This script measures how much of the
gap that accounts for instead of leaving it as a guess.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from website.backend.dependencies import get_db_pool, init_db_pool  # noqa: E402
from website.backend.services.round_web_service import (  # noqa: E402
    build_snapshot,
    load_round_tracks,
)

STRAGGLER_DISTANCE = 800.0  # config.teamplay.straggler_distance
MIN_TEAM_SIZE = 2           # config.teamplay.min_team_size


def aggregates(players) -> dict | None:
    """Centroid, dispersion, max spread and stragglers — the tracker's formulas.

    2D on purpose: `analyzeTeamCohesion` uses x and y only, and adding z here
    would make every comparison disagree for a reason that is ours, not theirs.
    """
    points = [(p.x, p.y) for p in players if p.x is not None and p.y is not None]
    if len(points) < MIN_TEAM_SIZE:
        return None
    cx = sum(x for x, _ in points) / len(points)
    cy = sum(y for _, y in points) / len(points)
    distances = [math.dist((x, y), (cx, cy)) for x, y in points]
    spread = max(
        (math.dist(a, b) for i, a in enumerate(points) for b in points[i + 1:]),
        default=0.0,
    )
    return {
        "alive_count": len(points),
        "centroid": (cx, cy),
        "dispersion": sum(distances) / len(distances),
        "max_spread": spread,
        "stragglers": sum(d > STRAGGLER_DISTANCE for d in distances),
    }


async def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--rounds", type=int, default=40)
    ap.add_argument("--samples-per-round", type=int, default=150)
    ap.add_argument("--seed", type=int, default=20260822)
    args = ap.parse_args()
    # Choosing which recorded samples to compare; nothing secret is generated.
    random.seed(args.seed)

    await init_db_pool()
    db = get_db_pool()

    rows = await db.fetch_all("""
        SELECT DISTINCT round_id FROM proximity_team_cohesion
        WHERE round_id IS NOT NULL ORDER BY round_id DESC LIMIT $1
    """, (args.rounds,))
    round_ids = [int(r[0]) for r in (rows or [])]

    alive_delta: Counter[int] = Counter()
    centroid: list[float] = []
    dispersion: list[float] = []
    spread: list[float] = []
    straggler_delta: Counter[int] = Counter()
    compared = 0
    skipped: Counter[str] = Counter()
    #: How many of the disagreements sit next to a revive, the cause §13.2b
    #: predicts. Measured, not assumed.
    revive_nearby = Counter()

    for round_id in round_ids:
        tracks = await load_round_tracks(db, round_id)
        if not tracks:
            skipped["round_without_tracks"] += 1
            continue
        samples = await db.fetch_all("""
            SELECT sample_time, team, alive_count, centroid_x, centroid_y,
                   dispersion, max_spread, straggler_count
            FROM proximity_team_cohesion WHERE round_id = $1 ORDER BY sample_time
        """, (round_id,))
        revives = [
            int(r[0]) for r in (await db.fetch_all(
                "SELECT revive_time FROM proximity_revive WHERE round_id = $1",
                (round_id,),
            ) or [])
        ]
        chosen = random.sample(list(samples or []),
                               min(args.samples_per_round, len(samples or [])))

        for t_ms, team, their_alive, cx, cy, disp, spr, strag in chosen:
            snap = build_snapshot(tracks, int(t_ms))
            ours = aggregates([
                p for p in snap.players.values()
                if p.alive and (p.team or "") == team
            ])
            if ours is None:
                skipped["below_min_team_size_on_our_side"] += 1
                continue
            compared += 1

            delta = ours["alive_count"] - int(their_alive or 0)
            alive_delta[delta] += 1
            if delta:
                # §13.2b: a revive in the seconds before this sample would leave
                # a player alive for the engine and dead for us.
                near = any(0 <= int(t_ms) - r <= 10_000 for r in revives)
                revive_nearby[("revive within 10s", bool(near), delta < 0)] += 1

            if cx is not None:
                centroid.append(math.dist(ours["centroid"], (float(cx), float(cy))))
            if disp is not None:
                dispersion.append(abs(ours["dispersion"] - float(disp)))
            if spr is not None:
                spread.append(abs(ours["max_spread"] - float(spr)))
            if strag is not None:
                straggler_delta[ours["stragglers"] - int(strag)] += 1

    def stat(name: str, values: list[float]) -> None:
        if not values:
            print(f"    {name}: brez podatkov")
            return
        values.sort()
        q = lambda f: values[min(int(len(values) * f), len(values) - 1)]  # noqa: E731
        print(f"    {name:14s} p50={q(0.5):8.1f}  p90={q(0.9):8.1f}"
              f"  p99={q(0.99):9.1f}  max={values[-1]:9.1f}")

    print(f"  rund: {len(round_ids)}   primerjanih vzorcev: {compared}")
    if skipped:
        print(f"  izpuščeni: {dict(skipped)}")

    print("\n  ═══ ⭐ alive_count — neposreden test izbire življenja ═══")
    total = sum(alive_delta.values()) or 1
    for delta in sorted(alive_delta):
        marker = "  ← ujemanje" if delta == 0 else ""
        print(f"    {delta:+3d}: {alive_delta[delta]:6d}  "
              f"({100.0 * alive_delta[delta] / total:5.1f} %){marker}")

    print("\n  ═══ ali §13.2b (revive) pojasni razliko ═══")
    print("    (negativna razlika = mi štejemo MANJ živih, kot je štel motor)")
    for (label, near, negative), count in sorted(revive_nearby.items()):
        print(f"    {label}={near!s:5s}  mi_manj={negative!s:5s}: {count}")

    print("\n  ═══ prostorski agregati (razlika proti zapisanemu) ═══")
    stat("centroid", centroid)
    stat("dispersion", dispersion)
    stat("max_spread", spread)
    print("\n  ═══ straggler_count (naš − zapisan) ═══")
    stotal = sum(straggler_delta.values()) or 1
    for delta in sorted(straggler_delta):
        print(f"    {delta:+3d}: {straggler_delta[delta]:6d}"
              f"  ({100.0 * straggler_delta[delta] / stotal:5.1f} %)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
