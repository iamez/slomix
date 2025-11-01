#!/usr/bin/env python3
"""
Quick fix: Manually import the 2 missing escape sessions
This bypasses the duplicate check in the import script
"""

import sqlite3
import sys

from community_stats_parser import C0RNP0RN3StatsParser

sys.path.append('bot')


parser = C0RNP0RN3StatsParser()

files_to_import = [
    'local_stats/2025-10-02-221225-te_escape2-round-1.txt',
    'local_stats/2025-10-02-221711-te_escape2-round-2.txt',
]

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

print('\n' + '=' * 70)
print('🔧 MANUAL IMPORT: Missing Escape Sessions')
print('=' * 70)

for file_path in files_to_import:
    print(f'\n📂 Processing: {file_path}')

    # Parse the file
    result = parser.parse_stats_file(file_path)

    # Extract session date from filename
    filename = file_path.split('/')[-1]
    session_date = '-'.join(filename.split('-')[:3])

    # INSERT session (FORCE - no duplicate check)
    cursor.execute(
        '''
        INSERT INTO sessions (
            session_date, map_name, round_number,
            time_limit, actual_time
        ) VALUES (?, ?, ?, ?, ?)
    ''',
        (
            session_date,
            result['map_name'],
            result['round_num'],
            result.get('map_time', ''),
            result.get('actual_time', ''),
        ),
    )

    session_id = cursor.lastrowid
    print(f'✅ Created session ID: {session_id}')

    # Insert player stats
    player_count = 0
    for player in result.get('players', []):
        obj_stats = player.get('objective_stats', {})

        cursor.execute(
            '''
            INSERT INTO player_comprehensive_stats (
                session_id, session_date, map_name, round_number,
                player_guid, player_name, clean_name,
                team, kills, deaths, gibs, self_kills, team_kills, team_gibs,
                damage_given, damage_received, team_damage_given, team_damage_received,
                xp, time_played_seconds, time_display,
                dpm, kd_ratio,
                killing_spree_best, death_spree_worst,
                kill_assists, kill_steals, headshot_kills,
                objectives_stolen, objectives_returned,
                dynamites_planted, dynamites_defused,
                times_revived, revives_given,
                bullets_fired, tank_meatshield, time_dead_ratio,
                most_useful_kills, denied_playtime,
                double_kills, triple_kills, quad_kills, multi_kills, mega_kills,
                useless_kills, full_selfkills, repairs_constructions
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''',
            (
                session_id,
                session_date,
                result['map_name'],
                result['round_num'],
                player['guid'],
                player['name'],
                player.get('clean_name', player['name']),
                player['team'],
                player['kills'],
                player['deaths'],
                obj_stats.get('gibs', 0),
                obj_stats.get('self_kills', 0),
                obj_stats.get('team_kills', 0),
                obj_stats.get('team_gibs', 0),
                obj_stats.get('damage_given', 0),
                obj_stats.get('damage_received', 0),
                obj_stats.get('team_damage_given', 0),
                obj_stats.get('team_damage_received', 0),
                obj_stats.get('xp', 0),
                obj_stats.get('time_played_seconds', 0),
                obj_stats.get('time_display', '0:00'),
                obj_stats.get('dpm', 0.0),
                obj_stats.get('kd_ratio', 0.0),
                obj_stats.get('killing_spree_best', 0),
                obj_stats.get('death_spree_worst', 0),
                obj_stats.get('kill_assists', 0),
                obj_stats.get('kill_steals', 0),
                obj_stats.get('headshot_kills', 0),
                obj_stats.get('objectives_stolen', 0),
                obj_stats.get('objectives_returned', 0),
                obj_stats.get('dynamites_planted', 0),
                obj_stats.get('dynamites_defused', 0),
                obj_stats.get('times_revived', 0),
                obj_stats.get('revives_given', 0),
                obj_stats.get('bullets_fired', 0),
                obj_stats.get('tank_meatshield', 0.0),
                obj_stats.get('time_dead_ratio', 0.0),
                obj_stats.get('most_useful_kills', 0),
                obj_stats.get('denied_playtime', 0),
                obj_stats.get('double_kills', 0),
                obj_stats.get('triple_kills', 0),
                obj_stats.get('quad_kills', 0),
                obj_stats.get('multi_kills', 0),
                obj_stats.get('mega_kills', 0),
                obj_stats.get('useless_kills', 0),
                obj_stats.get('full_selfkills', 0),
                obj_stats.get('repairs_constructions', 0),
            ),
        )
        player_count += 1

    print(f'✅ Imported {player_count} players')

conn.commit()
conn.close()

print('\n' + '=' * 70)
print('✅ IMPORT COMPLETE!')
print('=' * 70)
print(f'\nAdded 2 new escape sessions to database')
print(f'Total sessions on 2025-10-02 should now be: 20')
print(f'\nRun bot command !last_session to test!')
print('=' * 70 + '\n')
