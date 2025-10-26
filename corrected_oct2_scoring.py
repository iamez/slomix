#!/usr/bin/env python3
"""
CORRECTED Stopwatch scoring - maps can't be 2-1!

Round 1: Winner gets 1 point
Round 2: If attackers beat time, they get 2 points TOTAL for the map
         If defenders hold, R1 attackers get 1 MORE point (2 total)

So possible scores per map:
- 2-0: One team got 2 points (either R1+defense OR R2 beat time)
- 1-1: IMPOSSIBLE in Stopwatch (no draws)
"""

import sqlite3
import json

conn = sqlite3.connect('github/etlegacy_production.db')
cursor = conn.cursor()

# Get the two distinct teams (same logic as before)
cursor.execute('''
    SELECT DISTINCT player_guids 
    FROM session_teams 
    WHERE session_start_date LIKE "2025-10-02%"
''')

teams_raw = cursor.fetchall()
teams_sets = [set(json.loads(t[0])) for t in teams_raw]

unique_teams = []
for team_set in teams_sets:
    if not any(team_set == existing for existing in unique_teams):
        unique_teams.append(team_set)
        if len(unique_teams) == 2:
            break

# Get team names
cursor.execute('''
    SELECT team_name, player_guids 
    FROM session_teams 
    WHERE session_start_date LIKE "2025-10-02%"
    LIMIT 20
''')

team_names = {}
for name, guids_json in cursor.fetchall():
    guids_set = set(json.loads(guids_json))
    for unique_team in unique_teams:
        if guids_set == unique_team:
            team_names[frozenset(unique_team)] = name
            break

team1_key = frozenset(unique_teams[0])
team2_key = frozenset(unique_teams[1])
team1_name = team_names.get(team1_key, "Team A")
team2_name = team_names.get(team2_key, "Team B")

# Determine who attacked first
cursor.execute('''
    SELECT player_guid, team
    FROM player_comprehensive_stats
    WHERE session_date LIKE "2025-10-02%"
    AND round_number = 1
    LIMIT 1
''')

sample = cursor.fetchone()
sample_guid, sample_team = sample

if sample_guid in unique_teams[0]:
    if sample_team == 2:
        r1_attacker = team1_name
        r2_attacker = team2_name
    else:
        r1_attacker = team2_name
        r2_attacker = team1_name
else:
    if sample_team == 2:
        r1_attacker = team2_name
        r2_attacker = team1_name
    else:
        r1_attacker = team1_name
        r2_attacker = team2_name

# Get all rounds
cursor.execute('''
    SELECT map_name, round_number, time_limit, actual_time
    FROM sessions
    WHERE session_date LIKE "2025-10-02%"
    ORDER BY id
''')

rows = cursor.fetchall()

def time_to_sec(t):
    parts = t.split(':')
    return int(parts[0]) * 60 + int(parts[1])

# Process and display
print("\n" + "╔" + "═"*78 + "╗")
print("║" + " "*15 + "🎯 CORRECTED STOPWATCH SCORING" + " "*32 + "║")
print("╚" + "═"*78 + "╝\n")

print(f"👥 TEAMS: {team1_name} vs {team2_name}")
print(f"🎮 R1: {r1_attacker} attacks, R2: {r2_attacker} attacks\n")

print("┌" + "─"*78 + "┐")
print("│ Map                   │  R1  │  R2  │ Winner  │ Explanation            │")
print("├" + "─"*78 + "┤")

scores = {team1_name: 0, team2_name: 0}
map_wins = {team1_name: 0, team2_name: 0}

i = 0
while i < len(rows) - 1:
    r1 = rows[i]
    r2 = rows[i + 1]
    
    if r1[0] == r2[0]:
        map_name = r1[0][:20].ljust(20)
        r1_time = r1[3]
        r2_time = r2[3]
        
        r1_sec = time_to_sec(r1_time)
        r2_sec = time_to_sec(r2_time)
        
        # Stopwatch scoring logic
        if r2_sec < r1_sec:
            # R2 attacker beat the time → gets 2 points TOTAL for map
            winner = r2_attacker
            points = 2
            scores[r2_attacker] += 2
            map_wins[r2_attacker] += 1
            saved = r1_sec - r2_sec
            explanation = f"R2 beat time (Δ-{saved}s)"
            result = "2-0"
        else:
            # R2 did NOT beat time → R1 attacker gets 2 points TOTAL
            winner = r1_attacker
            points = 2
            scores[r1_attacker] += 2
            map_wins[r1_attacker] += 1
            explanation = "R1 held (R2 tied/slower)"
            result = "2-0"
        
        winner_display = f"{winner[:6]} {result}"
        print(f"│ {map_name} │ {r1_time} │ {r2_time} │ {winner_display.ljust(7)} │ {explanation.ljust(22)} │")
        
        i += 2
    else:
        i += 1

print("└" + "─"*78 + "┘\n")

# Final score
print("╔" + "═"*78 + "╗")
print(f"║  🏆 FINAL SCORE:" + " "*60 + "║")
print(f"║     {team1_name}: {scores[team1_name]:>2} points ({map_wins[team1_name]} maps)" + " "*47 + "║")
print(f"║     {team2_name}: {scores[team2_name]:>2} points ({map_wins[team2_name]} maps)" + " "*51 + "║")
print("╚" + "═"*78 + "╝\n")

print("📊 CORRECTED LOGIC:")
print(f"   Each map = 2 points to winner")
print(f"   {r1_attacker} won {map_wins[r1_attacker]} maps → {map_wins[r1_attacker] * 2} points")
print(f"   {r2_attacker} won {map_wins[r2_attacker]} maps → {map_wins[r2_attacker] * 2} points\n")

print("✋ YOUR HAND COUNT:")
print(f"   {map_wins[r1_attacker]} maps at 2-0 for {r1_attacker}")
print(f"   {map_wins[r2_attacker]} maps at 2-0 for {r2_attacker}")
print(f"   Total: {map_wins[r1_attacker] + map_wins[r2_attacker]} maps ✅\n")

conn.close()
