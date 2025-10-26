#!/usr/bin/env python3
"""Test if parser extracts time_played_minutes correctly"""
import sys
from pathlib import Path

from community_stats_parser import C0RNP0RN3StatsParser

sys.path.insert(0, 'bot')


parser = C0RNP0RN3StatsParser()

# Test Round 1 file
r1_file = 'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt'
print('=' * 80)
print(f'Testing Round 1: {r1_file}')
print('=' * 80)
result1 = parser.parse_stats_file(r1_file)
if result1 and 'players' in result1:
    sample = list(result1['players'].values())[0]
    time1 = sample.get('objective_stats', {}).get('time_played_minutes', -999)
    dpm1 = sample.get('dpm', -999)
    name1 = sample.get('name', 'unknown')
    print(f'Sample player: {name1}')
    print(f'  Time played: {time1:.2f} minutes')
    print(f'  DPM: {dpm1:.2f}')
else:
    print('❌ Parse failed or no players')

# Test Round 2 file
r2_files = list(Path('local_stats').glob('2025-10-02-*-round-2.txt'))
if r2_files:
    r2_file = str(r2_files[0])
    print(f'\nTesting Round 2: {Path(r2_file).name}')
    print('=' * 80)
    result2 = parser.parse_stats_file(r2_file)
    if result2 and 'players' in result2:
        sample = list(result2['players'].values())[0]
        time2 = sample.get('objective_stats', {}).get('time_played_minutes', -999)
        dpm2 = sample.get('dpm', -999)
        name2 = sample.get('name', 'unknown')
        print(f'Sample player: {name2}')
        print(f'  Time played: {time2:.2f} minutes')
        print(f'  DPM: {dpm2:.2f}')

        # Show all players' time values
        print(f'\n📊 All players in Round 2:')
        for guid, pdata in result2['players'].items():
            pname = pdata.get('name', 'unknown')
            ptime = pdata.get('objective_stats', {}).get('time_played_minutes', 0)
            pdpm = pdata.get('dpm', 0)
            print(f'  {pname:20} | time={ptime:6.2f} min | dpm={pdpm:6.2f}')
    else:
        print('❌ Parse failed or no players')
