import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Count sessions on Oct 2
cursor.execute('SELECT COUNT(*) FROM sessions WHERE session_date = "2025-10-02"')
sessions = cursor.fetchone()[0]
print(f'Sessions on Oct 2: {sessions}')

# Count player records from Oct 2
cursor.execute(
    '''
    SELECT COUNT(*)
    FROM player_comprehensive_stats
    WHERE session_id IN (SELECT id FROM sessions WHERE session_date = "2025-10-02")
'''
)
players = cursor.fetchone()[0]
print(f'Player records from Oct 2: {players}')

# Show sample session
cursor.execute(
    '''
    SELECT id, map_name, round_number, time_display
    FROM sessions
    WHERE session_date = "2025-10-02"
    ORDER BY id DESC
    LIMIT 3
'''
)
print("\nSample sessions:")
for row in cursor.fetchall():
    print(f"  ID {row[0]}: {row[1]} Round {row[2]} ({row[3]})")

conn.close()
