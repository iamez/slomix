"""Check what date is in session_teams table."""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

cursor.execute('SELECT * FROM session_teams')
rows = cursor.fetchall()

print("="*80)
print("SESSION_TEAMS TABLE CONTENTS:")
print("="*80)
for row in rows:
    print(f"ID: {row[0]}")
    print(f"Session Date: {row[1]}")
    print(f"Team 1 Name: {row[2]}")
    print(f"Team 1 GUIDs: {row[3]}")
    print(f"Team 2 Name: {row[4]}")
    print(f"Team 2 GUIDs: {row[5]}")
    print("-"*80)

conn.close()
