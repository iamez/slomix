#!/usr/bin/env python3
"""Debug what teams the scorer is finding"""

import sqlite3
import json

db_path = 'etlegacy_production.db'
session_date = '2025-10-02'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print(f"\n🔍 Debugging session_teams query for {session_date}\n")

# Run the EXACT query from the scorer
cursor.execute('''
    SELECT DISTINCT team_name, player_guids
    FROM session_teams
    WHERE substr(session_start_date, 1, 10) = ?
''', (session_date,))

team_rows = cursor.fetchall()

print(f"Found {len(team_rows)} DISTINCT team records:\n")

for i, row in enumerate(team_rows, 1):
    team_name, player_guids_json = row
    player_guids = json.loads(player_guids_json)
    print(f"  {i}. {team_name}")
    print(f"     GUIDs: {player_guids}\n")

conn.close()
