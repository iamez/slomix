#!/usr/bin/env python3
"""
Trace EXACTLY where the DPM value comes from - raw file to database
"""
import sys
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('local_stats/2025-10-02-211808-etl_adlernest-round-1.txt')

print('='*80)
print('DPM SOURCE TRACE - vid, Round 1, etl_adlernest')
print('='*80)

# Find vid
for player in result['players']:
    if player['name'].lower() == 'vid':
        guid = player.get('guid', 'UNKNOWN')
        print(f"Player: {player['name']}")
        print(f"GUID: {guid}")
        print()
        print("FROM PARSER:")
        print(f"  damage_given: {player['damage_given']}")
        print(f"  dpm: {player['dpm']}")
        
        if 'objective_stats' in player:
            obj = player['objective_stats']
            time_played = obj.get('time_played_minutes', -999)
            print(f"  time_played_minutes: {time_played}")
            
            if time_played > 0:
                manual_dpm = player['damage_given'] / time_played
                print(f"  manual calc (dmg/time): {manual_dpm:.2f}")
        
        print()
        print("SESSION INFO:")
        print(f"  actual_time: {result['actual_time']}")
        print(f"  round_time_minutes: {result.get('round_time_minutes', -999):.2f}")
        
        # Calculate session-based DPM
        if result.get('round_time_minutes', 0) > 0:
            session_dpm = player['damage_given'] / result['round_time_minutes']
            print(f"  session DPM calc: {session_dpm:.2f}")
        
        print()
        print("DATABASE HAS: 344.94")
        print()
        print("CONCLUSION:")
        print(f"  Parser's dpm ({player['dpm']:.2f}) matches session calc? {abs(player['dpm'] - (player['damage_given'] / result['round_time_minutes'])) < 0.01}")
        break

print()
print('='*80)
print("Now let's check the RAW file Field 21:")
print('='*80)

# Read raw file
with open('local_stats/2025-10-02-211808-etl_adlernest-round-1.txt', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.read().split('\n')

# Get GUID for vid from parser
vid_guid = None
for player in result['players']:
    if player['name'].lower() == 'vid':
        vid_guid = player.get('guid', None)
        break

# Find line with this GUID
for line in lines[1:]:
    if vid_guid in line:
        parts = line.split('\t')
        print(f"Found GUID: {parts[0]}")
        print(f"  Field 1 (damage): {parts[1]}")
        if len(parts) > 22:
            print(f"  Field 21 (DPM from c0rn): {parts[22]}")
        if len(parts) > 23:
            print(f"  Field 22 (time_played): {parts[23]}")
        break
