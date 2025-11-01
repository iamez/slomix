#!/usr/bin/env python3
"""
🎯 QUICK DPM DEBUG SUMMARY
==========================
Run this to see the DPM issue in simple terms
"""

import sqlite3

db = 'etlegacy_production.db'
conn = sqlite3.connect(db)
c = conn.cursor()

print("=" * 80)
print("🔍 DPM CALCULATION - WHY THE VALUES ARE WRONG")
print("=" * 80)

# Get latest session
c.execute('SELECT DISTINCT session_date FROM sessions ORDER BY session_date DESC LIMIT 1')
date = c.fetchone()[0]

print(f"\n📅 Latest Session: {date}")

# Get top player by kills
c.execute(
    f'''
    SELECT
        p.player_name,
        SUM(p.kills) as kills,
        AVG(p.dpm) as bot_dpm,
        COUNT(*) as rounds,
        SUM(p.damage_given) as total_damage
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE s.session_date = ?
    GROUP BY p.player_name
    ORDER BY kills DESC
    LIMIT 1
''',
    (date,),
)

name, kills, bot_dpm, rounds, damage = c.fetchone()

print(f"\n👤 Top Player: {name}")
print(f"   Kills: {kills}")
print(f"   Rounds: {rounds}")
print(f"   Total Damage: {damage:,}")
print(f"\n   🤖 Bot shows: {bot_dpm:.2f} DPM")
print(f"   ⚠️  This is AVG(dpm) across {rounds} rounds")

# Show per-round breakdown
print(f"\n   📊 Per-Round Breakdown:")
c.execute(
    f'''
    SELECT
        s.map_name,
        s.round_number,
        s.actual_time,
        p.damage_given,
        p.dpm
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE s.session_date = ? AND p.player_name = ?
    ORDER BY s.map_name, s.round_number
''',
    (date, name),
)

for map_name, rnd, actual_time, dmg, dpm in c.fetchall():
    indicator = "❌" if actual_time == "0:00" else "✅"
    print(f"      {indicator} {map_name} R{rnd}: {dmg} damage, {dpm:.1f} DPM (time: {actual_time})")

print("\n" + "=" * 80)
print("💡 THE PROBLEM:")
print("=" * 80)
print(
    """
When actual_time = 0:00 (Round 2 files):
- We CAN'T calculate what the DPM should be
- But c0rnp0rn3.lua already calculated it correctly
- The bot uses AVG(dpm) which is mathematically wrong

Example:
  Round 1: 10 minutes, 2500 damage → 250 DPM ✅
  Round 2: 5 minutes, 2000 damage → 400 DPM ✅

  Bot calculates: (250 + 400) / 2 = 325 DPM ❌ WRONG
  Should be: (2500 + 2000) / (10 + 5) = 300 DPM ✅

The bot needs to calculate: SUM(damage) / SUM(time_played)
But we don't store time_played_minutes in the database!

FIX: Add time_played_minutes column and use weighted average.
"""
)

print("\n📄 Full analysis: FINDINGS_DPM_CALCULATION.md")

conn.close()
