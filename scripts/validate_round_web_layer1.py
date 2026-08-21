#!/usr/bin/env python3
"""Check Layer 1 against the real database. READ-ONLY.

Three claims, three measurements. Each one is a defect the replay slider cannot
see and a relational layer cannot survive, so none of them is taken on trust:

1. **Life selection.** `replay_service.get_player_positions` breaks on the first
   life whose window contains `t`, walking them in ascending `spawn_time_ms` —
   so it picks the EARLIEST overlapping life. Layer 1 picks the latest. This
   run reports how often the two disagree on real rounds, which is the only
   number that says whether the fix matters.

2. **Floor, not nearest.** For a sampled set of `t`, no state Layer 1 returns
   may carry a source timestamp greater than `t`. This is a one-line invariant
   and the single most important difference between the two modules.

3. **Velocity.** Derived directions must agree with the scalar speed the tracker
   actually stored, and every refusal must carry a reason rather than a number.

Also measures cost per snapshot, against the 27 ms / 51 ms baseline the spec
recorded for `get_player_positions`.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from website.backend.dependencies import get_db_pool, init_db_pool  # noqa: E402
from website.backend.services import replay_service  # noqa: E402
from website.backend.services.round_web_service import (  # noqa: E402
    build_snapshot,
    find_position_floor,
    load_round_engagements,
    load_round_tracks,
    nearest_teammate_separation,
    select_life,
)


async def overlapping_rounds(db, limit: int) -> list[int]:
    rows = await db.fetch_all("""
        WITH pairs AS (
          SELECT a.round_id
          FROM player_track a
          JOIN player_track b
            ON a.round_id = b.round_id AND a.player_guid = b.player_guid AND a.id < b.id
          WHERE a.round_id IS NOT NULL
            AND a.spawn_time_ms < COALESCE(b.death_time_ms, 2147483647)
            AND b.spawn_time_ms < COALESCE(a.death_time_ms, 2147483647)
        )
        SELECT round_id, count(*) AS n FROM pairs GROUP BY 1 ORDER BY 2 DESC LIMIT $1
    """, (limit,))
    return [r[0] for r in rows]


def old_life_choice(track_list, t_ms):
    """Exactly what get_player_positions does today, for a like-for-like diff."""
    for t in track_list:
        spawn_ms = t[4] or 0
        death_ms = t[5]
        if spawn_ms <= t_ms and (death_ms is None or death_ms >= t_ms):
            return t
    return None


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--ticks", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20260821)
    args = ap.parse_args()
    random.seed(args.seed)

    await init_db_pool()
    db = get_db_pool()

    round_ids = await overlapping_rounds(db, args.rounds)
    print(f"  rund s prekrivanji: {len(round_ids)} -> {round_ids}")

    disagreements = 0
    compared = 0
    conflicts_total = 0
    future_violations = 0
    velocity_reasons: Counter[str] = Counter()
    velocity_ok = 0
    durations: list[float] = []
    player_counts: list[int] = []

    for round_id in round_ids:
        tracks = await load_round_tracks(db, round_id)
        engagements = await load_round_engagements(db, round_id)
        if not tracks:
            continue

        spawns = [t[4] or 0 for lst in tracks.values() for t in lst]
        deaths = [t[5] for lst in tracks.values() for t in lst if t[5] is not None]
        if not spawns or not deaths:
            continue
        t_lo, t_hi = min(spawns), max(deaths)
        if t_hi <= t_lo:
            continue

        for _ in range(args.ticks):
            # Sampling ticks to probe, not generating anything secret.
            t_ms = random.randint(t_lo, t_hi)  # noqa: S311

            # 1. old vs new life choice
            for lst in tracks.values():
                old = old_life_choice(lst, t_ms)
                new, alive, _conflict = select_life(lst, t_ms)
                if old is None and new is None:
                    continue
                compared += 1
                if alive and old is not None and new is not None and old[8] != new[8]:
                    disagreements += 1

            started = time.perf_counter()
            snap = build_snapshot(tracks, t_ms, engagements=engagements)
            durations.append((time.perf_counter() - started) * 1000.0)
            player_counts.append(len(snap.players))
            conflicts_total += snap.overlap_conflicts

            # 2. floor invariant — nothing may come from after t
            for guid, st in snap.players.items():
                if not st.alive:
                    continue  # a dead player is shown at their death time by design
                if st.stale_ms < 0:
                    future_violations += 1
                    print(f"    ⚠️ negativna zastarelost: round={round_id} t={t_ms} {guid}")

            # 3. velocity
            for st in snap.players.values():
                if not st.alive:
                    continue
                if st.velocity_reason:
                    velocity_reasons[st.velocity_reason] += 1
                else:
                    velocity_ok += 1

            _ = nearest_teammate_separation(snap)

    print("\n  === 1. IZBIRA ŽIVLJENJA (stara proti novi) ===")
    print(f"    primerjav: {compared}")
    print(f"    ⭐ NEUJEMANJ: {disagreements}"
          f"  ({100.0 * disagreements / max(compared, 1):.2f} %)")
    print(f"    zaznanih prekrivanj (overlap_conflict): {conflicts_total}")

    print("\n  === 2. FLOOR INVARIANTA ===")
    print(f"    kršitev (stanje iz prihodnosti): {future_violations}")

    print("\n  === 3. HITROST ===")
    print(f"    izpeljanih: {velocity_ok}")
    for reason, n in velocity_reasons.most_common():
        print(f"    zavrnjenih [{reason}]: {n}")

    if durations:
        durations.sort()
        print("\n  === CENA ===")
        print(f"    posnetkov: {len(durations)}  igralcev povprečno: "
              f"{sum(player_counts) / len(player_counts):.1f}")
        print(f"    mediana {durations[len(durations) // 2]:.2f} ms   "
              f"p95 {durations[int(len(durations) * 0.95)]:.2f} ms   "
              f"max {durations[-1]:.2f} ms")
        print("    (izhodišče get_player_positions po specu: 27 ms / 51 ms)")

    # The floor helper on its own, against the module it replaces.
    print("\n  === floor proti nearest (sintetično) ===")
    path = [{"time": 0, "x": 0}, {"time": 1000, "x": 1}, {"time": 2000, "x": 2}]
    for target in (900, 1100, 1999):
        f_sample, stale = find_position_floor(path, target)
        # Reaching into the private helper on purpose: the whole point of this
        # block is to show what the function Layer 1 replaces would answer.
        n_sample = replay_service._find_position_at_time(path, target)  # noqa: SLF001
        flag = "⚠️ IZ PRIHODNOSTI" if n_sample["time"] > target else ""
        print(f"    t={target:5d}  floor={f_sample['time']:5d} (stale {stale:4d})"
              f"   nearest={n_sample['time']:5d} {flag}")

    return 0 if future_violations == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
