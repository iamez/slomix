import sqlite3
import json
import sys
import os

if len(sys.argv) < 2:
    print("Usage: python populate_session_teams_from_db.py YYYY-MM-DD")
    sys.exit(1)

session_date = sys.argv[1]
DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bot', 'etlegacy_production.db')
if not os.path.exists(DB):
    print('DB not found:', DB)
    sys.exit(2)

conn = sqlite3.connect(DB)
cur = conn.cursor()

# Get players from round 1 grouped by team
cur.execute('''
SELECT player_guid, player_name, team
FROM player_comprehensive_stats
WHERE substr(session_date,1,10)=? AND round_number = 1
''', (session_date,))
rows = cur.fetchall()
if not rows:
    print('No round 1 player rows found for', session_date)
    conn.close()
    sys.exit(1)

team1_guids = []
team2_guids = []
team1_names = []
team2_names = []
for guid, name, team in rows:
    if team == 1:
        team1_guids.append(guid)
        team1_names.append(name)
    else:
        team2_guids.append(guid)
        team2_names.append(name)

print(f'Team1 players: {len(team1_guids)}, Team2 players: {len(team2_guids)}')
if not team1_guids or not team2_guids:
    print('Cannot populate session_teams: one side empty')
    conn.close()
    sys.exit(1)

# Upsert into session_teams for map ALL
# Delete existing entries for this date & map ALL
cur.execute("DELETE FROM session_teams WHERE session_start_date LIKE ? AND map_name = 'ALL'", (f"{session_date}%",))

cur.execute('''
INSERT INTO session_teams (session_start_date, map_name, team_name, player_guids, player_names)
VALUES (?, 'ALL', ?, ?, ?)
''', (session_date, 'Team A', json.dumps(team1_guids), json.dumps(team1_names)))
cur.execute('''
INSERT INTO session_teams (session_start_date, map_name, team_name, player_guids, player_names)
VALUES (?, 'ALL', ?, ?, ?)
''', (session_date, 'Team B', json.dumps(team2_guids), json.dumps(team2_names)))

conn.commit()
print('Inserted session_teams for', session_date)

# Show verification
cur.execute("SELECT team_name, player_guids FROM session_teams WHERE session_start_date LIKE ?", (f"{session_date}%",))
for tname, guids_json in cur.fetchall():
    guids = json.loads(guids_json)
    print(tname, len(guids))

conn.close()
