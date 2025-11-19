import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("Checking for duplicate sessions:")
print("="*70)

# Find duplicate round_date entries
cursor.execute("""
    SELECT round_date, COUNT(*) as count
    FROM rounds
    GROUP BY round_date
    HAVING COUNT(*) > 1
    ORDER BY count DESC
    LIMIT 20
""")

duplicates = cursor.fetchall()
if duplicates:
    print(f"Found {len(duplicates)} duplicate session_dates:")
    for round_date, count in duplicates:
        print(f"  {round_date}: {count} entries")
        
        # Show the IDs
        cursor.execute("""
            SELECT id, map_name, round_number, created_at
            FROM rounds
            WHERE round_date = ?
            ORDER BY id
        """, (round_date,))
        
        for row in cursor.fetchall():
            print(f"    ID {row[0]}: {row[1]} R{row[2]} - created {row[3]}")
        print()
else:
    print("✅ No duplicate session_dates found")

print("\nChecking player stats duplicates:")
print("="*70)

# Check if same player appears multiple times in same session
cursor.execute("""
    SELECT round_id, player_guid, COUNT(*) as count
    FROM player_comprehensive_stats
    GROUP BY round_id, player_guid
    HAVING COUNT(*) > 1
    LIMIT 10
""")

player_dupes = cursor.fetchall()
if player_dupes:
    print(f"Found {len(player_dupes)} cases of duplicate player stats:")
    for round_id, player_guid, count in player_dupes[:5]:
        print(f"  Session {round_id}, Player {player_guid}: {count} entries")
        
        # Get round info
        cursor.execute("SELECT round_date, map_name FROM rounds WHERE id = ?", (round_id,))
        session_info = cursor.fetchone()
        if session_info:
            print(f"    Round: {session_info[0]} - {session_info[1]}")
else:
    print("✅ No duplicate player stats found")

print("\nDatabase stats:")
print("="*70)
cursor.execute("SELECT COUNT(*) FROM rounds")
print(f"Total sessions: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
print(f"Total player stats: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM processed_files")
print(f"Total processed files: {cursor.fetchone()[0]}")

print("\nDate range in database:")
cursor.execute("""
    SELECT MIN(SUBSTR(round_date, 1, 10)), MAX(SUBSTR(round_date, 1, 10))
    FROM rounds
    WHERE SUBSTR(round_date, 1, 4) = '2025'
""")
min_date, max_date = cursor.fetchone()
print(f"From {min_date} to {max_date}")

conn.close()
