import sqlite3
from pathlib import Path

db_path = Path("bot/etlegacy_production.db")

print("=" * 100)
print("CHECKING SESSION ID CONFLICT")
print("=" * 100)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check rounds table structure
print("\n📋 SESSIONS TABLE STRUCTURE:")
print("-" * 100)
cursor.execute("PRAGMA table_info(sessions)")
cols = cursor.fetchall()
for col in cols:
    print(f"   {col[1]:<30} {col[2]:<15} PK={col[5]}")

# Check player_comprehensive_stats structure
print("\n" + "=" * 100)
print("📋 PLAYER_COMPREHENSIVE_STATS STRUCTURE:")
print("-" * 100)
cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
cols = cursor.fetchall()
for col in cols:
    if 'session' in col[1].lower() or 'id' == col[1].lower():
        print(f"   {col[1]:<30} {col[2]:<15} PK={col[5]} FK={col[1] == 'round_id'}")

# Check UNIQUE constraints
print("\n" + "=" * 100)
print("🔒 UNIQUE CONSTRAINTS:")
print("-" * 100)
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='player_comprehensive_stats'")
schema = cursor.fetchone()
if schema:
    for line in schema[0].split('\n'):
        if 'UNIQUE' in line:
            print(f"   {line.strip()}")

# Check what session IDs exist
print("\n" + "=" * 100)
print("📊 EXISTING SESSION IDs:")
print("-" * 100)
cursor.execute("SELECT id, round_date, map_name, round_number FROM rounds ORDER BY id")
sessions = cursor.fetchall()
print(f"\n{'ID':<6} {'Date':<15} {'Map':<25} {'Round':<6}")
print("-" * 60)
for row in sessions:
    print(f"{row[0]:<6} {row[1]:<15} {row[2]:<25} R{row[3]:<5}")

# Check player_comprehensive_stats round_id values
print("\n" + "=" * 100)
print("🔍 PLAYER STATS SESSION_ID VALUES:")
print("-" * 100)
cursor.execute("""
    SELECT 
        round_id,
        COUNT(*) as player_count,
        MIN(player_name) as sample_player
    FROM player_comprehensive_stats
    GROUP BY round_id
    ORDER BY round_id
""")
results = cursor.fetchall()
print(f"\n{'Session ID':<12} {'Player Count':<15} {'Sample Player':<20}")
print("-" * 50)
for row in results:
    print(f"{row[0]:<12} {row[1]:<15} {row[2]:<20}")

# THE PROBLEM
print("\n" + "=" * 100)
print("🚨 THE PROBLEM:")
print("=" * 100)
print("""
UNIQUE constraint: UNIQUE(round_id, player_guid)

This means if the bulk importer tries to insert:
- File 1: Creates round_id = 1
- File 2: Creates round_id = 2 
- File 3: Creates round_id = 3
...BUT if player_guid stays same and round_id somehow repeats...
OR if the bulk importer is trying to use round_date as round_id...

Let me check if round_id in player_comprehensive_stats is INTEGER or TEXT!
""")

# Check actual data type
cursor.execute("SELECT typeof(round_id), round_id FROM player_comprehensive_stats LIMIT 5")
types = cursor.fetchall()
print(f"\n{'Type':<15} {'Value':<15}")
print("-" * 30)
for row in types:
    print(f"{row[0]:<15} {row[1]:<15}")

conn.close()
print("\n" + "=" * 100)
