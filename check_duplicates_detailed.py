import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("Checking for duplicate sessions:")
print("="*70)

# Find duplicate session_date entries
cursor.execute("""
    SELECT session_date, COUNT(*) as count
    FROM sessions
    GROUP BY session_date
    HAVING COUNT(*) > 1
    ORDER BY count DESC
    LIMIT 20
""")

duplicates = cursor.fetchall()
if duplicates:
    print(f"Found {len(duplicates)} duplicate session_dates:")
    for session_date, count in duplicates:
        print(f"  {session_date}: {count} entries")
        
        # Show the IDs
        cursor.execute("""
            SELECT id, map_name, round_number, created_at
            FROM sessions
            WHERE session_date = ?
            ORDER BY id
        """, (session_date,))
        
        for row in cursor.fetchall():
            print(f"    ID {row[0]}: {row[1]} R{row[2]} - created {row[3]}")
        print()
else:
    print("✅ No duplicate session_dates found")

print("\nChecking player stats duplicates:")
print("="*70)

# Check if same player appears multiple times in same session
cursor.execute("""
    SELECT session_id, player_guid, COUNT(*) as count
    FROM player_comprehensive_stats
    GROUP BY session_id, player_guid
    HAVING COUNT(*) > 1
    LIMIT 10
""")

player_dupes = cursor.fetchall()
if player_dupes:
    print(f"Found {len(player_dupes)} cases of duplicate player stats:")
    for session_id, player_guid, count in player_dupes[:5]:
        print(f"  Session {session_id}, Player {player_guid}: {count} entries")
        
        # Get session info
        cursor.execute("SELECT session_date, map_name FROM sessions WHERE id = ?", (session_id,))
        session_info = cursor.fetchone()
        if session_info:
            print(f"    Session: {session_info[0]} - {session_info[1]}")
else:
    print("✅ No duplicate player stats found")

print("\nDatabase stats:")
print("="*70)
cursor.execute("SELECT COUNT(*) FROM sessions")
print(f"Total sessions: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
print(f"Total player stats: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM processed_files")
print(f"Total processed files: {cursor.fetchone()[0]}")

print("\nDate range in database:")
cursor.execute("""
    SELECT MIN(SUBSTR(session_date, 1, 10)), MAX(SUBSTR(session_date, 1, 10))
    FROM sessions
    WHERE SUBSTR(session_date, 1, 4) = '2025'
""")
min_date, max_date = cursor.fetchone()
print(f"From {min_date} to {max_date}")

conn.close()
