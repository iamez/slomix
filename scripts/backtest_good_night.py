#!/usr/bin/env python3
"""Phase-0 backtest: Good Night Index v0 (READ-ONLY, plan §Algorithm family 1).

good_night = .25*balance + .20*tension + .15*attendance + .15*story_density
           + .10*flow + .10*variety + .05*participation
"""
import asyncio
import datetime as dt
import json
import os

import asyncpg


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


async def main():
    conn = await asyncpg.connect(
        host="127.0.0.1", port=5432, database="etlegacy",
        user="etlegacy_user", password=os.environ.get("PGPASSWORD", ""))
    await conn.execute("SET default_transaction_read_only = on")

    sess = await conn.fetch("""
        SELECT gaming_session_id AS gsid, MIN(SUBSTRING(round_date,1,10)) AS d
        FROM rounds WHERE gaming_session_id IS NOT NULL AND is_valid AND round_number IN (1,2)
        GROUP BY gaming_session_id HAVING COUNT(*) >= 4
        ORDER BY gsid DESC LIMIT 20""")

    print(f"{'gsid':>5} {'date':<11}{'GN':>4} | {'bal':>4}{'ten':>4}{'att':>4}{'sto':>4}{'flo':>4}{'var':>4}{'par':>4} | opis")
    for gsid, d in sess:
        # rounds of the session (valid, played)
        rounds = await conn.fetch("""
            SELECT round_number, match_id, map_name, COALESCE(actual_duration_seconds,0) AS secs,
                   round_start_unix
            FROM rounds WHERE gaming_session_id=$1 AND is_valid AND round_status='completed'
              AND round_number IN (1,2) ORDER BY round_start_unix""", gsid)
        pairs = {}
        for r in rounds:
            pairs.setdefault(r["match_id"], {})[r["round_number"]] = r
        matches = [p for p in pairs.values() if 1 in p and 2 in p]
        n_maps = len(matches)
        if n_maps == 0:
            continue

        # session_results (post-backfill BOX scale)
        sr = await conn.fetchrow(
            "SELECT team_1_score, team_2_score, round_details FROM session_results "
            "WHERE gaming_session_id=$1 ORDER BY id DESC LIMIT 1", gsid)
        wins_a = wins_b = draws = 0
        if sr and sr["round_details"]:
            for m in json.loads(sr["round_details"]):
                if m.get("counted") is False:
                    continue
                pa = int(m.get("team_a_points", m.get("team1_points", 0)) or 0)
                pb = int(m.get("team_b_points", m.get("team2_points", 0)) or 0)
                if pa > pb:
                    wins_a += 1
                elif pb > pa:
                    wins_b += 1
                else:
                    draws += 1

        # --- balance ---
        map_closeness = 100 - min(100, abs(wins_a - wins_b) * 25)
        diffs = [abs(p[2]["secs"] - p[1]["secs"]) for p in
                 [{1: m[1], 2: m[2]} for m in matches]]
        round_closeness = (sum(100 - min(100, dd / 6) for dd in diffs) / len(diffs)) if diffs else 50
        balance = 0.6 * map_closeness + 0.4 * round_closeness

        # --- tension ---
        close_maps = sum(1 for dd in diffs if dd <= 30)
        stomp_maps = sum(1 for dd in diffs if dd >= 240)
        decider = 15 if abs(wins_a - wins_b) <= 1 else 0
        tension = clamp(close_maps * 18 + draws * 22 + decider - stomp_maps * 12)

        # --- attendance ---
        players = await conn.fetchval("""
            SELECT COUNT(DISTINCT p.player_guid) FROM player_comprehensive_stats p
            JOIN rounds r ON r.id=p.round_id
            WHERE r.gaming_session_id=$1 AND r.is_valid
              AND p.player_guid NOT LIKE 'OMNIBOT%' AND p.player_name NOT LIKE '[BOT]%'""", gsid)
        attendance = 100 if players >= 10 else 85 if players >= 8 else 70 if players >= 6 else 45

        # --- hours ---
        t0 = min(r["round_start_unix"] for r in rounds if r["round_start_unix"])
        t1 = max(r["round_start_unix"] + r["secs"] for r in rounds if r["round_start_unix"])
        hours = max(0.5, (t1 - t0) / 3600.0)

        # --- story density: high-impact kills (KIS spikes) + carrier kills per hour ---
        moments = await conn.fetchval("""
            SELECT COUNT(*) FROM storytelling_kill_impact
            WHERE session_date=$1 AND (total_impact >= 3.0 OR is_carrier_kill)""",
            dt.date.fromisoformat(d))
        story = clamp((moments or 0) / hours * 18 / 4)  # /4: KIS-spike proxy is denser than curated moments

        # --- flow ---
        invalid = await conn.fetchval(
            "SELECT COUNT(*) FROM rounds WHERE gaming_session_id=$1 AND is_valid IS FALSE", gsid)
        starts = sorted(r["round_start_unix"] for r in rounds if r["round_start_unix"])
        long_gaps = sum(1 for a, b in zip(starts, starts[1:]) if b - a > 25 * 60)
        flow = clamp(100 - (invalid or 0) * 20 - long_gaps * 10)

        # --- variety ---
        distinct_maps = len({m[1]["map_name"] for m in matches})
        both_won = 10 if (wins_a > 0 and wins_b > 0) else 0
        variety = clamp(distinct_maps * 18 + both_won)

        # --- participation ---
        votes = await conn.fetchval(
            "SELECT COUNT(*) FROM session_mvp_votes WHERE gaming_session_id=$1", gsid) or 0
        bets = await conn.fetchval("""
            SELECT COUNT(*) FROM parimutuel_bets b JOIN parimutuel_markets m ON m.id=b.market_id
            WHERE m.gaming_session_id=$1""", gsid) or 0
        participation = clamp((votes + bets) * 10)

        gn = (0.25 * balance + 0.20 * tension + 0.15 * attendance + 0.15 * story
              + 0.10 * flow + 0.10 * variety + 0.05 * participation)
        desc = f"{n_maps} maps ({wins_a}-{wins_b}" + (f"+{draws}d" if draws else "") + f"), {players}p, {hours:.1f}h, {moments}mom"
        print(f"{gsid:>5} {d:<11}{gn:>4.0f} | {balance:>4.0f}{tension:>4.0f}{attendance:>4.0f}{story:>4.0f}{flow:>4.0f}{variety:>4.0f}{participation:>4.0f} | {desc}")

    await conn.close()

asyncio.run(main())
