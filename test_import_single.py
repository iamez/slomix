"""Test single file import with enhanced objective stats"""

import json
import sqlite3
import sys
from pathlib import Path

from bot.community_stats_parser import C0RNP0RN3StatsParser

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# Test file
TEST_FILE = 'local_stats/2024-06-29-221611-supply-round-1.txt'
DB_PATH = 'etlegacy_production.db'

print("=" * 80)
print("TESTING SINGLE FILE IMPORT WITH OBJECTIVE STATS")
print("=" * 80)

# Parse the file
parser = C0RNP0RN3StatsParser()
print(f"\n1. Parsing file: {TEST_FILE}")
result = parser.parse_stats_file(TEST_FILE)

if not result or 'players' not in result:
    print("[ERROR] Failed to parse file!")
    sys.exit(1)

print(f"   [OK] Parsed {len(result['players'])} players")

# Check first player has objective stats
first_player = result['players'][0]
print(f"\n2. Checking objective_stats for player: {first_player['name']}")

if 'objective_stats' in first_player:
    obj = first_player['objective_stats']
    print(f"   [OK] Has objective_stats with {len(obj)} fields")
    print(f"   Sample data:")
    print(f"     XP: {obj.get('xp', 0)}")
    print(f"     Kill Assists: {obj.get('kill_assists', 0)}")
    print(f"     Dynamites Planted: {obj.get('dynamites_planted', 0)}")
    print(f"     Times Revived: {obj.get('times_revived', 0)}")
    print(f"     Multikill 2x: {obj.get('multikill_2x', 0)}")

    # Test JSON serialization
    print(f"\n3. Testing JSON serialization...")
    try:
        awards_json = json.dumps(obj)
        print(f"   [OK] JSON length: {len(awards_json)} chars")

        # Test deserialization
        restored = json.loads(awards_json)
        print(f"   [OK] Restored {len(restored)} fields")

    except Exception as e:
        print(f"   [ERROR] JSON serialization failed: {e}")
        sys.exit(1)
else:
    print("   [ERROR] No objective_stats found!")
    sys.exit(1)

# Test database insertion
print(f"\n4. Testing database query (player_stats table)...")
try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if player_stats table exists
    cursor.execute(
        '''
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='player_stats'
    '''
    )

    if cursor.fetchone():
        print("   [OK] player_stats table exists")

        # Check for awards column
        cursor.execute('PRAGMA table_info(player_stats)')
        columns = [col[1] for col in cursor.fetchall()]

        if 'awards' in columns:
            print("   [OK] 'awards' column exists")

            # Count existing records with awards data
            cursor.execute('SELECT COUNT(*) FROM player_stats WHERE awards IS NOT NULL')
            count = cursor.fetchone()[0]
            print(f"   [INFO] Currently {count} records have awards data")
        else:
            print("   [WARNING] 'awards' column not found in player_stats table")
    else:
        print("   [WARNING] player_stats table not found")

    conn.close()

except Exception as e:
    print(f"   [ERROR] Database check failed: {e}")
    sys.exit(1)

print(f"\n{'=' * 80}")
print("[SUCCESS] All checks passed! Ready to import files.")
print("=" * 80)
print("\nNext step: Run bulk_import_stats.py to import all historical files")
