#!/usr/bin/env python3
"""
Test if the parser fix preserves time_played_minutes in Round 2
"""
import sys
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()

print('='*80)
print('TESTING PARSER FIX - Round 2 time_played_minutes')
print('='*80)

# Test with the etl_adlernest Round 2 file that had time=0 in database
test_file = 'local_stats/2025-10-02-212249-etl_adlernest-round-2.txt'

print(f'\nParsing: {test_file}')
print('-'*80)

result = parser.parse_stats_file(test_file)

if result and 'players' in result:
    print(f'✅ Parsed successfully')
    print(f'Players found: {len(result["players"])}')
    print()
    
    # Find vid
    for player in result['players']:
        if player['name'].lower() == 'vid':
            print(f'Player: {player["name"]}')
            print(f'Damage: {player["damage_given"]}')
            print(f'DPM: {player.get("dpm", "N/A")}')
            
            obj_stats = player.get('objective_stats', {})
            time_played = obj_stats.get('time_played_minutes', -999)
            
            print(f'time_played_minutes: {time_played}')
            
            if time_played > 0:
                print(f'\n✅ SUCCESS! Player has time data: {time_played} minutes')
                print(f'   Can calculate accurate DPM: {player["damage_given"] / time_played:.2f}')
            else:
                print(f'\n❌ STILL BROKEN: time_played_minutes = {time_played}')
            break
else:
    print('❌ Parse failed')

print()
print('='*80)
print('Now checking database value (should be 0 still, needs re-import)')
print('='*80)

import sqlite3
conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

row = c.execute('''
    SELECT p.time_played_minutes, p.damage_given, p.dpm
    FROM sessions s
    JOIN player_comprehensive_stats p ON s.id = p.session_id
    WHERE s.session_date = '2025-10-02'
    AND s.map_name = 'etl_adlernest'
    AND s.round_number = 2
    AND p.player_name = 'vid'
''').fetchone()

if row:
    db_time, db_dmg, db_dpm = row
    print(f'Database time_played_minutes: {db_time}')
    print(f'Database damage: {db_dmg}')
    print(f'Database DPM: {db_dpm}')
    print()
    print('⚠️  Database still has old value (time=0)')
    print('   Need to re-import to see the fix!')

conn.close()
