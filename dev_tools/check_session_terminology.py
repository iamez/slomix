import sqlite3
from pathlib import Path

db_path = Path("bot/etlegacy_production.db")

print("=" * 100)
print("SESSION TERMINOLOGY INVESTIGATION")
print("=" * 100)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check what tables exist
print("\n📋 TABLES IN DATABASE:")
print("-" * 100)
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
for table in tables:
    print(f"   - {table[0]}")

# Check rounds table schema
print("\n" + "=" * 100)
print("📋 'rounds' TABLE SCHEMA:")
print("-" * 100)
cursor.execute("PRAGMA table_info(sessions)")
columns = cursor.fetchall()
for col in columns:
    print(f"   {col[1]:<30} {col[2]:<15} {'NOT NULL' if col[3] else ''}")

# Check player_comprehensive_stats schema - look for round_id
print("\n" + "=" * 100)
print("📋 'player_comprehensive_stats' SCHEMA (session-related fields):")
print("-" * 100)
cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
columns = cursor.fetchall()
session_related = [col for col in columns if 'session' in col[1].lower() or 'id' in col[1].lower() or 'timestamp' in col[1].lower()]
for col in session_related:
    print(f"   {col[1]:<30} {col[2]:<15} {'NOT NULL' if col[3] else ''}")

# Now let's understand the actual data structure
print("\n" + "=" * 100)
print("🔍 UNDERSTANDING THE DATA STRUCTURE:")
print("-" * 100)

# Get unique session_dates from sessions table
cursor.execute("SELECT DISTINCT round_date FROM rounds ORDER BY round_date")
session_dates = cursor.fetchall()
print(f"\n📅 Unique session_dates in 'rounds' table: {len(session_dates)}")
for date in session_dates:
    print(f"   - {date[0]}")

# Get all data from sessions table grouped by round_date
print("\n" + "=" * 100)
print("📊 FULL PICTURE - All rounds grouped by round_date:")
print("-" * 100)

cursor.execute("""
    SELECT 
        round_date,
        COUNT(*) as total_rounds,
        GROUP_CONCAT(DISTINCT map_name) as maps_played,
        MIN(created_at) as first_round_time,
        MAX(created_at) as last_round_time
    FROM rounds
    GROUP BY round_date
    ORDER BY round_date
""")

results = cursor.fetchall()
print(f"\n{'Session Date':<15} {'Rounds':<8} {'Maps':<50} {'First Round':<20} {'Last Round':<20}")
print("-" * 120)
for row in results:
    round_date, total_rounds, maps, first, last = row
    print(f"{round_date:<15} {total_rounds:<8} {maps:<50} {first[:19]:<20} {last[:19]:<20}")

# Check player_comprehensive_stats - does it have round_id?
print("\n" + "=" * 100)
print("🔍 CHECKING player_comprehensive_stats linkage:")
print("-" * 100)

cursor.execute("SELECT round_id, round_date, map_name FROM player_comprehensive_stats LIMIT 5")
player_rows = cursor.fetchall()
if player_rows:
    print("\nSample player_comprehensive_stats records:")
    print(f"{'round_id':<15} {'round_date':<15} {'map_name':<25}")
    print("-" * 60)
    for row in player_rows:
        print(f"{row[0]:<15} {row[1]:<15} {row[2]:<25}")
else:
    print("⚠️ No data in player_comprehensive_stats!")

# Now the BIG QUESTION
print("\n" + "=" * 100)
print("❓ THE BIG QUESTION:")
print("=" * 100)
print("""
Current Database Structure:
- 'rounds' table has 'round_date' field (format: YYYY-MM-DD)
- Each round_date = 2025-01-01 (same date for all 8 rounds)
- 8 rounds total = 4 maps × 2 rounds each

User's Definition:
- GAMING SESSION = When you sit down, play multiple maps/rounds, then log off
- Can have multiple gaming sessions in one day
- A ROUND = 1 single round (R1 or R2)
- A MAP = Round 1 + Round 2 combined

PROBLEM:
If user played on 2025-01-01 morning (4 maps), then evening (4 more maps),
the database currently stores ALL 8 rounds under round_date='2025-01-01'.

There's NO way to distinguish:
- Morning gaming session vs Evening gaming session
- Just date, no time component

SOLUTION NEEDED:
Need a 'gaming_session_id' with timestamp to group continuous play periods!
""")

conn.close()
print("\n" + "=" * 100)
