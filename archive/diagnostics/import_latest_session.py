"""
Quick import of the latest session (Oct 2, 2025) for DPM testing
"""

import sqlite3
import sys
from pathlib import Path

from community_stats_parser import CommunityStatsParser

# Add bot directory to path for parser
sys.path.insert(0, str(Path(__file__).parent / 'bot'))


def import_session(date_prefix='2025-10-02'):
    """Import all files from a specific date"""
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()
    parser = CommunityStatsParser()

    stats_dir = Path('local_stats')
    files = sorted(stats_dir.glob(f'{date_prefix}-*.txt'))

    print(f"📅 Found {len(files)} files from {date_prefix}")

    imported = 0
    for filepath in files:
        filename = filepath.name
        print(f"  Processing: {filename}")

        try:
            # Parse the file
            result = parser.parse_file(str(filepath))
            if not result:
                print(f"    ⚠️ Parse failed")
                continue

            # Create session
            cursor.execute(
                '''
                INSERT INTO sessions (
                    filename, session_date, server_name, map_name,
                    campaign_name, actual_time, round_number
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
                (
                    filename,
                    result['header']['session_date'],
                    result['header']['server_name'],
                    result['header']['map_name'],
                    result['header'].get('campaign_name', 'Unknown'),
                    result['header']['actual_time'],
                    result['header'].get('round_number', 1),
                ),
            )
            session_id = cursor.lastrowid

            # Insert players
            for guid, player_data in result['players'].items():
                objective_stats = player_data.get('objective_stats', {})
                time_played_minutes = objective_stats.get('time_played_minutes', 0.0)

                cursor.execute(
                    '''
                    INSERT INTO player_comprehensive_stats (
                        session_id, player_guid, player_name, team,
                        kills, deaths, gibs, selfkills, team_kills, team_gibs,
                        damage_given, damage_received, damage_team,
                        dpm, time_played_minutes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                    (
                        session_id,
                        guid,
                        player_data['name'],
                        player_data['team'],
                        player_data['kills'],
                        player_data['deaths'],
                        player_data['gibs'],
                        player_data['selfkills'],
                        player_data['team_kills'],
                        player_data['team_gibs'],
                        player_data['damage_given'],
                        player_data['damage_received'],
                        player_data['damage_team'],
                        objective_stats.get('dpm', 0.0),
                        time_played_minutes,
                    ),
                )

            conn.commit()
            imported += 1
            print(f"    ✅ Imported ({len(result['players'])} players)")

        except Exception as e:
            print(f"    ❌ Error: {e}")
            conn.rollback()
            continue

    conn.close()
    print(f"\n✅ Import complete: {imported}/{len(files)} files imported")
    return imported


if __name__ == '__main__':
    import_session('2025-10-02')
