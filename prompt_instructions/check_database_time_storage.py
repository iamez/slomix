#!/usr/bin/env python3
"""Check what's stored in database for October 2nd"""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print('='*80)
print('DATABASE STORAGE - October 2nd, 2025')
print('='*80)

rows = c.execute('''
    SELECT 
        p.player_name,
        p.damage_given,
        p.time_played_minutes,
        p.dpm,
        s.actual_time,
        s.map_name,
        s.round_number
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE s.session_date LIKE "2025-10-02%"
    AND p.player_name LIKE "%vid%"
    ORDER BY s.session_date
''').fetchall()

print(f"\nFound {len(rows)} records for vid:\n")
print(f"{'Player':<15} | {'Damage':>6} | {'Time(min)':>9} | {'DPM':>7} | {'Session':>12} | {'Map':<15} | {'Round'}")
print('-'*90)

for r in rows:
    print(f"{r[0]:<15} | {r[1]:>6} | {r[2]:>9.2f} | {r[3]:>7.2f} | {r[4]:>12} | {r[5]:<15} | R{r[6]}")

print('\n' + '='*80)
print('🔍 ANALYSIS:')
print('='*80)

zero_time = sum(1 for r in rows if r[2] == 0.0)
print(f"Records with time_played_minutes = 0: {zero_time}/{len(rows)}")

if zero_time > 0:
    print("\n❌ PROBLEM: time_played_minutes is 0 in database!")
    print("   This happens because parser reads Tab[22] which is always 0.0")
    print("   Should read Tab[23] instead (or use session time)")
else:
    print("\n✅ All records have valid time_played_minutes!")

conn.close()
