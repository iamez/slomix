#!/usr/bin/env python3
import sqlite3
import json

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

c.execute('''
    SELECT session_start_date, map_name, team_name, player_guids
    FROM session_teams
    WHERE session_start_date LIKE '2025-10-28%'
    ORDER BY map_name, team_name
''')

rows = c.fetchall()
print(f"Found {len(rows)} rows for 2025-10-28:\n")

for round_date, map_name, team_name, player_guids_json in rows:
    guids = json.loads(player_guids_json)
    print(f"{map_name:<20} {team_name:<10} ({len(guids)} players)")

conn.close()
