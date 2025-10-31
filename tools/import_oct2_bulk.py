#!/usr/bin/env python3
"""
Bulk Import October 2nd Stats with Seconds Parser
=================================================
Imports all Oct 2 stats files into fresh database with seconds-based time.
"""

import glob
import os
import re
import sqlite3
import sys
from datetime import datetime

from community_stats_parser import C0RNP0RN3StatsParser

sys.path.insert(0, 'bot')


def import_all_oct2_files():
    """Import all October 2nd stats files"""

    parser = C0RNP0RN3StatsParser()
    conn = sqlite3.connect('etlegacy_production.db')
    c = conn.cursor()

    # Find all Oct 2 files
    files = sorted(glob.glob('local_stats/2025-10-02-*.txt'))

    print('=' * 80)
    print('BULK IMPORT - October 2nd Stats with SECONDS')
    print('=' * 80)
    print(f'\nFound {len(files)} files to import')
    print()

    imported = 0
    failed = 0

    for filepath in files:
        filename = os.path.basename(filepath)

        print(f'📥 Importing: {filename}')

        # Parse file
        result = parser.parse_stats_file(filepath)

        if not result or not result.get('success'):
            print(f'   ❌ Parse failed!')
            failed += 1
            continue

        # Extract session data
        map_name = result.get('map_name', '')
        round_number = result.get('round_num', 0)
        server_name = result.get('server_name', '')
        config = result.get('config', '')
        defender = result.get('defender_team', 0)
        winner = result.get('winner_team', 0)
        time_limit = result.get('map_time', '')
        actual_time = result.get('actual_time', '')
        timestamp = result.get('timestamp', datetime.now())

        # Extract date and time from timestamp
        if isinstance(timestamp, datetime):
            session_date = timestamp.date()
            timestamp.time()
        else:
            session_date = datetime.now().date()
            datetime.now().time()

        # Insert session
        c.execute(
            '''
            INSERT INTO sessions (
                session_date, map_name, round_number, server_name,
                config_name, defender_team, winner_team, time_limit,
                actual_time, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
            (
                session_date,
                map_name,
                round_number,
                server_name,
                config,
                defender,
                winner,
                time_limit,
                actual_time,
                datetime.now(),
            ),
        )

        session_id = c.lastrowid

        # Insert players
        player_count = 0
        for player in result.get('players', []):
            # Strip color codes from name for clean_name
            clean_name = re.sub(r'\^[0-9a-zA-Z]', '', player['name'])

            # Get objective stats
            obj_stats = player.get('objective_stats', {})

            c.execute(
                '''
                INSERT INTO player_comprehensive_stats (
                    session_id, session_date, map_name, round_number,
                    player_guid, player_name, clean_name, team,
                    kills, deaths, damage_given, damage_received,
                    team_damage_given, team_damage_received,
                    gibs, self_kills, team_kills, team_gibs,
                    time_played_seconds, time_played_minutes, time_display,
                    dpm, kd_ratio, accuracy, headshot_ratio, xp,
                    headshot_kills, times_revived, denied_playtime,
                    dynamites_planted, dynamites_defused,
                    objectives_stolen, objectives_returned,
                    bullets_fired
                ) VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?
                )
            ''',
                (
                    session_id,
                    session_date,
                    map_name,
                    round_number,
                    player['guid'],
                    player['name'],
                    clean_name,
                    player['team'],
                    player.get('kills', 0),
                    player.get('deaths', 0),
                    player.get('damage_given', 0),
                    player.get('damage_received', 0),
                    player.get('team_damage_given', 0),
                    player.get('team_damage_received', 0),
                    player.get('gibs', 0),
                    player.get('self_kills', 0),
                    player.get('team_kills', 0),
                    player.get('team_gibs', 0),
                    player.get('time_played_seconds', 0),
                    player.get('time_played_minutes', 0.0),
                    player.get('time_display', '0:00'),
                    player.get('dpm', 0.0),
                    player.get('kd_ratio', 0.0),
                    player.get('accuracy', 0.0),
                    player.get('headshot_ratio', 0.0),
                    player.get('xp', 0),
                    player.get('headshots', 0),
                    obj_stats.get('revives', 0),
                    obj_stats.get('denied_playtime', 0),
                    obj_stats.get('dynamites_planted', 0),
                    obj_stats.get('dynamites_defused', 0),
                    obj_stats.get('objectives_stolen', 0),
                    obj_stats.get('objectives_returned', 0),
                    player.get('shots_total', 0),
                ),
            )
            c.lastrowid

            # Import weapon stats
            weapon_stats = player.get('weapon_stats', {})
            for weapon_id, (weapon_name, wstats) in enumerate(weapon_stats.items()):
                c.execute(
                    '''
                    INSERT INTO weapon_comprehensive_stats (
                        session_id, player_guid, weapon_id, weapon_name,
                        kills, deaths, hits, shots, headshots,
                        accuracy, headshot_ratio
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                    (
                        session_id,
                        player['guid'],
                        weapon_id,
                        weapon_name,
                        wstats.get('kills', 0),
                        wstats.get('deaths', 0),
                        wstats.get('hits', 0),
                        wstats.get('shots', 0),
                        wstats.get('headshots', 0),
                        wstats.get('accuracy', 0.0),
                        (
                            wstats.get('headshots', 0) / wstats.get('hits', 1) * 100
                            if wstats.get('hits', 0) > 0
                            else 0.0
                        ),
                    ),
                )

            player_count += 1

        conn.commit()

        print(f'   ✅ Imported {player_count} players')
        imported += 1

    conn.close()

    print()
    print('=' * 80)
    print('IMPORT COMPLETE')
    print('=' * 80)
    print(f'✅ Imported: {imported} files')
    print(f'❌ Failed: {failed} files')
    print(f'⏭️  Skipped: {len(files) - imported - failed} files')
    print()
    print('Next step: Verify data with queries')


if __name__ == '__main__':
    import_all_oct2_files()
