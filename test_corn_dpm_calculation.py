#!/usr/bin/env python3
"""
Test what DPM values actually exist in stats files
and understand how c0rnp0rn3.lua calculates them
"""
import sys

from community_stats_parser import C0RNP0RN3StatsParser

sys.path.insert(0, 'bot')

parser = C0RNP0RN3StatsParser()

print('=' * 80)
print('ANALYZING c0rnp0rn3.lua DPM CALCULATION')
print('=' * 80)

print('\n--- ROUND 1 FILE ---')
r1 = parser.parse_stats_file('local_stats/2025-10-02-211808-etl_adlernest-round-1.txt')
if r1:
    print(f'Session actual_time: {r1.get("actual_time", "unknown")}')
    print(f'Players found: {len(r1.get("players", []))}')
    if r1.get('players'):
        for i, p in enumerate(r1['players'][:3]):
            name = p.get('name', 'unknown')
            damage = p.get('damage_given', 0)
            dpm_from_file = p.get('dpm', 0)
            obj = p.get('objective_stats', {})
            time_played = obj.get('time_played_minutes', 0)

            print(f'\n  Player {i + 1}: {name}')
            print(f'    Damage: {damage}')
            print(f'    DPM (from c0rnp0rn3.lua): {dpm_from_file:.2f}')
            print(f'    time_played_minutes: {time_played:.2f}')
            if time_played > 0:
                our_dpm = damage / time_played
                print(f'    Our DPM calculation: {our_dpm:.2f}')
                diff = abs(dpm_from_file - our_dpm)
                if diff < 0.1:
                    print(f'    ✅ Match! (diff: {diff:.4f})')
                else:
                    print(f'    ❌ MISMATCH! (diff: {diff:.2f})')

print('\n' + '=' * 80)
print('--- ROUND 2 FILE ---')
r2 = parser.parse_stats_file('local_stats/2025-10-02-212249-etl_adlernest-round-2.txt')
if r2:
    print(f'Session actual_time: {r2.get("actual_time", "unknown")}')
    print(f'Players found: {len(r2.get("players", []))}')
    if r2.get('players'):
        for i, p in enumerate(r2['players'][:3]):
            name = p.get('name', 'unknown')
            damage = p.get('damage_given', 0)
            dpm_from_file = p.get('dpm', 0)
            obj = p.get('objective_stats', {})
            time_played = obj.get('time_played_minutes', 0)

            print(f'\n  Player {i + 1}: {name}')
            print(f'    Damage: {damage}')
            print(f'    DPM (from c0rnp0rn3.lua): {dpm_from_file:.2f}')
            print(f'    time_played_minutes: {time_played:.2f}')
            if time_played > 0:
                our_dpm = damage / time_played
                print(f'    Our DPM calculation: {our_dpm:.2f}')
                diff = abs(dpm_from_file - our_dpm)
                if diff < 0.1:
                    print(f'    ✅ Match! (diff: {diff:.4f})')
                else:
                    print(f'    ❌ MISMATCH! (diff: {diff:.2f})')
            else:
                print(f'    ⚠️  Cannot verify (time_played = 0)')

print('\n' + '=' * 80)
print('RECOMMENDATION:')
print('=' * 80)
print(
    '''
We should store TWO DPM values:

1. cDPM (c0rnp0rn3 DPM) - From Field 21 in stats file
   - This is what c0rnp0rn3.lua calculates
   - May use averaged/estimated time for some players

2. Our DPM - damage_given / time_played_minutes
   - Factual calculation based on actual playtime
   - Only calculable when time_played_minutes > 0

For session-wide DPM:
  Our DPM = SUM(damage_given) / SUM(time_played_minutes)

This gives users both perspectives!
'''
)
