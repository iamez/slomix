#!/usr/bin/env python3
"""Check qmr's actual death time values - before and after fix."""

import sqlite3
import os
from bot.community_stats_parser import C0RNP0RN3StatsParser

# Step 1: Show current corrupted data from database
print("=" * 70)
print("STEP 1: Current Database Values (CORRUPTED)")
print("=" * 70)

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT id, session_date, map_name, round_number, player_name,
           time_played_minutes, time_dead_minutes, time_dead_ratio
    FROM player_comprehensive_stats
    WHERE clean_name LIKE '%qmr%' 
    AND time_dead_ratio > 100
    ORDER BY session_date DESC
    LIMIT 5
""")

corrupted_rounds = []
for row in cursor.fetchall():
    stat_id, date, map_name, round_num, name, played, dead, ratio = row
    corrupted_rounds.append((stat_id, date, map_name, round_num))
    print(f"ID {stat_id} ({date}) - {map_name} R{round_num}")
    print(f"  Player: {name}")
    print(f"  Time Played: {played:.1f} min")
    print(f"  Time Dead:   {dead:.1f} min  ❌ CORRUPTED")
    print(f"  Ratio:       {ratio:.1f}%     ❌ IMPOSSIBLE (>{100}%)")
    print()

conn.close()

# Step 2: Find the raw stats files and re-parse with the fix
print("=" * 70)
print("STEP 2: Re-parsing Raw Stats Files (WITH FIX)")
print("=" * 70)

stats_dir = 'local_stats'
parser = C0RNP0RN3StatsParser()

# Search for files containing qmr data
for stat_id, date, map_name, round_num in corrupted_rounds[:1]:  # Just check first one
    # Build pattern to find matching files
    date_part = date.replace('-', '-')  # Already in YYYY-MM-DD format
    
    # Find R1 and R2 files for this map/date
    matching_files = []
    if os.path.exists(stats_dir):
        for f in os.listdir(stats_dir):
            if date_part in f and map_name.lower() in f.lower():
                matching_files.append(f)
    
    if not matching_files:
        print(f"Could not find stats files for {date} {map_name}")
        continue
    
    matching_files.sort()
    print(f"Found files for {date} {map_name}:")
    for f in matching_files:
        print(f"  - {f}")
    
    # Find R1 and R2
    r1_file = None
    r2_file = None
    for f in matching_files:
        if 'round-1' in f:
            r1_file = os.path.join(stats_dir, f)
        elif 'round-2' in f:
            r2_file = os.path.join(stats_dir, f)
    
    if r1_file and r2_file:
        print()
        print(f"Parsing R1: {os.path.basename(r1_file)}")
        r1_data = parser.parse_file(r1_file)
        
        print(f"Parsing R2: {os.path.basename(r2_file)}")
        r2_data = parser.parse_file(r2_file)
        
        if r1_data.get('success') and r2_data.get('success'):
            # Find qmr in both rounds
            r1_qmr = None
            r2_qmr = None
            
            for p in r1_data['players']:
                if 'qmr' in p.get('name', '').lower():
                    r1_qmr = p
                    break
            
            for p in r2_data['players']:
                if 'qmr' in p.get('name', '').lower():
                    r2_qmr = p
                    break
            
            if r1_qmr and r2_qmr:
                print()
                print("RAW VALUES FROM LUA OUTPUT:")
                print("-" * 50)
                
                r1_obj = r1_qmr.get('objective_stats', {})
                r2_obj = r2_qmr.get('objective_stats', {})
                
                print(f"Round 1 ({r1_qmr['name']}):")
                print(f"  time_played_minutes: {r1_obj.get('time_played_minutes', 0):.1f}")
                print(f"  time_dead_minutes:   {r1_obj.get('time_dead_minutes', 0):.1f}")
                print(f"  time_dead_ratio:     {r1_obj.get('time_dead_ratio', 0):.1f}%")
                
                print()
                print(f"Round 2 CUMULATIVE ({r2_qmr['name']}):")
                print(f"  time_played_minutes: {r2_obj.get('time_played_minutes', 0):.1f}")
                print(f"  time_dead_minutes:   {r2_obj.get('time_dead_minutes', 0):.1f}")
                print(f"  time_dead_ratio:     {r2_obj.get('time_dead_ratio', 0):.1f}%")
                
                # Now calculate R2 differential with the FIX
                print()
                print("CALCULATING R2 DIFFERENTIAL (WITH FIX):")
                print("-" * 50)
                
                r2_only = parser.calculate_round_2_differential(r1_data, r2_data)
                
                for p in r2_only['players']:
                    if 'qmr' in p.get('name', '').lower():
                        obj = p.get('objective_stats', {})
                        print(f"Round 2 ONLY (differential):")
                        print(f"  time_played_minutes: {obj.get('time_played_minutes', 0):.1f}")
                        print(f"  time_dead_minutes:   {obj.get('time_dead_minutes', 0):.1f}  ✅ FIXED")
                        print(f"  time_dead_ratio:     {obj.get('time_dead_ratio', 0):.1f}%   ✅ FIXED")
                        
                        # Compare old vs new
                        print()
                        print("=" * 70)
                        print("COMPARISON: OLD (Corrupted) vs NEW (Fixed)")
                        print("=" * 70)
                        print(f"                    OLD         NEW")
                        print(f"  time_dead_mins:  {dead:.1f}      {obj.get('time_dead_minutes', 0):.1f}")
                        print(f"  time_dead_ratio: {ratio:.1f}%    {obj.get('time_dead_ratio', 0):.1f}%")
                        break
            else:
                print("qmr not found in both rounds")
    elif r1_file or r2_file:
        # Only one file - check what's there
        single_file = r1_file or r2_file
        print(f"\nOnly found single file: {os.path.basename(single_file)}")
        data = parser.parse_file(single_file)
        if data.get('success'):
            for p in data['players']:
                if 'qmr' in p.get('name', '').lower():
                    obj = p.get('objective_stats', {})
                    print(f"\nqmr stats from file:")
                    print(f"  time_played_minutes: {obj.get('time_played_minutes', 0):.1f}")
                    print(f"  time_dead_minutes:   {obj.get('time_dead_minutes', 0):.1f}")
                    print(f"  time_dead_ratio:     {obj.get('time_dead_ratio', 0):.1f}%")
                    break
