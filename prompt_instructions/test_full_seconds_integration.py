#!/usr/bin/env python3
"""
Full Integration Test - Import Oct 2 with Seconds Parser
=========================================================
Tests the complete pipeline:
1. Parse files with seconds-based parser
2. Import to database
3. Verify time_played_seconds is populated
4. Check DPM calculations
"""
import sys
import sqlite3
sys.path.insert(0, '.')
from bot.community_stats_parser import C0RNP0RN3StatsParser
from datetime import datetime

parser = C0RNP0RN3StatsParser()
conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print('='*80)
print('🧪 FULL INTEGRATION TEST - October 2nd Import with Seconds')
print('='*80)

# Delete existing Oct 2 records
print('\n📋 Step 1: Clean existing October 2nd data')
c.execute("DELETE FROM player_comprehensive_stats WHERE session_id IN (SELECT id FROM sessions WHERE session_date LIKE '2025-10-02%')")
c.execute("DELETE FROM sessions WHERE session_date LIKE '2025-10-02%'")
conn.commit()
print(f"✅ Cleaned old Oct 2 data")

# Parse one Round 1 file
print('\n📋 Step 2: Parse Round 1 file')
test_file = 'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt'
result = parser.parse_stats_file(test_file)

if result['success']:
    print(f"✅ Parsed: {result['map_name']} Round {result['round_num']}")
    print(f"   Time: {result['actual_time']}")
    print(f"   Players: {len(result['players'])}")
    
    # Check one player
    vid = next((p for p in result['players'] if 'vid' in p['name'].lower()), None)
    if vid:
        print(f"\n   Player 'vid':")
        print(f"     time_played_seconds: {vid.get('time_played_seconds', 'MISSING')}")
        print(f"     time_display: {vid.get('time_display', 'MISSING')}")
        print(f"     DPM: {vid.get('dpm', 0):.2f}")

# Insert session
print('\n📋 Step 3: Insert into database')
c.execute('''
    INSERT INTO sessions (session_date, map_name, round_number, actual_time)
    VALUES (?, ?, ?, ?)
''', ('2025-10-02 21:18:08', result['map_name'], result['round_num'], result['actual_time']))

session_id = c.lastrowid

# Insert players
for player in result['players']:
    clean_name = player['name'].replace('^', '').replace(' ', '_')
    c.execute('''
        INSERT INTO player_comprehensive_stats
        (session_id, player_name, player_guid, clean_name, team, kills, deaths,
         damage_given, damage_received, dpm, time_played_minutes, time_played_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        session_id,
        player['name'],
        player.get('guid', 'UNKNOWN'),
        clean_name,
        player.get('team', 0),
        player.get('kills', 0),
        player.get('deaths', 0),
        player.get('damage_given', 0),
        player.get('damage_received', 0),
        player.get('dpm', 0.0),
        player.get('time_played_minutes', 0.0),
        player.get('time_played_seconds', 0)
    ))

conn.commit()
print(f"✅ Inserted {len(result['players'])} players")

# Verify database
print('\n📋 Step 4: Verify database')
rows = c.execute('''
    SELECT 
        p.player_name,
        p.damage_given,
        p.time_played_seconds,
        p.time_played_minutes,
        p.dpm,
        s.actual_time
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE p.player_name LIKE '%vid%'
    AND s.session_date LIKE '2025-10-02%'
''').fetchall()

print(f"\nDatabase records for 'vid':\n")
print(f"{'Player':<15} | {'Damage':>6} | {'Seconds':>7} | {'Minutes':>7} | {'DPM':>7} | {'Session'}")
print('-'*80)

for r in rows:
    print(f"{r[0]:<15} | {r[1]:>6} | {r[2]:>7} | {r[3]:>7.2f} | {r[4]:>7.2f} | {r[5]}")

# Critical checks
print('\n📋 Step 5: Critical Checks')
has_seconds = all(r[2] > 0 for r in rows)
print(f"  ✅ All records have time_played_seconds > 0: {has_seconds}")

# Check DPM calculation from database
if rows:
    r = rows[0]
    db_dpm = r[4]
    calculated_dpm = (r[1] * 60) / r[2] if r[2] > 0 else 0
    dpm_match = abs(db_dpm - calculated_dpm) < 0.01
    print(f"  DPM in DB: {db_dpm:.2f}")
    print(f"  DPM calculated: {calculated_dpm:.2f}")
    print(f"  ✅ DPM matches: {dpm_match}")

print('\n' + '='*80)
if has_seconds and dpm_match:
    print('🎉 SUCCESS! Seconds-based import working perfectly!')
    print('='*80)
    print('\n✅ Ready to:')
    print('  1. Import all October 2nd files')
    print('  2. Update bot queries')
    print('  3. Test !last_session command')
else:
    print('❌ ISSUES FOUND! Check the output above.')
    print('='*80)

conn.close()
