#!/usr/bin/env python3
"""W5 probe: help/harm ledger + clutch solo-duration (owner answer A1).

READ-ONLY. The owner asked (2026-07-07): reward clutches AND other great
plays; look at who helped their team — and the mirror image, who accidentally
helped the OPPONENT ("own goal, se zgodi, ne-namerno").

Section 1 — HELP vs HARM ledger, per player (all-time, per-session rates):
    help:  KIS/session (kill value), OIS/session (objective value)
    harm:  team kills, team gibs, team damage per minute, docs lost as
           carrier (carrier_event outcome='killed'), full selfkills
    net view = table for the owner; no formula yet — v1 numbers first
    (the owner explicitly said "vendar nevem kako" — evidence before weights)

Section 2 — clutch DIFFICULTY add-on: for each detected last-alive chain,
how long the clutcher had already been alone (side alive == 1) before the
first chain kill. Longer solo time under pressure = harder clutch; candidate
multiplier for clutch v1 alongside the existing R2 time-to-beat stake.

Constraints: ~200ms track quantization; alive counts valid since 2026-04;
bot rows excluded; is_valid via linked rounds.
"""
from __future__ import annotations

import asyncio
import os
import re
import statistics as st
import sys
from collections import defaultdict

import asyncpg

FORMULA_VERSION = "help-harm-v0.1"
MIN_SESSIONS = 5
ALIVE_SINCE = "2026-04-01"
CHAIN_WINDOW_MS = 15_000

_COLOR = re.compile(r"\^.")


def _clean(s: str) -> str:
    return _COLOR.sub("", s or "")


async def main() -> int:
    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PGPASSWORD", ""))
    await conn.execute("SET default_transaction_read_only = on")

    # ---- Section 1: ledger ------------------------------------------------
    base = await conn.fetch("""
        SELECT UPPER(LEFT(p.player_guid, 8)) AS g8,
               MAX(p.player_name) AS name,
               COUNT(DISTINCT r.gaming_session_id) AS sessions,
               SUM(p.team_kills) AS tk,
               SUM(p.team_gibs) AS tg,
               SUM(p.team_damage_given) AS td,
               SUM(p.full_selfkills) AS fsk,
               SUM(p.time_played_seconds) / 60.0 AS minutes
        FROM player_comprehensive_stats p
        JOIN rounds r ON r.id = p.round_id
        WHERE r.is_valid AND r.gaming_session_id IS NOT NULL
          AND p.player_guid NOT LIKE 'OMNIBOT%'
          AND p.player_name NOT LIKE '[BOT]%'
        GROUP BY UPPER(LEFT(p.player_guid, 8))
        HAVING COUNT(DISTINCT r.gaming_session_id) >= $1
    """, MIN_SESSIONS)

    kis = {r[0]: float(r[1] or 0) for r in await conn.fetch("""
        SELECT UPPER(LEFT(killer_guid, 8)), SUM(total_impact)
        FROM storytelling_kill_impact
        WHERE killer_guid NOT LIKE 'OMNIBOT%' AND killer_name NOT LIKE '[BOT]%'
        GROUP BY 1""")}

    ois: dict[str, float] = defaultdict(float)
    for r in await conn.fetch("""
        SELECT UPPER(LEFT(returner_guid, 8)), COUNT(*)
        FROM proximity_carrier_return
        WHERE returner_guid IS NOT NULL AND returner_guid NOT LIKE 'OMNIBOT%'
        GROUP BY 1"""):
        ois[r[0]] += 3.0 * r[1]
    for r in await conn.fetch("""
        SELECT UPPER(LEFT(player_guid, 8)), event_type, COUNT(*)
        FROM proximity_construction_event
        WHERE event_type IN ('dynamite_defuse', 'construction_complete')
          AND player_guid IS NOT NULL AND player_guid NOT LIKE 'OMNIBOT%'
        GROUP BY 1, 2"""):
        ois[r[0]] += (2.5 if r[1] == "dynamite_defuse" else 2.0) * r[2]

    docs_lost = {r[0]: int(r[1]) for r in await conn.fetch("""
        SELECT UPPER(LEFT(carrier_guid, 8)), COUNT(*)
        FROM proximity_carrier_event
        WHERE outcome = 'killed' AND carrier_guid IS NOT NULL
          AND carrier_guid NOT LIKE 'OMNIBOT%'
        GROUP BY 1""")}

    rows = []
    for b in base:
        g8, name, sess = b["g8"], _clean(b["name"]), int(b["sessions"])
        minutes = float(b["minutes"] or 1)
        rows.append({
            "g8": g8, "name": name, "sessions": sess,
            "help_kis_ps": kis.get(g8, 0.0) / sess,
            "help_ois_ps": ois.get(g8, 0.0) / sess,
            "tk_ps": int(b["tk"] or 0) / sess,
            "tg_ps": int(b["tg"] or 0) / sess,
            "td_pm": float(b["td"] or 0) / minutes,
            "docs_lost_ps": docs_lost.get(g8, 0) / sess,
            "fsk_ps": int(b["fsk"] or 0) / sess,
        })

    rows.sort(key=lambda r: -(r["help_kis_ps"] + r["help_ois_ps"]))
    print(f"=== HELP vs HARM ledger  {FORMULA_VERSION} ===")
    print(f"SAMPLE: players={len(rows)} (>= {MIN_SESSIONS} sessions)")
    hdr = (f"{'player':<15}{'sess':>5} | {'KIS/s':>7}{'OIS/s':>7} | "
           f"{'TK/s':>6}{'TGib/s':>7}{'TDmg/m':>7}{'docsL/s':>8}{'FSK/s':>6}")
    print(hdr)
    for r in rows:
        print(f"{r['name'][:14]:<15}{r['sessions']:>5} | "
              f"{r['help_kis_ps']:>7.1f}{r['help_ois_ps']:>7.2f} | "
              f"{r['tk_ps']:>6.2f}{r['tg_ps']:>7.2f}{r['td_pm']:>7.1f}"
              f"{r['docs_lost_ps']:>8.2f}{r['fsk_ps']:>6.2f}")

    # ---- Section 2: clutch solo-duration ----------------------------------
    # life windows per (round, side) to reconstruct when the side hit 1 alive
    tracks = await conn.fetch("""
        SELECT pt.round_start_unix AS rsu, pt.team,
               UPPER(LEFT(pt.player_guid, 8)) AS g8,
               pt.spawn_time_ms AS s, COALESCE(pt.death_time_ms, 2147483647) AS d
        FROM player_track pt
        JOIN rounds r ON r.id = pt.round_id AND r.is_valid
        WHERE pt.team IN ('AXIS', 'ALLIES') AND pt.round_start_unix > 0
          AND pt.spawn_time_ms >= 0
          AND pt.player_guid NOT LIKE 'OMNIBOT%'
          AND pt.player_name NOT LIKE '[BOT]%'
    """)
    lives: dict = defaultdict(list)
    for t in tracks:
        lives[(int(t["rsu"]), t["team"])].append((int(t["s"]), int(t["d"]), t["g8"]))

    def solo_since(rsu: int, team: str, g8: str, t_ms: int) -> int | None:
        """ms the player had ALREADY been the side's only alive one at t."""
        wins = lives.get((rsu, team))
        if not wins:
            return None
        others = [(s, d) for s, d, g in wins if g != g8]
        if not others:
            return None
        # last moment before t when another teammate was alive
        last_mate = max((d for s, d in others if s <= t_ms and d <= t_ms),
                        default=None)
        if last_mate is None:
            return None
        if any(s <= t_ms < d for s, d in others):
            return 0  # a mate is alive — not solo at all
        return max(0, t_ms - last_mate)

    chains = await conn.fetch("""
        SELECT DISTINCT ON (ki.id)
               ki.round_start_unix AS rsu, UPPER(LEFT(ki.killer_guid, 8)) AS g8,
               MAX(ki.killer_name) OVER (PARTITION BY ki.id) AS name,
               ki.kill_time_ms AS t, cp.attacker_team AS team
        FROM storytelling_kill_impact ki
        JOIN proximity_combat_position cp
          ON cp.round_start_unix = ki.round_start_unix
         AND UPPER(LEFT(cp.attacker_guid, 8)) = UPPER(LEFT(ki.killer_guid, 8))
         AND ABS(cp.event_time - ki.kill_time_ms) <= 300
        WHERE ki.session_date >= $1::date
          AND ki.round_start_unix > 0
          AND cp.axis_alive > 0 AND cp.allies_alive > 0
          AND ((cp.attacker_team = 'AXIS' AND cp.axis_alive = 1)
            OR (cp.attacker_team = 'ALLIES' AND cp.allies_alive = 1))
          AND ki.killer_guid NOT LIKE 'OMNIBOT%'
          AND ki.killer_name NOT LIKE '[BOT]%'
        ORDER BY ki.id
    """, __import__("datetime").date.fromisoformat(ALIVE_SINCE))

    # first kill per (round, killer) chain
    per_chain: dict = {}
    for c in sorted(chains, key=lambda c: (c["rsu"], c["g8"], c["t"])):
        key = (int(c["rsu"]), c["g8"])
        prev = per_chain.get(key)
        if prev is None or int(c["t"]) - prev["last_t"] > CHAIN_WINDOW_MS:
            per_chain[key] = {"first_t": int(c["t"]), "last_t": int(c["t"]),
                              "team": c["team"], "name": _clean(c["name"]),
                              "n": 1}
        else:
            prev["last_t"] = int(c["t"])
            prev["n"] += 1

    solos = []
    for (rsu, g8), ch in per_chain.items():
        if ch["n"] < 2:
            continue
        sd = solo_since(rsu, ch["team"], g8, ch["first_t"])
        if sd is not None:
            solos.append((sd / 1000.0, ch["n"], ch["name"]))

    print(f"\n=== CLUTCH SOLO-DURATION (chains >= 2 kills since {ALIVE_SINCE}) ===")
    print(f"SAMPLE: chains={len(solos)}")
    if solos:
        vals = [s for s, _n, _ in solos]
        print(f"solo-before-first-kill: median={st.median(vals):.1f}s "
              f"p25={sorted(vals)[len(vals)//4]:.1f}s "
              f"p75={sorted(vals)[3*len(vals)//4]:.1f}s max={max(vals):.1f}s")
        solos.sort(reverse=True)
        print("longest-solo clutches (difficulty candidates):")
        for sdur, n, name in solos[:8]:
            print(f"  {name[:16]:<17} solo {sdur:>6.1f}s before a {n}-kill chain")
        zero = sum(1 for s in vals if s < 1.0)
        print(f"chains starting <1s after side hit 1 alive: {zero}/{len(vals)} "
              f"({100 * zero // len(vals)}%) — instant-clutch vs endured-solo split")

    await conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
