#!/usr/bin/env python3
"""K-B2: defender dead-time before objective advance — CASE-CONTROL (READ-ONLY).

SuperBoyy hypothesis: defender dead-time SPIKES just before the objective
advances. Owner guard: comparing "before advance" alone is hindsight bias —
so we compare ADVANCE events against NEAR-MISS controls (dynamite DEFUSED =
a plant that nearly advanced but was stopped) and each against its own
baseline 60s earlier.

Dead fraction from player_track life windows (true spawn->death intervals,
NOT the effective_denied_ms proxy the first probe used):
  dead_frac(team, T) = 1 - alive(T)/roster ;  alive = spawn<=T<death.

formula_version = obj-deadtime-v0.1. Prints SAMPLE SIZES per group.
"""
from __future__ import annotations

import asyncio
import os
import statistics as st

import asyncpg

FORMULA_VERSION = "obj-deadtime-v0.1"
BEFORE_S, BASELINE_S = 5, 60   # measure at T-5s vs T-60s


async def main() -> None:
    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PGPASSWORD", ""))
    await conn.execute("SET default_transaction_read_only = on")

    # life windows per round/team
    tracks = await conn.fetch("""
        SELECT round_id, team, spawn_time_ms,
               COALESCE(death_time_ms, 2147483647) AS death_ms, player_guid
        FROM player_track
        WHERE round_id IS NOT NULL AND team IN ('AXIS', 'ALLIES')
          AND player_guid NOT LIKE 'OMNIBOT%'""")
    lives: dict = {}
    rosters: dict = {}
    for r in tracks:
        key = (r["round_id"], r["team"])
        lives.setdefault(key, []).append(
            (int(r["spawn_time_ms"] or 0), int(r["death_ms"]), r["player_guid"][:8]))
        rosters.setdefault(key, set()).add(r["player_guid"][:8])

    def dead_frac(round_id: int, team: str, t_ms: int) -> float | None:
        key = (round_id, team)
        roster = rosters.get(key)
        if not roster or t_ms <= 0:
            return None
        # DISTINCT players alive at t — duplicate/overlapping windows for
        # one player must not count twice (codex, PR #463)
        alive = len({g for s, d, g in lives[key] if s <= t_ms < d})
        return 1.0 - min(alive, len(roster)) / len(roster)

    # ADVANCE = attackers progressed a phase; CONTROL = near-miss (defused).
    # construction_event has acting player's team -> defender = the other one.
    events = await conn.fetch("""
        SELECT round_id, event_time, event_type, player_team
        FROM proximity_construction_event
        WHERE round_id IS NOT NULL
          AND event_type IN ('objective_destroyed', 'construction_complete',
                             'dynamite_defuse')
          AND player_team IN ('AXIS', 'ALLIES')""")

    groups = {"ADVANCE": [], "NEAR-MISS(defuse)": []}
    for e in events:
        if e["event_type"] == "dynamite_defuse":
            # defuser IS the defender
            grp, defender = "NEAR-MISS(defuse)", e["player_team"]
        else:
            grp = "ADVANCE"
            defender = "ALLIES" if e["player_team"] == "AXIS" else "AXIS"
        t = int(e["event_time"] or 0)
        before = dead_frac(e["round_id"], defender, t - BEFORE_S * 1000)
        base = dead_frac(e["round_id"], defender, t - BASELINE_S * 1000)
        if before is None or base is None:
            continue
        groups[grp].append((before, base))

    print(f"=== objective-phase defender dead-time  formula_version={FORMULA_VERSION} ===")
    print(f"windows: before=T-{BEFORE_S}s baseline=T-{BASELINE_S}s | "
          f"life-source=player_track spawn/death | rounds_with_tracks={len({k[0] for k in lives})}")
    stats = {}
    for grp, vals in groups.items():
        if not vals:
            continue
        b = [v[0] for v in vals]
        base = [v[1] for v in vals]
        delta = st.mean(b) - st.mean(base)
        higher = sum(1 for x, y in vals if x > y)
        stats[grp] = (st.mean(b), st.mean(base), delta, higher, len(vals))
        print(f"{grp:<18} n={len(vals):>4} | dead_frac before={st.mean(b):.3f} "
              f"baseline={st.mean(base):.3f} delta={delta:+.3f} | "
              f"before>baseline in {higher}/{len(vals)} ({100 * higher / len(vals):.0f}%)")

    if "ADVANCE" in stats and "NEAR-MISS(defuse)" in stats:
        da, dn = stats["ADVANCE"][2], stats["NEAR-MISS(defuse)"][2]
        print(f"\nCASE-CONTROL verdict: advance delta {da:+.3f} vs near-miss delta {dn:+.3f} "
              f"-> spike is {'INFORMATIVE (separates success from near-miss)' if da - dn > 0.03 else 'NOT informative beyond hindsight'} "
              f"(diff {da - dn:+.3f})")

asyncio.run(main())
