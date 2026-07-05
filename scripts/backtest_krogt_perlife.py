#!/usr/bin/env python3
"""Phase-0 backtest: per-LIFE KROGT (read-only, dev DB).

A "life" = spawn->death window, segmented by the player's own deaths in
proximity_kill_outcome (plus one survived-to-round-end life). A life COUNTS
when >=1 contribution happened during it: Kill (combat_position attacker),
Revive given (proximity_revive medic), Objective action (objective_run
engineer), Gib (kill_outcome gibber), or the death ending it was Traded
(lua_trade_kill original victim). This is the ET translation of KAST/KOST,
where CS/R6 "round" == one life.

Usage: PGPASSWORD=... python3 scripts/backtest_krogt_perlife.py  (READ-ONLY)

First-run findings (dev, 2026-07-05, 373 covered rounds / last 25 sessions,
13 players >= 100 lives):
- per-life KROGT DISCRIMINATES where per-round saturated: 52.6%-67.7%
  (vid/bronze ~64-65%, tail ~53-55%; pro CS KAST band is ~70-75% -- ours is
  stricter, no free "survived" credit: even the survived-to-end life still
  needs a contribution).
- Adds signal beyond DPM: e.g. immoo{ ranked top on per-round revive rate
  (87%) but lands last per-life -- a different play shape, not just volume.
- Traded-death credit is real but small (12-185 saved lives per player).
Limitations (v0): lives only from proximity-covered rounds (~66%); the
survived-to-end life is counted even for late joiners; traded credit keys
on exact original_kill_time match. Life accounting is seeded from ALL PCS
player-rounds, so zero-death rounds contribute their survived life (rare in
ET — rerun shifted totals by only +1-4 lives/player, ordering unchanged).
"""
import os
from collections import defaultdict

import psycopg2

conn = psycopg2.connect(
    host="127.0.0.1", port=5432, dbname="etlegacy",
    user="etlegacy_user", password=os.environ.get("PGPASSWORD", ""),
)
cur = conn.cursor()

# Covered, played rounds of the last 25 sessions (same scope as round-level backtest)
cur.execute("""
    WITH ls AS (
      SELECT DISTINCT gaming_session_id AS gsid FROM rounds
      WHERE is_valid IS DISTINCT FROM FALSE AND gaming_session_id IS NOT NULL
        AND round_number IN (1, 2)
      ORDER BY gsid DESC LIMIT 25
    )
    SELECT r.id, COALESCE(r.actual_duration_seconds, 0) * 1000
    FROM rounds r
    WHERE r.gaming_session_id IN (SELECT gsid FROM ls)
      AND r.is_valid IS DISTINCT FROM FALSE AND r.round_number IN (1, 2)
      AND EXISTS (SELECT 1 FROM proximity_kill_outcome ko WHERE ko.round_id = r.id)
""")
round_end = {rid: int(end_ms) for rid, end_ms in cur.fetchall()}
rids = tuple(round_end.keys())
print(f"covered rounds: {len(rids)}")

def fetch(q, params=()):
    cur.execute(q, params)
    return cur.fetchall()

g8 = "UPPER(LEFT(%s, 8))"
# Deaths per (player, round): life segmentation + traded flag per death
deaths = fetch(f"""
    SELECT round_id, {g8 % 'victim_guid'}, kill_time
    FROM proximity_kill_outcome WHERE round_id IN %s AND victim_guid IS NOT NULL
""", (rids,))
traded_deaths = {
    (rid, gg, kt) for rid, gg, kt in fetch(f"""
        SELECT round_id, {g8 % 'original_victim_guid'}, original_kill_time
        FROM proximity_lua_trade_kill WHERE round_id IN %s
    """, (rids,))
}
events = []  # (round_id, guid8, time_ms) contribution events
events += fetch(f"""
    SELECT round_id, {g8 % 'attacker_guid'}, event_time FROM proximity_combat_position
    WHERE round_id IN %s AND attacker_guid IS NOT NULL AND attacker_team <> victim_team
""", (rids,))
events += fetch(f"""
    SELECT round_id, {g8 % 'medic_guid'}, revive_time FROM proximity_revive
    WHERE round_id IN %s AND medic_guid IS NOT NULL
""", (rids,))
events += fetch(f"""
    SELECT round_id, {g8 % 'engineer_guid'}, action_time FROM proximity_objective_run
    WHERE round_id IN %s AND engineer_guid IS NOT NULL
""", (rids,))
events += fetch(f"""
    SELECT round_id, {g8 % 'gibber_guid'}, outcome_time FROM proximity_kill_outcome
    WHERE round_id IN %s AND outcome = 'gibbed' AND gibber_guid IS NOT NULL
""", (rids,))

# Names (display), bots excluded
names = dict(fetch("""
    SELECT UPPER(LEFT(player_guid, 8)), MAX(player_name)
    FROM player_comprehensive_stats p JOIN rounds r ON r.id = p.round_id
    WHERE r.id IN %s AND player_guid NOT LIKE 'OMNIBOT%%' AND player_name NOT LIKE '[BOT]%%'
    GROUP BY UPPER(LEFT(player_guid, 8))
""", (rids,)))

# Seed life accounting from ALL player-rounds (PCS), not just rounds where the
# player died — otherwise a zero-death round contributes no survived-to-end
# life at all and full-round survivors drop out of both numerator and
# denominator (codex P2, PR #441).
player_rounds = fetch("""
    SELECT DISTINCT p.round_id, UPPER(LEFT(p.player_guid, 8))
    FROM player_comprehensive_stats p
    WHERE p.round_id IN %s
      AND p.player_guid NOT LIKE 'OMNIBOT%%' AND p.player_name NOT LIKE '[BOT]%%'
""", (rids,))

deaths_by = defaultdict(list)
for rid, gg, kt in deaths:
    if gg in names and kt is not None:
        deaths_by[(rid, gg)].append(int(kt))
ev_by = defaultdict(list)
for rid, gg, t in events:
    if gg in names and t is not None:
        ev_by[(rid, gg)].append(int(t))

stats = defaultdict(lambda: [0, 0, 0])  # guid -> [lives, contributing_lives, traded_lives]
for rid, gg in player_rounds:
    if gg not in names:
        continue
    dts = sorted(deaths_by.get((rid, gg), []))
    end = max(round_end.get(rid, 0), dts[-1] if dts else 0)
    bounds = [0, *dts, end]  # life i = (bounds[i], bounds[i+1]]
    evs = sorted(ev_by.get((rid, gg), []))
    for i in range(len(bounds) - 1):
        lo, hi = bounds[i], bounds[i + 1]
        if hi <= lo:
            continue
        stats[gg][0] += 1
        contributed = any(lo < t <= hi for t in evs)
        # a life ended by a TRADED death counts (i < len(dts) means it ended in a death)
        if not contributed and i < len(dts) and (rid, gg, dts[i]) in traded_deaths:
            contributed = True
            stats[gg][2] += 1
        if contributed:
            stats[gg][1] += 1

rows = [
    (names[gg], lives, 100.0 * contrib / lives, traded)
    for gg, (lives, contrib, traded) in stats.items() if lives >= 100
]
rows.sort(key=lambda r: -r[2])
print(f"{'player':<22}{'lives':>7}{'KROGT/life %':>14}{'traded-save':>12}")
for name, lives, pct, traded in rows:
    print(f"{name:<22}{lives:>7}{pct:>13.1f}%{traded:>12}")

cur.close()
conn.close()
