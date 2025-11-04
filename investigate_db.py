import sqlite3

# Connect to database
conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("=" * 70)
print("DATABASE INVESTIGATION")
print("=" * 70)

# Check tables
print("\n1. TABLES IN DATABASE:")
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for table in tables:
    print(f"   - {table[0]}")

# Check round_date format
print("\n2. SESSION_DATE FORMAT (Last 5 sessions):")
sessions = cursor.execute("""
    SELECT round_date, actual_time, map_name 
    FROM rounds 
    ORDER BY id DESC 
    LIMIT 5
""").fetchall()

for i, (date, time, map_name) in enumerate(sessions, 1):
    print(f"   {i}. round_date: '{date}' | actual_time: '{time}' | map: {map_name}")

# Check if team_lineups exists
print("\n3. TEAM_LINEUPS TABLE:")
team_lineups_exists = cursor.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name='team_lineups'
""").fetchone()

if team_lineups_exists:
    print("   ✅ team_lineups table EXISTS")
    count = cursor.execute("SELECT COUNT(*) FROM team_lineups").fetchone()[0]
    print(f"   📊 Rows: {count}")
else:
    print("   ❌ team_lineups table DOES NOT EXIST")

# Check round_teams as alternative
print("\n4. SESSION_TEAMS TABLE (Alternative):")
session_teams_exists = cursor.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name='session_teams'
""").fetchone()

if session_teams_exists:
    print("   ✅ session_teams table EXISTS")
    count = cursor.execute("SELECT COUNT(*) FROM session_teams").fetchone()[0]
    print(f"   📊 Rows: {count}")
    # Sample data
    sample = cursor.execute("""
        SELECT round_date, team, player_name 
        FROM session_teams 
        LIMIT 3
    """).fetchall()
    print("   Sample data:")
    for row in sample:
        print(f"      {row[0]} | Team: {row[1]} | Player: {row[2]}")
else:
    print("   ❌ session_teams table DOES NOT EXIST")

print("\n" + "=" * 70)
print("INVESTIGATION COMPLETE")
print("=" * 70)

conn.close()
