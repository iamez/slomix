#!/usr/bin/env python3
"""All-Seeing Eye S1 backtest: 1vN clutch chains valued by KIS (READ-ONLY).

chain value = sum(KIS of chain kills) x N_mult(1v2 1.3 / 1v3 1.7 / 1v4+ 2.2)
              x stake_mult (carrier/objective flags, R2 time-to-beat pressure)
              x outcome_mult (killer's side won round 1.5 / lost 0.6)
              + doc-return bonus (+25% if the clutcher's side returns docs <=30s)

Data valid from ~2026-04 (Oksii alive counts). Golden check: qmr 2026-04-07 R2
te_escape2 (3 kills / 13.25s as last man) must surface near the top.

Usage: PGPASSWORD=... python3 scripts/backtest_clutch_detector.py
"""
from __future__ import annotations

import asyncio
import os
from collections import defaultdict

import asyncpg

CHAIN_WINDOW_MS = 20_000
N_MULT = {2: 1.3, 3: 1.7}          # 4+ -> 2.2
OUT_WIN, OUT_LOSS = 1.5, 0.6
RETURN_BONUS = 0.25


def n_mult(enemies: int) -> float:
    return N_MULT.get(enemies, 2.2 if enemies >= 4 else 1.0)


async def main() -> None:
    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PGPASSWORD", ""))
    await conn.execute("SET default_transaction_read_only = on")

    # Per-kill rows: KIS impact + situational flags + killer side + alive counts.
    # kill_impact lacks killer_team -> join combat_position on (round_start_unix,
    # killer guid8, |kill_time - event_time| <= 300ms).
    rows = await conn.fetch("""
        SELECT ki.session_date, ki.round_start_unix, ki.round_number, ki.map_name,
               UPPER(LEFT(ki.killer_guid, 8)) AS g8, MAX(ki.killer_name) AS name,
               ki.kill_time_ms, MAX(ki.total_impact) AS kis,
               BOOL_OR(ki.is_carrier_kill) AS carrier,
               BOOL_OR(ki.is_objective_area) AS obj_area,
               MAX(cp.attacker_team) AS team,
               MAX(cp.axis_alive) AS axis_alive, MAX(cp.allies_alive) AS allies_alive
        FROM storytelling_kill_impact ki
        JOIN proximity_combat_position cp
          ON cp.round_start_unix = ki.round_start_unix
         AND UPPER(LEFT(cp.attacker_guid, 8)) = UPPER(LEFT(ki.killer_guid, 8))
         AND ABS(cp.event_time - ki.kill_time_ms) <= 300
        WHERE ki.session_date >= '2026-04-01'
          AND ki.killer_guid NOT LIKE 'OMNIBOT%'
          AND ki.killer_name NOT LIKE '[BOT]%'
          AND cp.axis_alive > 0 AND cp.allies_alive > 0
        GROUP BY ki.session_date, ki.round_start_unix, ki.round_number, ki.map_name,
                 UPPER(LEFT(ki.killer_guid, 8)), ki.kill_time_ms
        ORDER BY ki.round_start_unix, ki.kill_time_ms
    """)

    # R2 pressure context: time_to_beat = R1 actual duration of the same match
    ttb = {}
    for r in await conn.fetch("""
        SELECT r2.round_start_unix, r1.actual_duration_seconds
        FROM rounds r2 JOIN rounds r1
          ON r1.match_id = r2.match_id AND r1.round_number = 1
        WHERE r2.round_number = 2 AND r2.round_start_unix IS NOT NULL
          AND r1.actual_duration_seconds IS NOT NULL
    """):
        ttb[r[0]] = int(r[1])

    # round winner side for outcome_mult
    winner = {}
    for r in await conn.fetch("""
        SELECT round_start_unix, winner_team FROM rounds
        WHERE round_start_unix IS NOT NULL AND winner_team IN (1, 2)
    """):
        winner[r[0]] = int(r[1])

    # doc returns per round (any teammate of clutcher counts as team recovery)
    returns = defaultdict(list)
    for r in await conn.fetch("""
        SELECT round_start_unix, flag_team, return_time
        FROM proximity_carrier_return WHERE round_start_unix IS NOT NULL
    """):
        returns[r[0]].append((r[1], int(r[2] or 0)))

    # ---- chain detection: group per (round, killer) FIRST, then chain in time.
    # Chaining over the global chronological stream fragments a player's chain
    # whenever ANOTHER player's kill interleaves (owner error-check, 2026-07-06).
    by_killer: dict = defaultdict(list)
    for r in rows:
        side_alive = r["axis_alive"] if r["team"] == "AXIS" else r["allies_alive"]
        if side_alive != 1:
            continue
        by_killer[(r["round_start_unix"], r["g8"])].append(r)

    chains = []
    for _key, krows in by_killer.items():
        krows.sort(key=lambda r: r["kill_time_ms"])
        cur = None
        for r in krows:
            enemies = r["allies_alive"] if r["team"] == "AXIS" else r["axis_alive"]
            if cur and r["kill_time_ms"] - cur["t1"] <= CHAIN_WINDOW_MS:
                cur["kills"].append(r)
                cur["t1"] = r["kill_time_ms"]
                cur["max_enemies"] = max(cur["max_enemies"], enemies)
            else:
                cur = {"t0": r["kill_time_ms"], "t1": r["kill_time_ms"],
                       "kills": [r], "max_enemies": enemies, "meta": r}
                chains.append(cur)

    scored = []
    for c in chains:
        if len(c["kills"]) < 2:
            continue
        m = c["meta"]
        kis_sum = sum(float(k["kis"] or 0) for k in c["kills"])
        stake = 1.0
        if any(k["carrier"] for k in c["kills"]) or any(k["obj_area"] for k in c["kills"]):
            stake *= 1.5
        rsu = m["round_start_unix"]
        if m["round_number"] == 2 and rsu in ttb:
            remaining = ttb[rsu] - c["t1"] / 1000.0
            stake *= 1.0 + max(0.0, min(1.0, 1.0 - remaining / 120.0))
        side_num = 1 if m["team"] == "AXIS" else 2
        out = OUT_WIN if winner.get(rsu) == side_num else (
            OUT_LOSS if rsu in winner else 1.0)
        value = kis_sum * n_mult(c["max_enemies"]) * stake * out
        ret_note = ""
        for _fteam, rt in returns.get(rsu, []):
            if 0 <= rt - c["t1"] <= 30_000:
                value *= 1 + RETURN_BONUS
                ret_note = " +docs returned"
                break
        scored.append((value, m["session_date"], m["map_name"], m["round_number"],
                       m["name"], len(c["kills"]), c["max_enemies"],
                       (c["t1"] - c["t0"]) / 1000.0, kis_sum, stake, out, ret_note))

    scored.sort(reverse=True)
    print(f"chains(2+ kills as last man)={len(scored)}  | TOP 20:")
    print(f"{'val':>6} {'date':<11}{'map':<16}{'R':<2}{'player':<16}"
          f"{'k':>2}{'1vN':>4}{'span':>6}{'KIS':>6}{'stk':>5}{'out':>4}")
    for v, d, mp, rn, name, k, n, span, kis, stk, out, ret in scored[:20]:
        print(f"{v:>6.1f} {d!s:<11}{mp:<16}{rn:<2}{name[:15]:<16}"
              f"{k:>2}{'1v' + str(n):>4}{span:>5.1f}s{kis:>6.1f}{stk:>5.2f}{out:>4.1f}{ret}")

    await conn.close()

asyncio.run(main())
