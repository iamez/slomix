import sqlite3
import json

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Get Round 1 players
cursor.execute('''
    SELECT player_guid, clean_name, team 
    FROM player_comprehensive_stats 
    WHERE substr(session_date, 1, 10) = '2025-10-02'
    AND round_number = 1 
    AND map_name = 'etl_adlernest'
''')
players = cursor.fetchall()

print("\n=== Round 1 etl_adlernest Players ===")
for guid, name, team in players:
    print(f"{name:20} GUID: {guid[:8]}... Team: {team}")

# Get session teams
cursor.execute('''
    SELECT team_name, player_guids 
    FROM session_teams 
    WHERE substr(session_start_date, 1, 10) = '2025-10-02'
    LIMIT 2
''')
teams = cursor.fetchall()

print("\n=== Session Teams ===")
for team_name, guids_json in teams:
    guids = json.loads(guids_json)
    print(f"\n{team_name}:")
    for guid in guids:
        print(f"  {guid}")

conn.close()
