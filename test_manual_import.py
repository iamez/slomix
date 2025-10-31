"""Quick test: import single working file with objective stats"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from bot.community_stats_parser import C0RNP0RN3StatsParser

sys.path.insert(0, str(Path(__file__).parent.parent))


TEST_FILE = 'local_stats/2024-06-29-221611-supply-round-1.txt'
DB_PATH = 'bot/etlegacy_production.db'  # Bot's actual database

print("\n" + "=" * 80)
print("MANUAL IMPORT TEST - SINGLE FILE WITH OBJECTIVE STATS")
print("=" * 80)

# Parse file
parser = C0RNP0RN3StatsParser()
print(f"\n1. Parsing: {TEST_FILE}")
result = parser.parse_stats_file(TEST_FILE)

if not result or 'players' not in result:
    print("[ERROR] Parse failed!")
    sys.exit(1)

print(f"   [OK] Parsed {len(result['players'])} players")

# Extract session data
file_date = result.get('session_date', 'Unknown')
map_name = result.get('map_name', 'Unknown')
round_num = result.get('round_number', 1)
time_limit = result.get('map_time', '0:00')
actual_time = result.get('actual_time', '0:00')

print(f"\n2. Session Info:")
print(f"   Date: {file_date}")
print(f"   Map: {map_name}")
print(f"   Round: {round_num}")

# Insert into database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    # Create session (using bot's schema)
    print(f"\n3. Creating session...")
    now = datetime.now().isoformat()
    cursor.execute(
        '''
        INSERT INTO sessions (date, map_name, status, start_time, end_time, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''',
        (file_date or '2024-06-29', map_name, 'completed', now, now, now),
    )

    session_id = cursor.lastrowid
    print(f"   [OK] Session ID: {session_id}")

    # Insert players
    print(f"\n4. Inserting players...")
    players_with_objectives = 0

    for player in result['players']:
        guid = player.get('guid', 'UNKNOWN')
        name = player.get('name', 'Unknown')
        clean_name = parser.strip_color_codes(name)
        team = player.get('team', 0)
        kills = player.get('kills', 0)
        deaths = player.get('deaths', 0)
        damage_given = player.get('damage_given', 0)
        damage_received = player.get('damage_received', 0)
        kd_ratio = kills / deaths if deaths > 0 else float(kills)
        headshot_kills = player.get('headshots', 0)
        dpm = player.get('dpm', 0.0)

        # Serialize objective stats to JSON
        objective_stats = player.get('objective_stats', {})
        awards_json = json.dumps(objective_stats) if objective_stats else None

        if objective_stats:
            players_with_objectives += 1

        # Insert into player_stats with awards JSON (bot's database schema)
        team_name = "Axis" if team == 1 else "Allies" if team == 2 else "Spectator"
        cursor.execute(
            '''
            INSERT INTO player_stats (
                session_id, player_name, team,
                kills, deaths, damage, kd_ratio, dpm,
                awards
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
            (
                session_id,
                clean_name,
                team_name,
                kills,
                deaths,
                damage_given,
                kd_ratio,
                dpm,
                awards_json,
            ),
        )

    conn.commit()

    print(f"   [OK] Inserted {len(result['players'])} players")
    print(f"   [OK] {players_with_objectives} have objective_stats")

    # Verify data was inserted
    print(f"\n5. Verifying data...")
    cursor.execute(
        'SELECT COUNT(*) FROM player_stats WHERE session_id = ? AND awards IS NOT NULL',
        (session_id,),
    )
    awards_count = cursor.fetchone()[0]
    print(f"   [OK] {awards_count} records with awards JSON")

    # Show sample awards data
    cursor.execute(
        'SELECT player_name, awards FROM player_stats WHERE session_id = ? AND awards IS NOT NULL LIMIT 1',
        (session_id,),
    )
    row = cursor.fetchone()
    if row:
        print(f"\n6. Sample awards data for '{row[0]}':")
        awards = json.loads(row[1])
        print(f"   XP: {awards.get('xp', 0)}")
        print(f"   Kill Assists: {awards.get('kill_assists', 0)}")
        print(f"   Dynamites Planted: {awards.get('dynamites_planted', 0)}")
        print(f"   Times Revived: {awards.get('times_revived', 0)}")
        print(f"   Multikill 2x: {awards.get('multikill_2x', 0)}")

    print(f"\n{'=' * 80}")
    print("[SUCCESS] File imported successfully with objective stats!")
    print("=" * 80)

except Exception as e:
    conn.rollback()
    print(f"\n[ERROR] Import failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

finally:
    conn.close()
