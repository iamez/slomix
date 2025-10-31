import sqlite3
import json

conn = sqlite3.connect('github/etlegacy_production.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT team_name, player_guids 
    FROM session_teams 
    WHERE session_start_date LIKE "2025-10-02%"
''')

teams = cursor.fetchall()

print("\n📊 October 2nd Session Teams:")
for i, (team_name, player_guids_json) in enumerate(teams, 1):
    guids = json.loads(player_guids_json)
    print(f"\n  Team {i}: {team_name}")
    print(f"    GUIDs: {guids}")
    print(f"    Count: {len(guids)} players")

conn.close()
