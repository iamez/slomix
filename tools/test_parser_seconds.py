#!/usr/bin/env python3
"""
Quick Parser Test - Verify Seconds Implementation
=================================================
Test that parser correctly:
1. Reads time from header (MM:SS)
2. Converts to seconds (INTEGER)
3. Creates time_display (MM:SS)
4. Calculates DPM using seconds
5. Handles Round 2 differential correctly
"""

import sys

from community_stats_parser import C0RNP0RN3StatsParser

sys.path.insert(0, 'bot')


def test_parser():
    parser = C0RNP0RN3StatsParser()

    print('=' * 80)
    print('PARSER SECONDS IMPLEMENTATION TEST')
    print('=' * 80)

    # Test 1: Round 1 (etl_adlernest)
    print('\n--- TEST 1: Round 1 Basic ---')
    print('File: 2025-10-02-211808-etl_adlernest-round-1.txt')
    print('Expected: 3:51 = 231 seconds')

    r1 = parser.parse_stats_file('local_stats/2025-10-02-211808-etl_adlernest-round-1.txt')

    if r1 and 'players' in r1:
        vid = next((p for p in r1['players'] if 'vid' in p['name'].lower()), None)
        if vid:
            print(f"\nPlayer: {vid['name']}")
            print(f"  Damage: {vid['damage_given']}")
            print(f"  time_played_seconds: {vid.get('time_played_seconds', 'MISSING!')}")
            print(f"  time_display: {vid.get('time_display', 'MISSING!')}")
            print(f"  DPM: {vid.get('dpm', 0):.2f}")

            # Verify
            if vid.get('time_played_seconds') == 231:
                print("  ✅ Seconds correct!")
            else:
                print(f"  ❌ Seconds wrong! Expected 231, got {vid.get('time_played_seconds')}")

            if vid.get('time_display') == '3:51':
                print("  ✅ Display correct!")
            else:
                print(f"  ❌ Display wrong! Expected '3:51', got {vid.get('time_display')}")

            # DPM calculation check
            expected_dpm = (vid['damage_given'] * 60) / 231
            if abs(vid.get('dpm', 0) - expected_dpm) < 0.01:
                print(f"  ✅ DPM calculation correct! ({expected_dpm:.2f})")
            else:
                print(f"  ❌ DPM wrong! Expected {expected_dpm:.2f}, got {vid.get('dpm', 0):.2f}")

    # Test 2: Round 2 Differential
    print('\n' + '=' * 80)
    print('--- TEST 2: Round 2 Differential ---')
    print('File: 2025-10-02-212249-etl_adlernest-round-2.txt')
    print('Expected: R2 only time preserved (differential)')

    r2 = parser.parse_stats_file('local_stats/2025-10-02-212249-etl_adlernest-round-2.txt')

    if r2 and 'players' in r2:
        vid_r2 = next((p for p in r2['players'] if 'vid' in p['name'].lower()), None)
        if vid_r2:
            print(f"\nPlayer: {vid_r2['name']}")
            print(f"  Damage (R2 only): {vid_r2['damage_given']}")
            print(f"  time_played_seconds: {vid_r2.get('time_played_seconds', 'MISSING!')}")
            print(f"  time_display: {vid_r2.get('time_display', 'MISSING!')}")
            print(f"  DPM: {vid_r2.get('dpm', 0):.2f}")

            # Check time is not zero
            if vid_r2.get('time_played_seconds', 0) > 0:
                print(f"  ✅ Round 2 time preserved! ({vid_r2.get('time_played_seconds')} seconds)")
            else:
                print(f"  ❌ Round 2 time LOST! This is the old bug!")

    # Test 3: Longer session
    print('\n' + '=' * 80)
    print('--- TEST 3: Longer Session ---')
    print('File: 2025-10-02-213333-supply-round-1.txt')
    print('Expected: 9:41 = 581 seconds')

    r3 = parser.parse_stats_file('local_stats/2025-10-02-213333-supply-round-1.txt')

    if r3 and 'players' in r3:
        vid_r3 = next((p for p in r3['players'] if 'vid' in p['name'].lower()), None)
        if vid_r3:
            print(f"\nPlayer: {vid_r3['name']}")
            print(f"  time_played_seconds: {vid_r3.get('time_played_seconds', 'MISSING!')}")
            print(f"  time_display: {vid_r3.get('time_display', 'MISSING!')}")

            if vid_r3.get('time_played_seconds') == 581:
                print("  ✅ Long session seconds correct!")
            else:
                print(f"  ❌ Expected 581, got {vid_r3.get('time_played_seconds')}")

    print('\n' + '=' * 80)
    print('TEST COMPLETE')
    print('=' * 80)
    print()
    print('If all tests passed ✅:')
    print('  → Parser is working correctly')
    print('  → Ready for full data import')
    print()
    print('If any tests failed ❌:')
    print('  → Check bot/community_stats_parser.py')
    print('  → Look for time_played_seconds assignment')


if __name__ == '__main__':
    test_parser()
