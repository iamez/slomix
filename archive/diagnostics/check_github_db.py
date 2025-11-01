import sqlite3

conn = sqlite3.connect('github/etlegacy_production.db')
cursor = conn.cursor()

# Check October 2nd data
cursor.execute('SELECT COUNT(*) FROM sessions WHERE session_date LIKE "2025-10-02%"')
sessions_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM session_teams WHERE session_start_date LIKE "2025-10-02%"')
teams_count = cursor.fetchone()[0]

print(f"\n📊 GitHub Database Status:")
print(f"   Oct 2nd sessions: {sessions_count}")
print(f"   Oct 2nd teams: {teams_count}")

if sessions_count > 0:
    cursor.execute('SELECT map_name, round_number, winner_team, defender_team FROM sessions WHERE session_date LIKE "2025-10-02%" LIMIT 5')
    print(f"\n   Sample sessions:")
    for row in cursor.fetchall():
        print(f"      {row}")

conn.close()
