import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Get latest sessions
cursor.execute("""
    SELECT session_date, id, map_name 
    FROM sessions 
    ORDER BY id DESC 
    LIMIT 10
""")

print("📅 Latest sessions in database:")
for row in cursor.fetchall():
    session_date, sid, map_name = row
    print(f"  ID {sid}: {session_date} - {map_name}")

# Check the session that !last_session returned (2025-11-02)
cursor.execute("""
    SELECT session_date, id, map_name
    FROM sessions
    WHERE session_date LIKE '2025-11-02%'
    ORDER BY session_date
""")

print("\n🔍 Sessions matching 2025-11-02:")
nov2_sessions = cursor.fetchall()
if nov2_sessions:
    for row in nov2_sessions:
        print(f"  ID {row[1]}: {row[0]} - {row[2]}")
else:
    print("  No sessions found!")

# Check Nov 1st sessions
cursor.execute("""
    SELECT session_date, id, map_name
    FROM sessions
    WHERE session_date LIKE '2025-11-01%'
    ORDER BY session_date DESC
""")

print("\n🔍 Sessions matching 2025-11-01:")
nov1_sessions = cursor.fetchall()
if nov1_sessions:
    for row in nov1_sessions[:10]:  # Show first 10
        print(f"  ID {row[1]}: {row[0]} - {row[2]}")
    print(f"  ... {len(nov1_sessions)} total sessions on Nov 1st")
else:
    print("  No sessions found!")

conn.close()
