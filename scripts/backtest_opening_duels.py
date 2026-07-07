#!/usr/bin/env python3
"""New formula candidates (owner B6 mandate: "izmisli še kake formule").

READ-ONLY backtest, tables before surfaces (owner rule). Two candidates the
comp scene has proven and our data supports natively:

OPENING DUELS — the FIRST kill of a round sets the man-advantage tone
(CS/Valorant "entry" stat). From storytelling_kill_impact ordering per round:
    opening_kill_rate  = rounds where player scored the round's first kill
    opening_death_rate = rounds where player WAS the round's first victim
    opening_net        = (openings won - openings lost) / rounds present
Group-relative; a player can be great mid-round but a liability in openings —
invisible in K/D, visible here.

TRADE DISCIPLINE — dying is part of stopwatch; dying UNTRADED while your
team is alive is the real cost. Deaths from proximity_kill_outcome (victim
side), avenged deaths from proximity_lua_trade_kill (original_victim):
    traded_death_share = deaths avenged within the trade window / deaths
Complements kill-side KIS: this is the TEAM-PLAY view of your deaths.

Both: bot + is_valid gated, min-sample thresholds, tie-aware group table.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
from collections import defaultdict

import asyncpg

FORMULA_VERSION = "duels-v0.1"
MIN_ROUNDS_PRESENT = 30
MIN_DEATHS = 30

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

    # ---- opening duels ------------------------------------------------------
    # first kill per (round_start_unix, round_number) by kill_time_ms; rounds
    # with unknown identity (rsu=0) excluded — they conflate rounds
    openings = await conn.fetch("""
        SELECT DISTINCT ON (ki.round_start_unix, ki.round_number)
               ki.round_start_unix, ki.round_number,
               UPPER(LEFT(ki.killer_guid, 8)) AS killer,
               UPPER(LEFT(ki.victim_guid, 8)) AS victim
        FROM storytelling_kill_impact ki
        LEFT JOIN rounds r ON r.round_start_unix = ki.round_start_unix
                          AND r.round_number = ki.round_number
        WHERE ki.round_start_unix > 0
          AND (r.id IS NULL OR r.is_valid)
          AND ki.killer_guid NOT LIKE 'OMNIBOT%'
          AND ki.victim_guid NOT LIKE 'OMNIBOT%'
          AND ki.killer_name NOT LIKE '[BOT]%'
          AND COALESCE(ki.victim_name, '') NOT LIKE '[BOT]%'
        ORDER BY ki.round_start_unix, ki.round_number, ki.kill_time_ms
    """)

    # rounds present per player (denominator): distinct rounds with any kill
    # involvement in kill_impact — pragmatic presence proxy for this source
    # denominator carries the SAME is_valid + bot gates as the numerator —
    # a mismatched presence count would silently dilute/inflate the rates
    presence_rows = await conn.fetch("""
        SELECT g8, COUNT(*) FROM (
            SELECT UPPER(LEFT(ki.killer_guid, 8)) AS g8,
                   ki.round_start_unix, ki.round_number
            FROM storytelling_kill_impact ki
            LEFT JOIN rounds r ON r.round_start_unix = ki.round_start_unix
                              AND r.round_number = ki.round_number
            WHERE ki.round_start_unix > 0 AND (r.id IS NULL OR r.is_valid)
              AND ki.killer_name NOT LIKE '[BOT]%'
            UNION
            SELECT UPPER(LEFT(ki.victim_guid, 8)),
                   ki.round_start_unix, ki.round_number
            FROM storytelling_kill_impact ki
            LEFT JOIN rounds r ON r.round_start_unix = ki.round_start_unix
                              AND r.round_number = ki.round_number
            WHERE ki.round_start_unix > 0 AND (r.id IS NULL OR r.is_valid)
              AND COALESCE(ki.victim_name, '') NOT LIKE '[BOT]%'
        ) x WHERE g8 NOT LIKE 'OMNIBOT%' GROUP BY g8
    """)
    presence = {r[0]: int(r[1]) for r in presence_rows}

    names = {r[0]: _clean(r[1]) for r in await conn.fetch("""
        SELECT UPPER(LEFT(player_guid, 8)), MAX(player_name)
        FROM player_comprehensive_stats
        WHERE player_guid NOT LIKE 'OMNIBOT%' AND player_name NOT LIKE '[BOT]%'
        GROUP BY 1""")}

    ok = defaultdict(int)
    od = defaultdict(int)
    for r in openings:
        ok[r["killer"]] += 1
        od[r["victim"]] += 1

    duel_rows = []
    for g8, n in presence.items():
        if n < MIN_ROUNDS_PRESENT or g8 not in names:
            continue
        wins, losses = ok.get(g8, 0), od.get(g8, 0)
        duel_rows.append({
            "g8": g8, "name": names[g8], "rounds": n,
            "ok_rate": wins / n, "od_rate": losses / n,
            "net": (wins - losses) / n,
        })
    duel_rows.sort(key=lambda r: -r["net"])

    print(f"=== OPENING DUELS  {FORMULA_VERSION} ===")
    print(f"SAMPLE: openings={len(openings)} players={len(duel_rows)} "
          f"(>= {MIN_ROUNDS_PRESENT} rounds present)")
    print(f"{'player':<16}{'rounds':>7} | {'open-K%':>8}{'open-D%':>8}{'net':>8}")
    for r in duel_rows:
        print(f"{r['name'][:15]:<16}{r['rounds']:>7} | "
              f"{100 * r['ok_rate']:>7.1f}%{100 * r['od_rate']:>7.1f}%"
              f"{100 * r['net']:>+7.1f}%")

    # ---- trade discipline ---------------------------------------------------
    deaths_rows = await conn.fetch("""
        SELECT UPPER(LEFT(ko.victim_guid, 8)) AS g8, COUNT(*) AS deaths
        FROM proximity_kill_outcome ko
        LEFT JOIN rounds r ON r.id = ko.round_id
        WHERE (r.id IS NULL OR r.is_valid)
          AND ko.victim_guid NOT LIKE 'OMNIBOT%'
          AND ko.victim_name NOT LIKE '[BOT]%'
        GROUP BY UPPER(LEFT(ko.victim_guid, 8))
        HAVING COUNT(*) >= $1
    """, MIN_DEATHS)
    # DISTINCT deaths, not trade rows: several teammates can avenge the
    # same death and each writes a trade row (codex, PR #467)
    avenged = {r[0]: int(r[1]) for r in await conn.fetch("""
        SELECT UPPER(LEFT(tk.original_victim_guid, 8)),
               COUNT(DISTINCT (tk.round_start_unix, tk.original_kill_time))
        FROM proximity_lua_trade_kill tk
        LEFT JOIN rounds r ON r.id = tk.round_id
        WHERE (r.id IS NULL OR r.is_valid)
          AND tk.original_victim_guid IS NOT NULL
          AND tk.original_victim_guid NOT LIKE 'OMNIBOT%'
        GROUP BY 1""")}
    trades = [
        {"g8": r["g8"], "deaths": int(r["deaths"]),
         "traded": min(avenged.get(r["g8"], 0), int(r["deaths"]))}
        for r in deaths_rows
    ]

    td_rows = sorted(
        ({"name": names.get(r["g8"], r["g8"]), "deaths": r["deaths"],
          "share": r["traded"] / r["deaths"]} for r in trades
         if r["g8"] in names),
        key=lambda x: -x["share"])

    print("\n=== TRADE DISCIPLINE (deaths avenged in trade window) ===")
    print(f"SAMPLE: players={len(td_rows)} (>= {MIN_DEATHS} deaths)")
    print(f"{'player':<16}{'deaths':>7}{'traded%':>9}")
    for r in td_rows:
        print(f"{r['name'][:15]:<16}{r['deaths']:>7}{100 * r['share']:>8.1f}%")

    await conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
