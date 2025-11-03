import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Get all sessions with their file info
cursor.execute("""
    SELECT session_date, map_name, round_number
    FROM sessions
    ORDER BY session_date
""")

sessions = cursor.fetchall()

print(f"Total sessions in database: {len(sessions)}")
print("\nAll sessions:")
for row in sessions:
    # Reconstruct the filename pattern
    # session_date is like: 2025-10-27-230230
    # filename would be: 2025-10-27-230230-mapname-round-N.txt
    session_date = row[0]
    map_name = row[1]
    round_num = row[2]
    
    # Expected filename pattern
    filename = f"{session_date}-{map_name}-round-{round_num}.txt"
    print(f"  {filename}")

# Group by date
cursor.execute("""
    SELECT SUBSTR(session_date, 1, 10) as date, COUNT(*) as count
    FROM sessions
    GROUP BY date
    ORDER BY date
""")

print("\nSessions by date:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} sessions")

conn.close()
