#!/usr/bin/env python3
"""Phase-0 backtest: Objective Pressure — "real pressure seconds" v0 (READ-ONLY).

Good Night plan rank 6 (§F). Goal: reward the part of ET that raw K/D misses —
time a player spends applying REAL objective pressure, not just fragging.

Definitions (the script runs BOTH and prints the A/B):
  v0   — 2D, any-zone: a sample counts while the player is within any objective
         radius (2D) AND both teams have someone in a zone that ~200ms bucket.
  v0.2 — 3D, per-zone + teammate support: a sample counts only when the player
         is inside a SPECIFIC objective (full 3D distance, so a different floor
         doesn't count) AND that same objective has an enemy contesting it (§F.1)
         AND at least one teammate is in it too (>=2 of the player's team => not
         "empty pressure", §F.2). "Alive" is implicit: a track exists only
         between spawn and death.

This proves-with-a-table whether the metric adds signal before any endpoint/UI:
we compare each session's pressure-seconds leaders against its frag leaders. The
"hidden objective players" are pressure leaders the kills column misses — the
invisible objective value the metric is meant to surface.

No writes: SET default_transaction_read_only = on; pure SELECT + geometry.
"""
import asyncio
import json
import os
import sys
from collections import defaultdict

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from website.backend.services.objective_pressure_service import (  # noqa: E402
    _accumulate_round,  # canonical v0.2 accumulator — keep backtest and service in lockstep
)
from website.backend.utils.et_constants import strip_et_colors  # noqa: E402

BUCKET_MS = 200          # time granularity for the contested cross-check
SAMPLE_CAP_MS = 400      # cap a sample's credited duration so track gaps don't inflate
ZONES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "website/assets/maps/proximity/objective_zones.json")


def _load_zones():
    """map_name (and aliases), lowercased -> list of (x, y, z, radius)."""
    with open(ZONES_PATH) as f:
        raw = json.load(f)
    out: dict[str, list] = {}
    for m in raw["maps"].values():
        objs = [(o["x"], o["y"], o.get("z", 0.0), o.get("radius", 500))
                for o in m.get("objectives", [])]
        if not objs:
            continue
        for key in [m.get("map_name", "")] + m.get("aliases", []):
            if key:
                out[key.lower()] = objs
    return out


def _in_any_zone_2d(x, y, zones):
    """v0 baseline: 2D-only, any objective (the pre-refinement definition).
    The shipped v0.2 uses the service's 3D per-zone accumulator instead."""
    return any((x - zx) ** 2 + (y - zy) ** 2 <= r * r for zx, zy, _zz, r in zones)


async def main():
    zones_by_map = _load_zones()

    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PGPASSWORD", ""))
    await conn.execute("SET default_transaction_read_only = on")

    dates = await conn.fetch("""
        SELECT session_date, COUNT(*) AS n
        FROM player_track
        WHERE path IS NOT NULL AND sample_count > 0
        GROUP BY session_date HAVING COUNT(*) >= 20
        ORDER BY session_date DESC LIMIT 10""")

    print("Objective Pressure — v0 (2D any-zone) vs v0.2 (3D per-zone + teammate support), bots excluded")
    print(f"{'date':<11}{'maps':>4}{'trk':>6}  {'top v0.2 pressure (player=sec)':<40} "
          f"{'hidden-count':<12} hidden objective players [v0.2]")
    print("-" * 118)

    for drow in dates:
        sd = drow["session_date"]
        tracks = await conn.fetch("""
            SELECT round_start_unix, round_number, map_name, player_guid, player_name,
                   team, path
            FROM player_track
            WHERE session_date = $1 AND path IS NOT NULL AND sample_count > 0
              AND round_start_unix IS NOT NULL AND round_start_unix > 0
              AND player_guid NOT LIKE 'OMNIBOT%' AND player_name NOT LIKE '[BOT]%'""", sd)

        p_v0 = defaultdict(float)      # player -> v0 pressure seconds (2D, any-zone contested)
        p_v02 = defaultdict(float)     # player -> v0.2 (3D, per-zone contested + teammate support)
        maps_used = set()

        by_round = defaultdict(list)
        for t in tracks:
            by_round[(t["round_start_unix"], t["round_number"], t["map_name"])].append(t)

        for (_rsu, _rnum, mapname), rtracks in by_round.items():
            zones = zones_by_map.get((mapname or "").lower())
            if not zones:
                continue
            maps_used.add(mapname)

            # Parse once; keep the display name as the aggregation key for both.
            v0_teams: dict[int, set] = defaultdict(set)
            parsed_v0 = []           # (name, samples, marks) for the v0 baseline
            svc_rtracks = []         # (team, name, samples) for the canonical v0.2
            for t in rtracks:
                path = t["path"] if isinstance(t["path"], list) else json.loads(t["path"])
                samples = sorted(
                    (int(s["time"]), float(s["x"]), float(s["y"]), float(s.get("z", 0.0)))
                    for s in path if "time" in s and "x" in s and "y" in s)
                if not samples:
                    continue
                name = strip_et_colors(t["player_name"] or t["player_guid"][:8])
                svc_rtracks.append((t["team"], name, samples))
                marks = []  # (time, in_any_2d)
                for tm, x, y, _z in samples:
                    a2 = _in_any_zone_2d(x, y, zones)
                    marks.append((tm, a2))
                    if a2:
                        v0_teams[tm // BUCKET_MS].add(t["team"])
                parsed_v0.append((name, samples, marks))

            # v0.2 = the SHIPPED service accumulator (distinct-player support,
            # forward-gap credit, terminal sample = 0) — no divergence from prod.
            _accumulate_round(svc_rtracks, zones, p_v02)

            # v0 = the pre-refinement baseline (2D any-zone, count-based, old
            # last-sample fallback) kept only for the A/B contrast.
            for name, samples, marks in parsed_v0:
                for i, (tm, a2) in enumerate(marks):
                    if a2 and len(v0_teams.get(tm // BUCKET_MS, ())) >= 2:
                        dt = (samples[i + 1][0] - tm) if i + 1 < len(samples) else BUCKET_MS
                        p_v0[name] += min(max(dt, 0), SAMPLE_CAP_MS) / 1000.0

        if not p_v02 and not p_v0:
            print(f"{str(sd):<11}{len(maps_used):>5}{len(tracks):>7}  (no zoned maps)")
            continue

        # Frag leaders for the same session (from combat_position kills), bots excluded.
        frags = await conn.fetch("""
            SELECT attacker_name AS name, COUNT(*) AS k
            FROM proximity_combat_position
            WHERE session_date = $1 AND event_type = 'kill'
              AND attacker_team IS NOT NULL AND attacker_team != victim_team
              AND attacker_guid NOT LIKE 'OMNIBOT%' AND attacker_name NOT LIKE '[BOT]%'
            GROUP BY attacker_name ORDER BY k DESC LIMIT 5""", sd)
        frag_names = {strip_et_colors(f["name"]) for f in frags}

        def _hidden(pdict, frags=frag_names):
            top = [n for n, _ in sorted(pdict.items(), key=lambda kv: -kv[1])[:5]]
            return top, [n for n in top if n not in frags]

        _v0_top, v0_hidden = _hidden(p_v0)
        v02_top, v02_hidden = _hidden(p_v02)
        v02_str = ", ".join(f"{n}={p_v02[n]:.0f}" for n in v02_top)
        h02 = ", ".join(v02_hidden) or "(none)"
        print(f"{str(sd):<11}{len(maps_used):>4}{len(tracks):>6}  {v02_str[:40]:<40} "
              f"{f'v0:{len(v0_hidden)} v0.2:{len(v02_hidden)}':<12} {h02[:34]}")

    await conn.close()


asyncio.run(main())
