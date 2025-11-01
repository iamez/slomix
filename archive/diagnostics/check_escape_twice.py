import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Count sessions per map
cursor.execute('''
    SELECT map_name, COUNT(*) 
    FROM sessions 
    WHERE session_date = "2025-10-02" 
    GROUP BY map_name 
    ORDER BY map_name
''')

print('\n🗺️  Map counts for 2025-10-02:')
for row in cursor.fetchall():
    print(f'   {row[0]}: {row[1]} sessions')

# Total sessions
cursor.execute('SELECT COUNT(*) FROM sessions WHERE session_date = "2025-10-02"')
print(f'\n📊 Total sessions: {cursor.fetchone()[0]}')

# Check te_escape2 specifically
cursor.execute('''
    SELECT map_name, round_number, winner_team, time_limit, actual_time
    FROM sessions
    WHERE session_date = "2025-10-02" AND map_name = "te_escape2"
    ORDER BY round_number
''')

print('\n🔍 te_escape2 rounds:')
for row in cursor.fetchall():
    print(f'   {row[0]} R{row[1]}: winner={row[2]}, limit={row[3]}, actual={row[4]}')

conn.close()
