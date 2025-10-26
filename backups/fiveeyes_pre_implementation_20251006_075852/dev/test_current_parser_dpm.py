#!/usr/bin/env python3
"""Test current parser to see what DPM we're getting"""
import sys
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()

print('='*80)
print('TESTING CURRENT PARSER OUTPUT')
print('='*80)

# Test Round 1
print('\n--- ROUND 1: etl_adlernest ---')
result = parser.parse_stats_file('local_stats/2025-10-02-211808-etl_adlernest-round-1.txt')

if result and 'players' in result:
    print(f"Session time: {result['actual_time']}")
    
    # Find vid
    for player in result['players']:
        if 'vid' in player['name'].lower():
            print(f"\nPlayer: {player['name']}")
            print(f"  Damage: {player['damage_given']}")
            print(f"  Time (minutes): {player.get('time_played_minutes', 0):.2f}")
            
            # Check if time comes from objective_stats
            obj_time = player.get('objective_stats', {}).get('time_played_minutes', 0)
            print(f"  Time (objective_stats): {obj_time:.2f}")
            
            print(f"  DPM (from file): {player.get('dpm', 0):.2f}")
            
            # What SHOULD the DPM be?
            # Header shows 3:51 = 231 seconds = 3.85 minutes
            # damage = 1328
            # DPM should be = 1328 / 3.85 = 344.94
            actual_seconds = 231  # 3:51
            actual_minutes = actual_seconds / 60.0  # 3.85
            correct_dpm = player['damage_given'] / actual_minutes
            print(f"  DPM (calculated from 3:51 = 231s): {correct_dpm:.2f}")
            break

# Test Round 2 differential
print('\n--- ROUND 2 DIFFERENTIAL: etl_adlernest ---')
r2_result = parser.parse_stats_file('local_stats/2025-10-02-212249-etl_adlernest-round-2.txt')

if r2_result and 'players' in r2_result:
    for player in r2_result['players']:
        if 'vid' in player['name'].lower():
            print(f"\nPlayer: {player['name']}")
            print(f"  Time (minutes): {player.get('time_played_minutes', 0):.2f}")
            obj_time = player.get('objective_stats', {}).get('time_played_minutes', 0)
            print(f"  Time (objective_stats): {obj_time:.2f}")
            print(f"  Damage: {player['damage_given']}")
            print(f"  DPM: {player.get('dpm', 0):.2f}")
            break

print('\n' + '='*80)
print('🔍 CURRENT ISSUE:')
print('='*80)
print('Parser reads Tab[22] (time_played_minutes) which is ALWAYS 0.0!')
print('Should read Tab[23] instead, which has lua-rounded time (3.9, 9.7, etc.)')
print('\nNEXT STEP: Update parser to use seconds-based calculation')
