#!/usr/bin/env python3
"""Check Erdenberg stats for October 2 to investigate olz's 800 DPM"""

import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print('\n' + '='*80)
print('ERDENBERG - October 2, 2025 - DPM Investigation')
print('='*80 + '\n')

# Get all Erdenberg sessions on Oct 2
c.execute("""
    SELECT 
        s.id,
        s.map_name, 
        s.round_number,
        s.actual_time,
        p.clean_name,
        p.kills,
        p.deaths,
        p.damage_given,
        p.dpm,
        p.time_played_minutes,
        p.time_played_seconds
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE s.session_date = '2025-10-02' 
    AND s.map_name LIKE '%erdenberg%'
    ORDER BY s.round_number, p.dpm DESC
""")

results = c.fetchall()

if not results:
    print("❌ No Erdenberg data found for October 2, 2025")
else:
    current_round = None
    
    for row in results:
        session_id, map_name, round_num, actual_time, player, kills, deaths, damage, dpm, time_min, time_sec = row
        
        # Print round header
        if current_round != round_num:
            if current_round is not None:
                print()
            print(f"\n{'='*80}")
            print(f"📍 {map_name} - Round {round_num}")
            print(f"⏱️  Map Duration: {actual_time}")
            print(f"🆔 Session ID: {session_id}")
            print('='*80)
            print(f"{'Player':<20} {'K/D':>8} {'Damage':>8} {'DPM':>8} {'Time(m)':>10} {'Time(s)':>10}")
            print('-'*80)
            current_round = round_num
        
        # Print player stats
        kd_str = f"{kills}/{deaths}"
        print(f"{player:<20} {kd_str:>8} {damage:>8} {dpm:>8.1f} {time_min:>10.1f} {time_sec:>10}")
        
        # Highlight olz
        if 'olz' in player.lower():
            print(f"  ⭐ {'='*74}")
            print(f"  ⭐ OLZ FOUND! DPM: {dpm:.1f}")
            print(f"  ⭐ Calculation: {damage} damage ÷ {time_min:.2f} minutes = {dpm:.1f} DPM")
            if time_sec:
                actual_dpm = (damage * 60) / time_sec if time_sec > 0 else 0
                print(f"  ⭐ Using seconds: {damage} × 60 ÷ {time_sec} = {actual_dpm:.1f} DPM")
            print(f"  ⭐ {'='*74}")

print('\n' + '='*80)
print('SUMMARY - Why is olz only in Round 2?')
print('='*80)

# Check who was in Round 1
print("\n🔍 ALL PLAYERS IN ROUND 1:")
c.execute("""
    SELECT clean_name
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE s.session_date = '2025-10-02' 
    AND s.map_name LIKE '%erdenberg%'
    AND s.round_number = 1
    ORDER BY clean_name
""")
round1_players = [r[0] for r in c.fetchall()]
print(f"  Total: {len(round1_players)} players")
for player in round1_players:
    print(f"    - {player}")

# Check who was in Round 2
print("\n🔍 ALL PLAYERS IN ROUND 2:")
c.execute("""
    SELECT clean_name
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE s.session_date = '2025-10-02' 
    AND s.map_name LIKE '%erdenberg%'
    AND s.round_number = 2
    ORDER BY clean_name
""")
round2_players = [r[0] for r in c.fetchall()]
print(f"  Total: {len(round2_players)} players")
for player in round2_players:
    print(f"    - {player}")

# Find who joined/left between rounds
round1_set = set(round1_players)
round2_set = set(round2_players)

joined_r2 = round2_set - round1_set
left_r2 = round1_set - round2_set

if joined_r2:
    print(f"\n✅ JOINED in Round 2 (weren't in Round 1):")
    for player in joined_r2:
        print(f"    + {player}")

if left_r2:
    print(f"\n❌ LEFT after Round 1 (not in Round 2):")
    for player in left_r2:
        print(f"    - {player}")

print('\n' + '='*80)

# Get olz specific stats
c.execute("""
    SELECT 
        s.round_number,
        s.actual_time,
        p.damage_given,
        p.dpm,
        p.time_played_minutes,
        p.time_played_seconds
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE s.session_date = '2025-10-02' 
    AND s.map_name LIKE '%erdenberg%'
    AND p.clean_name LIKE '%olz%'
    ORDER BY s.round_number
""")

olz_stats = c.fetchall()

if olz_stats:
    print("\n🎯 OLZ's Erdenberg Performance:")
    for round_num, actual_time, damage, dpm, time_min, time_sec in olz_stats:
        print(f"\n  Round {round_num}:")
        print(f"    Map Duration: {actual_time}")
        print(f"    Damage Given: {damage:,}")
        print(f"    DPM: {dpm:.1f}")
        print(f"    Time Played: {time_min:.1f} minutes ({time_sec} seconds)")
        
        if time_sec and time_sec > 0:
            calculated_dpm = (damage * 60) / time_sec
            print(f"    Calculated DPM (from seconds): {calculated_dpm:.1f}")
            
            if abs(dpm - calculated_dpm) > 1:
                print(f"    ⚠️  MISMATCH! Stored DPM ({dpm:.1f}) != Calculated ({calculated_dpm:.1f})")
else:
    print("\n❌ No data found for olz on Erdenberg")

conn.close()
print()
