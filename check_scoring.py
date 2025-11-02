#!/usr/bin/env python3
"""Quick check of session scoring data"""

import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

print("=" * 80)
print("2025-10-30 Session Rounds:")
print("=" * 80)

c.execute("""
    SELECT map_name, round_number, defender_team, winner_team
    FROM sessions 
    WHERE session_date LIKE '2025-10-30%'
    ORDER BY id
""")

rounds = c.fetchall()
print(f"\nTotal rounds: {len(rounds)}\n")

for map_name, round_num, def_team, win_team in rounds:
    print(f"{map_name:<20} Round {round_num} - Defender: Team {def_team}, Winner: Team {win_team}")

# Count wins per team
team1_wins = sum(1 for _, _, _, w in rounds if w == 1)
team2_wins = sum(1 for _, _, _, w in rounds if w == 2)

print(f"\n" + "=" * 80)
print(f"Round Wins:")
print(f"  Team 1: {team1_wins} rounds ({team1_wins/len(rounds)*100:.1f}%)")
print(f"  Team 2: {team2_wins} rounds ({team2_wins/len(rounds)*100:.1f}%)")
print("=" * 80)

# Check team assignments
c.execute("""
    SELECT team_name, player_guids, player_names
    FROM session_teams
    WHERE session_start_date = '2025-10-30' AND map_name = 'ALL'
    ORDER BY team_name
""")

print("\nTeam Assignments:")
import json
for team_name, guids_json, names_json in c.fetchall():
    guids = json.loads(guids_json)
    names = json.loads(names_json)
    print(f"\n{team_name}: {len(guids)} players")
    for name in names[:5]:
        print(f"  - {name}")
    if len(names) > 5:
        print(f"  ... and {len(names)-5} more")

conn.close()
