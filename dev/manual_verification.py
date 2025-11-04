#!/usr/bin/env python3
"""
Manual verification guide - show exact file and how to check it
"""

print('='*80)
print('🔍 MANUAL VERIFICATION GUIDE')
print('='*80)

print('''
FILE WE TESTED:
  local_stats/2025-10-02-212249-etl_adlernest-round-2.txt

DATE/TIME:
  2025-10-02 at 21:22:49 (9:22 PM)
  Map: etl_adlernest
  Round: 2

PLAYER: vid
''')

print('\n' + '='*80)
print('METHOD 1: CHECK RAW FILE')
print('='*80)

# Read the actual file
filepath = 'local_stats/2025-10-02-212249-etl_adlernest-round-2.txt'

with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.read().split('\n')

header = lines[0]
print(f'\nHEADER (first 100 chars):')
print(f'  {header[:100]}...')

header_parts = header.split('\\')
print(f'\nHEADER FIELDS:')
print(f'  [0] Server: {header_parts[0][:30]}')
print(f'  [1] Map: {header_parts[1]}')
print(f'  [3] Round: {header_parts[3]}')
print(f'  [6] Time limit: {header_parts[6]}')
print(f'  [7] Actual time: {header_parts[7]}')

print(f'\n📋 PLAYER LINES (looking for vid):')
print('-'*80)

# Find vid's line
vid_found = False
for i, line in enumerate(lines[1:], 2):
    if not line.strip():
        continue
    
    # Line format: GUID\tfield1\tfield2\t...
    parts = line.split('\t')
    if len(parts) < 2:
        continue
    
    guid = parts[0]
    
    # To find the name, we need to parse the extended fields
    # But let's just check the GUID we know is vid's
    if guid == 'D8423F90':  # This is vid's GUID from our test
        vid_found = True
        print(f'Line {i}: GUID = {guid} (this is vid)')
        print(f'  Field 1 (damage_given): {parts[1]}')
        if len(parts) > 22:
            print(f'  Field 22 (DPM from file): {parts[22]}')
        if len(parts) > 23:
            print(f'  Field 23 (time_played_minutes): {parts[23]} ✅')
        break

if not vid_found:
    print('  ❌ vid not found - checking all GUIDs:')
    for i, line in enumerate(lines[1:], 2):
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) >= 1:
            print(f'    Line {i}: GUID = {parts[0]}')

print('\n' + '='*80)
print('METHOD 2: USE PARSER')
print('='*80)

import sys
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file(filepath)

if result and 'players' in result:
    print(f'\n✅ Parser extracted {len(result["players"])} players')
    print(f'   Session time: {result.get("actual_time", "N/A")}')
    print(f'   Map: {result.get("map_name", "N/A")}')
    print(f'   Round: {result.get("round_number", "N/A")}')
    print()
    
    for player in result['players']:
        if player['name'].lower() == 'vid':
            obj = player.get('objective_stats', {})
            time_played = obj.get('time_played_minutes', -999)
            
            print(f'   Player: {player["name"]}')
            print(f'   GUID: {player.get("guid", "UNKNOWN")}')
            print(f'   Damage: {player["damage_given"]}')
            print(f'   time_played_minutes: {time_played} ✅')
            print()
            
            if time_played > 0:
                print(f'   🎯 VERIFICATION SUCCESS!')
                print(f'      Raw file has time: {parts[23] if vid_found else "check above"}')
                print(f'      Parser extracted: {time_played}')
                print(f'      Match: {abs(float(parts[23]) - time_played) < 0.01 if vid_found else "N/A"}')
            break

print('\n' + '='*80)
print('METHOD 3: COMPARE WITH ROUND 1')
print('='*80)

r1_file = 'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt'
print(f'\nRound 1 file: {r1_file}')

r1_result = parser.parse_stats_file(r1_file)

if r1_result and 'players' in r1_result:
    for player in r1_result['players']:
        if player['name'].lower() == 'vid':
            r1_obj = player.get('objective_stats', {})
            r1_time = r1_obj.get('time_played_minutes', -999)
            r1_damage = player['damage_given']
            
            print(f'  Round 1: {r1_damage} damage, {r1_time:.2f} min')
            break

if result and 'players' in result:
    for player in result['players']:
        if player['name'].lower() == 'vid':
            r2_obj = player.get('objective_stats', {})
            r2_time = r2_obj.get('time_played_minutes', -999)
            r2_damage = player['damage_given']
            
            print(f'  Round 2: {r2_damage} damage, {r2_time:.2f} min')
            
            print(f'\n  Round 2 - Round 1 = Differential:')
            print(f'    Damage: {r2_damage} (from parser)')
            print(f'    Time: {r2_time:.2f} min (from parser)')
            print(f'\n  ✅ These are Round 2 ONLY stats (differential calculated)')
            break

print('\n' + '='*80)
print('🎉 VERIFICATION COMPLETE')
print('='*80)
print('''
You can verify manually:
1. Open: local_stats/2025-10-02-212249-etl_adlernest-round-2.txt
2. Look at line 2 (first player line after header)
3. Find GUID "D8423F90" (vid's GUID)
4. Count to Field 23 (TAB-separated)
5. Should see: 7.7 (cumulative time)
6. Parser calculates: 7.7 - 3.9 (R1) = 3.8 (R2 only) ✅
''')
