#!/usr/bin/env python3
"""
Test the SECONDS-BASED parser update
=====================================
Verify that the parser now:
1. Stores time in SECONDS (integer)
2. Creates time_display (MM:SS format)
3. Calculates DPM using seconds
4. Preserves time in Round 2 differential
"""
import sys
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()

print('='*80)
print('🧪 TESTING SECONDS-BASED PARSER')
print('='*80)

# Test Round 1
print('\n--- TEST 1: Round 1 (etl_adlernest) ---')
r1 = parser.parse_stats_file('local_stats/2025-10-02-211808-etl_adlernest-round-1.txt')

if r1 and 'players' in r1:
    print(f"Session time: {r1['actual_time']}")
    
    vid = next((p for p in r1['players'] if 'vid' in p['name'].lower()), None)
    if vid:
        print(f"\nPlayer: {vid['name']}")
        print(f"  Damage: {vid['damage_given']}")
        
        # NEW: Check seconds-based fields
        print(f"\n  ⏱️ NEW FIELDS:")
        print(f"  time_played_seconds: {vid.get('time_played_seconds', 'MISSING')}")
        print(f"  time_display: {vid.get('time_display', 'MISSING')}")
        print(f"  DPM: {vid.get('dpm', 0):.2f}")
        
        # Verify calculations
        expected_seconds = 231  # 3:51
        actual_seconds = vid.get('time_played_seconds', 0)
        expected_dpm = (vid['damage_given'] * 60) / expected_seconds
        
        print(f"\n  ✅ VALIDATION:")
        print(f"  Expected seconds: {expected_seconds}")
        print(f"  Actual seconds: {actual_seconds}")
        print(f"  Match: {actual_seconds == expected_seconds}")
        print(f"  Expected DPM: {expected_dpm:.2f}")
        print(f"  Actual DPM: {vid.get('dpm', 0):.2f}")
        print(f"  DPM Match: {abs(vid.get('dpm', 0) - expected_dpm) < 0.01}")
        
        # Check backward compatibility
        print(f"\n  📊 BACKWARD COMPAT:")
        print(f"  time_played_minutes: {vid.get('time_played_minutes', 0):.2f}")
        print(f"  objective_stats time: {vid.get('objective_stats', {}).get('time_played_minutes', 0):.2f}")

# Test Round 2 differential
print('\n' + '='*80)
print('--- TEST 2: Round 2 Differential (etl_adlernest) ---')
r2 = parser.parse_stats_file('local_stats/2025-10-02-212249-etl_adlernest-round-2.txt')

if r2 and 'players' in r2:
    vid = next((p for p in r2['players'] if 'vid' in p['name'].lower()), None)
    if vid:
        print(f"\nPlayer: {vid['name']}")
        print(f"  Damage: {vid['damage_given']}")
        
        # NEW: Check seconds-based fields for R2 differential
        print(f"\n  ⏱️ NEW FIELDS:")
        print(f"  time_played_seconds: {vid.get('time_played_seconds', 'MISSING')}")
        print(f"  time_display: {vid.get('time_display', 'MISSING')}")
        print(f"  DPM: {vid.get('dpm', 0):.2f}")
        
        # Critical check: Is time_played_seconds > 0?
        has_time = vid.get('time_played_seconds', 0) > 0
        print(f"\n  ✅ CRITICAL CHECK:")
        print(f"  time_played_seconds > 0: {has_time}")
        
        if not has_time:
            print(f"  ❌ FAIL: Round 2 differential lost time data!")
        else:
            print(f"  ✅ PASS: Round 2 differential preserved time!")
            
            # Verify DPM calculation
            expected_dpm = (vid['damage_given'] * 60) / vid['time_played_seconds']
            print(f"\n  DPM Verification:")
            print(f"    Expected: {expected_dpm:.2f}")
            print(f"    Actual: {vid.get('dpm', 0):.2f}")
            print(f"    Match: {abs(vid.get('dpm', 0) - expected_dpm) < 0.01}")

# Test longer session
print('\n' + '='*80)
print('--- TEST 3: Longer Session (supply) ---')
r3 = parser.parse_stats_file('local_stats/2025-10-02-213333-supply-round-1.txt')

if r3 and 'players' in r3:
    print(f"Session time: {r3['actual_time']}")
    
    vid = next((p for p in r3['players'] if 'vid' in p['name'].lower()), None)
    if vid:
        print(f"\nPlayer: {vid['name']}")
        print(f"  time_played_seconds: {vid.get('time_played_seconds', 'MISSING')}")
        print(f"  time_display: {vid.get('time_display', 'MISSING')}")
        
        # Verify: 9:41 = 581 seconds
        expected_seconds = 9 * 60 + 41  # 581
        actual_seconds = vid.get('time_played_seconds', 0)
        print(f"\n  Expected: {expected_seconds} seconds (9:41)")
        print(f"  Actual: {actual_seconds} seconds")
        print(f"  Match: {actual_seconds == expected_seconds}")

print('\n' + '='*80)
print('🎯 TEST SUMMARY')
print('='*80)
print('If all tests passed, the parser is now using SECONDS everywhere!')
print('Next step: Add time_played_seconds column to database')
