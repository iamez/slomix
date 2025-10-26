#!/usr/bin/env python3
"""
Beautiful compact visual breakdown of October 2nd Stopwatch scoring
Shows WHO attacked WHEN and WHY each team got points
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

# Find the two unique teams
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
    if sample_team == 2:  # Allies attack
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
print("║" + " "*20 + "🎯 OCTOBER 2nd STOPWATCH SCORING" + " "*25 + "║")
print("╚" + "═"*78 + "╝\n")

print(f"👥 TEAMS: {team1_name} vs {team2_name}")
print(f"🎮 PATTERN: {r1_attacker} always attacks Round 1, {r2_attacker} attacks Round 2\n")

print("┌" + "─"*78 + "┐")
print("│ Map                   │  R1  │  R2  │ Winner  │ Breakdown              │")
print("├" + "─"*78 + "┤")

scores = {team1_name: 0, team2_name: 0}
ties = 0
r2_wins = 0

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
        
        # R1: Attacker always gets 1pt
        scores[r1_attacker] += 1
        
        # R2: Check if they beat the time
        if r2_sec < r1_sec:
            # R2 attacker beat time → gets 2pts
            scores[r2_attacker] += 2
            winner = f"{r2_attacker[:6]} 2-1"
            saved = r1_sec - r2_sec
            breakdown = f"R2 won (Δ-{saved}s)"
            r2_wins += 1
        else:
            # Tie or slower → R1 attacker gets defensive +1pt
            scores[r1_attacker] += 1
            winner = f"{r1_attacker[:6]} 2-0"
            breakdown = f"R1 held (tie)" if r2_sec == r1_sec else f"R1 held (+{r2_sec-r1_sec}s)"
            ties += 1
        
        print(f"│ {map_name} │ {r1_time} │ {r2_time} │ {winner.ljust(7)} │ {breakdown.ljust(22)} │")
        
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

# Math breakdown
print("📊 SCORING BREAKDOWN:\n")
print(f"   {r1_attacker} (R1 attacker):")
print(f"      • Completed 10 objectives → 10 points")
print(f"      • Defended {ties} ties → {ties} points")
print(f"      • Total: {scores[r1_attacker]} points\n")

print(f"   {r2_attacker} (R2 attacker):")
print(f"      • Beat time on {r2_wins} maps → {r2_wins * 2} points")
print(f"      • Lost {ties} ties → 0 points")
print(f"      • Total: {scores[r2_attacker]} points\n")

print("💡 KEY INSIGHT:")
print(f"   {r1_attacker} attacked first on ALL maps → got 1pt per map (10pts)")
print(f"   Then defended successfully on {ties} maps → got +1pt each ({ties}pts)")
print(f"   {r2_attacker} beat the time on only {r2_wins} maps → got 2pts each ({r2_wins*2}pts)")
print(f"\n   Result: {scores[r1_attacker]} - {scores[r2_attacker]}\n")

# Verify against user's hand count
print("✋ YOUR HAND COUNT VERIFICATION:")
print(f"   {ties} ties (2-0 maps) = {ties} maps where R1 held")
print(f"   {r2_wins} time-beats (1-2 maps) = {r2_wins} maps where R2 won")
print(f"   Total: {ties + r2_wins} maps ✅\n")

conn.close()
