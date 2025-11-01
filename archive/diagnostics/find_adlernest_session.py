#!/usr/bin/env python3
"""Find the adlernest session"""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

# Check if Session 72 exists
print("Checking Session 72:")
s72 = c.execute('SELECT * FROM sessions WHERE id = 72').fetchone()
print(f"  {s72}\n")

# Find adlernest sessions
print("Finding etl_adlernest sessions:")
sessions = c.execute('''
    SELECT id, session_date, map_name, round_number, created_at
    FROM sessions
    WHERE map_name = 'etl_adlernest'
    ORDER BY id
    LIMIT 10
''').fetchall()

for sess_id, date, map_name, round_num, created_at in sessions:
    player_count = c.execute('''
        SELECT COUNT(DISTINCT player_name)
        FROM player_comprehensive_stats
        WHERE session_id = ?
    ''', (sess_id,)).fetchone()[0]
    
    print(f"Session {sess_id}: {date} {map_name} R{round_num}")
    print(f"  Created: {created_at} | Unique players: {player_count}")

# Check what the first session IDs are
print("\n\nFirst 10 sessions in database:")
first_sessions = c.execute('''
    SELECT id, session_date, map_name, round_number
    FROM sessions
    ORDER BY id
    LIMIT 10
''').fetchall()

for sess_id, date, map_name, round_num in first_sessions:
    print(f"  Session {sess_id}: {date} {map_name} R{round_num}")

conn.close()
