#!/usr/bin/env python3
"""
REAL ET:Legacy Stopwatch Scoring (from m1ke's explanation)

Scoring happens AFTER Round 2:
- R2 beat time: 2-0 (attackers win)
- R2 = R1 = max time: 1-1 (tie)
- R2 didn't beat time (but not max): 0-2 (defenders win)

Special: R1 fullhold (= max time) gives defenders 1pt immediately
"""

import sqlite3
import json

conn = sqlite3.connect('github/etlegacy_production.db')
cursor = conn.cursor()

# Get the two distinct teams
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
print("║" + " "*12 + "🎯 REAL ET:LEGACY STOPWATCH SCORING" + " "*31 + "║")
print("╚" + "═"*78 + "╝\n")

print(f"👥 TEAMS: {team1_name} vs {team2_name}")
print(f"🎮 R1: {r1_attacker} attacks, R2: {r2_attacker} attacks\n")

print("┌" + "─"*78 + "┐")
print("│ Map               │  R1  │ Limit│  R2  │ Result │ Explanation         │")
print("├" + "─"*78 + "┤")

scores = {team1_name: 0, team2_name: 0}

i = 0
while i < len(rows) - 1:
    r1 = rows[i]
    r2 = rows[i + 1]
    
    if r1[0] == r2[0]:
        map_name = r1[0][:16].ljust(16)
        r1_limit = r1[2]  # Max map time
        r1_time = r1[3]   # Actual time
        r2_time = r2[3]   # R2 actual time
        
        r1_limit_sec = time_to_sec(r1_limit)
        r1_sec = time_to_sec(r1_time)
        r2_sec = time_to_sec(r2_time)
        
        # Check if R1 was fullhold (actual = limit)
        r1_fullhold = (r1_sec >= r1_limit_sec)
        
        # Scoring logic
        if r2_sec < r1_sec:
            # R2 beat the time → 2-0 for R2 attackers
            scores[r2_attacker] += 2
            result = "2-0"
            winner = r2_attacker[:6]
            explanation = f"{winner} beat time"
        elif r2_sec == r1_sec == r1_limit_sec:
            # Both times = max time → 1-1 tie
            scores[r1_attacker] += 1
            scores[r2_attacker] += 1
            result = "1-1"
            winner = "TIE"
            explanation = "Both fullhold"
        elif r2_sec == r1_sec:
            # Times equal but NOT max time → depends on interpretation
            # Treating as 1-1 tie
            scores[r1_attacker] += 1
            scores[r2_attacker] += 1
            result = "1-1"
            winner = "TIE"
            explanation = "Same time"
        else:
            # R2 didn't beat time → 2-0 for R1 attackers
            scores[r1_attacker] += 2
            result = "2-0"
            winner = r1_attacker[:6]
            explanation = f"{winner} defended"
        
        print(f"│ {map_name} │ {r1_time} │ {r1_limit} │ {r2_time} │ {result:^6} │ {explanation.ljust(19)} │")
        
        i += 2
    else:
        i += 1

print("└" + "─"*78 + "┘\n")

# Final score
print("╔" + "═"*78 + "╗")
print(f"║  🏆 FINAL SCORE:" + " "*60 + "║")
print(f"║     {team1_name}: {scores[team1_name]:>2} points" + " "*57 + "║")
print(f"║     {team2_name}: {scores[team2_name]:>2} points" + " "*53 + "║")
print("╚" + "═"*78 + "╝\n")

print("📜 M1KE'S RULES:")
print("   • Beat time in R2: 2-0 win")
print("   • R2 = R1 = max time: 1-1 tie")
print("   • R2 didn't beat time: 0-2 loss")
print("   • Fullhold in R1 (= max time): 1pt to defenders immediately\n")

conn.close()
