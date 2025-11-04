"""Get last 2 gaming sessions for comprehensive validation"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Get all unique gaming session IDs in descending order
cursor.execute('''
    SELECT DISTINCT gaming_session_id 
    FROM rounds 
    ORDER BY gaming_session_id DESC 
    LIMIT 2
''')

sessions = [row[0] for row in cursor.fetchall()]
print(f"Last 2 gaming sessions: {sessions}")

# Get rounds for each session
for session_id in sessions:
    cursor.execute('''
        SELECT id, round_date, round_time, map_name, round_number
        FROM rounds
        WHERE gaming_session_id = ?
        ORDER BY id
    ''', (session_id,))
    
    rounds = cursor.fetchall()
    print(f"\nSession {session_id}: {len(rounds)} rounds")
    for r in rounds:
        print(f"  Round {r[0]}: {r[1]} {r[2]} - {r[3]} (R{r[4]})")

conn.close()
