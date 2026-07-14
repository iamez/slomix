#!/usr/bin/env python3
"""Phase-0 backtest: Life Cards — "best life of the night" (READ-ONLY).

Good Night plan rank 9 (§H). A "life" is one spawn->death span (a player_track
row). The best-life card celebrates the standout single life of a session — the
rampage that people remember ("X got 6 before going down") — which a
session-total scoreboard flattens away.

v0 signal: kills landed DURING the life window, joined from
proximity_combat_position on the same round_start_unix + attacker_guid with
event_time inside [spawn_time_ms, death_time_ms]. Ranked by kills, then by a
tighter (shorter, more explosive) life. Bots excluded.

Proves-with-a-table that the metric surfaces memorable individual lives before
any endpoint/UI. No writes: SET default_transaction_read_only = on.
"""
import asyncio
import os
import sys

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from website.backend.utils.et_constants import strip_et_colors  # noqa: E402

# Rank lives by kills, then prefer the more explosive life (more kills per second
# of the life). A life must clear this bar to be a "card" at all.
MIN_KILLS = 3


async def main():
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
        WHERE spawn_time_ms IS NOT NULL AND death_time_ms IS NOT NULL
        GROUP BY session_date HAVING COUNT(*) >= 20
        ORDER BY session_date DESC LIMIT 10""")

    print("Life Cards v0 — best single life per session (kills landed within one spawn->death)")
    print(f"{'date':<11}{'lives':>6}{'≥3k':>5}  {'best life (player: kills in Ns on map)':<52} runner-up")
    print("-" * 116)

    for drow in dates:
        sd = drow["session_date"]
        # Each life with the kills it produced. Bots excluded on both sides.
        lives = await conn.fetch("""
            SELECT pt.player_name, pt.map_name, pt.round_number,
                   GREATEST(pt.death_time_ms - pt.spawn_time_ms, 0) AS life_ms,
                   k.kills
            FROM player_track pt
            JOIN LATERAL (
                SELECT COUNT(*) AS kills FROM proximity_combat_position cp
                WHERE cp.session_date = pt.session_date
                  AND cp.round_start_unix = pt.round_start_unix
                  AND cp.event_type = 'kill'
                  AND cp.attacker_guid = pt.player_guid
                  AND cp.attacker_team != cp.victim_team
                  AND cp.event_time BETWEEN pt.spawn_time_ms AND pt.death_time_ms
            ) k ON TRUE
            WHERE pt.session_date = $1
              AND pt.spawn_time_ms IS NOT NULL AND pt.death_time_ms IS NOT NULL
              AND pt.player_guid NOT LIKE 'OMNIBOT%' AND pt.player_name NOT LIKE '[BOT]%'
              AND k.kills >= $2
        """, sd, MIN_KILLS)

        total_lives = drow["n"]
        if not lives:
            print(f"{str(sd):<11}{total_lives:>6}{0:>5}  (no standout life)")
            continue

        def _rank(r):
            # more kills first; then the tighter life (kills per second)
            life_s = max((r["life_ms"] or 0) / 1000.0, 1.0)
            return (r["kills"], r["kills"] / life_s)

        ordered = sorted(lives, key=_rank, reverse=True)

        def _fmt(r):
            name = strip_et_colors(r["player_name"] or "?")
            life_s = round((r["life_ms"] or 0) / 1000.0)
            return f"{name}: {r['kills']}k in {life_s}s on {r['map_name']}"

        best = _fmt(ordered[0])
        runner = _fmt(ordered[1]) if len(ordered) > 1 else ""
        print(f"{str(sd):<11}{total_lives:>6}{len(lives):>5}  {best[:52]:<52} {runner[:40]}")

    await conn.close()


asyncio.run(main())
