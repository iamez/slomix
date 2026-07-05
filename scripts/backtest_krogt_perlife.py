#!/usr/bin/env python3
"""Phase-0 backtest: per-LIFE KROGT (read-only, dev DB).

A "life" = one player_track row (spawn_time_ms -> death_time_ms) — the
tracker records EVERY life including selfkill/world/team deaths, which
kill_outcome (enemy kills only) misses (codex P2, PR #441). A life COUNTS
when >=1 contribution happened during it: Kill (combat_position attacker),
Revive given (proximity_revive medic), Objective action (objective_run
engineer), Gib (kill_outcome gibber), or the death ending it was Traded
(lua_trade_kill original victim). This is the ET translation of KAST/KOST,
where CS/R6 "round" == one life.

Usage: PGPASSWORD=... python3 scripts/backtest_krogt_perlife.py  (READ-ONLY)

Findings (dev, 2026-07-05, 373 covered rounds / last 25 sessions, 13 players
>= 100 lives, player_track lives):
- per-life KROGT DISCRIMINATES where per-round saturated: 52.1%-64.7%
  (pro CS KAST band is ~70-75% -- ours is stricter, no free "survived"
  credit: even the survived-to-end life still needs a contribution).
- Adds signal beyond DPM: e.g. immoo{ ranked top on per-round revive rate
  (87%) but lands near-last per-life -- a different play shape, not volume.
- Switching life boundaries from kill_outcome deaths to player_track rows
  (includes selfkill/world/team deaths) raised life counts 10-30% and
  corrected selfkill-heavy players DOWN (e.g. .olz 58.0% -> 55.0%).
Limitations (v0): lives only from proximity-covered rounds with tracks
(336/373 here); traded credit matches the life end within +/-1s (different
Lua clocks).
"""
import os
import sys
from collections import defaultdict

import psycopg2

conn = psycopg2.connect(
    host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
    port=int(os.environ.get("POSTGRES_PORT", "5432")),
    dbname=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
    user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
    password=os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PGPASSWORD", ""),
)
cur = conn.cursor()
# Enforce the read-only promise at the session level — an accidental write
# raises instead of committing.
cur.execute("SET default_transaction_read_only = on")

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
if not rids:
    # Postgres rejects `IN ()` — bail out cleanly on an empty/uncovered DB.
    print("no proximity-covered rounds in scope — nothing to backtest")
    sys.exit(0)

def fetch(q, params=()):
    cur.execute(q, params)
    return cur.fetchall()

g8 = "UPPER(LEFT(%s, 8))"
# Lives: one player_track row per spawn->death window (includes selfkills)
tracks = fetch(f"""
    SELECT round_id, {g8 % 'player_guid'}, spawn_time_ms, death_time_ms
    FROM player_track WHERE round_id IN %s AND player_guid IS NOT NULL
""", (rids,))
traded_by = defaultdict(list)  # (rid, guid8) -> traded death times
for rid, gg, kt in fetch(f"""
    SELECT round_id, {g8 % 'original_victim_guid'}, original_kill_time
    FROM proximity_lua_trade_kill WHERE round_id IN %s
""", (rids,)):
    if kt is not None:
        traded_by[(rid, gg)].append(int(kt))
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
      -- defensive: the Lua can log denied approaches; dying near an objective
      -- must not earn O credit (0 such rows on dev today, but cheap to guard)
      AND COALESCE(action_type, '') <> 'approach_killed'
      AND COALESCE(run_type, '') <> 'denied'
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

ev_by = defaultdict(list)
for rid, gg, t in events:
    if gg in names and t is not None:
        ev_by[(rid, gg)].append(int(t))

lives_by = defaultdict(list)  # (rid, guid8) -> [(spawn_ms, death_ms), ...]
for rid, gg, spawn_ms, death_ms in tracks:
    if gg not in names:
        continue
    lo = int(spawn_ms or 0)
    hi = int(death_ms) if death_ms is not None else round_end.get(rid, 0)
    if hi > lo:
        lives_by[(rid, gg)].append((lo, hi))

stats = defaultdict(lambda: [0, 0, 0])  # guid -> [lives, contributing_lives, traded_lives]
for (rid, gg), windows in lives_by.items():
    windows.sort()
    evs = sorted(ev_by.get((rid, gg), []))
    traded_times = sorted(traded_by.get((rid, gg), []))
    ei = 0  # windows and evs are both sorted — advance one index, O(lives+events)
    for lo, hi in windows:
        stats[gg][0] += 1
        while ei < len(evs) and evs[ei] <= lo:
            ei += 1
        contributed = ei < len(evs) and evs[ei] <= hi
        # a life ended by a TRADED death counts; player_track death_time_ms and
        # lua_trade_kill original_kill_time come from different Lua clocks, so
        # match within +/-1s of the life's end
        if not contributed and any(abs(t - hi) <= 1000 for t in traded_times):
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
