#!/usr/bin/env python3
"""
Analyze October 2nd scoring WITH team names

Uses session_teams to show WHO attacked when
"""

import sqlite3
import json

conn = sqlite3.connect('github/etlegacy_production.db')
cursor = conn.cursor()

print("\n" + "="*80)
print("🎯 OCTOBER 2nd STOPWATCH SCORING - WITH TEAM TRACKING")
print("="*80)

# Get team assignments
cursor.execute('''
    SELECT team_name, player_guids
    FROM session_teams
    WHERE session_start_date LIKE "2025-10-02%"
    ORDER BY team_name
''')

teams = cursor.fetchall()
if len(teams) >= 2:
    team1_name, team1_guids_json = teams[0]
    team2_name, team2_guids_json = teams[1]
    
    team1_guids = set(json.loads(team1_guids_json))
    team2_guids = set(json.loads(team2_guids_json))
    
    print(f"\n👥 TEAMS:")
    print(f"   {team1_name}: {len(team1_guids)} players")
    print(f"   {team2_name}: {len(team2_guids)} players")
else:
    print("❌ No team data found!")
    exit(1)

# Get a Round 1 player to determine which team attacked first
cursor.execute('''
    SELECT player_guid, team
    FROM player_comprehensive_stats
    WHERE session_date LIKE "2025-10-02%"
    AND round_number = 1
    LIMIT 1
''')

sample = cursor.fetchone()
if not sample:
    print("❌ No Round 1 player data!")
    exit(1)

sample_guid, sample_team = sample

# Determine which team name corresponds to which game team number
if sample_guid in team1_guids:
    # team1_name played as game team 'sample_team' in Round 1
    if sample_team == 2:  # Allies attack in Round 1
        round1_attacker = team1_name
        round2_attacker = team2_name
    else:  # Axis attack in Round 1
        round1_attacker = team2_name
        round2_attacker = team1_name
else:
    # team2_name played as game team 'sample_team' in Round 1
    if sample_team == 2:  # Allies attack in Round 1
        round1_attacker = team2_name
        round2_attacker = team1_name
    else:  # Axis attack in Round 1
        round1_attacker = team1_name
        round2_attacker = team2_name

print(f"\n🎮 GAME FLOW:")
print(f"   Round 1: {round1_attacker} attacks (Allies)")
print(f"   Round 2: {round2_attacker} attacks (teams swapped)")

# Get sessions
cursor.execute('''
    SELECT map_name, round_number, time_limit, actual_time
    FROM sessions
    WHERE session_date LIKE "2025-10-02%"
    ORDER BY id
''')

rows = cursor.fetchall()

# Process pairs
scores = {team1_name: 0, team2_name: 0}
map_num = 1

print(f"\n{'='*80}")
print(f"📊 MAP-BY-MAP BREAKDOWN:")
print(f"{'='*80}\n")

i = 0
while i < len(rows) - 1:
    r1 = rows[i]
    r2 = rows[i + 1]
    
    if r1[0] == r2[0]:  # Same map
        map_name = r1[0]
        r1_time = r1[3]
        r2_time = r2[3]
        
        # Convert to seconds
        def time_to_sec(t):
            parts = t.split(':')
            return int(parts[0]) * 60 + int(parts[1])
        
        r1_sec = time_to_sec(r1_time)
        r2_sec = time_to_sec(r2_time)
        
        print(f"{'─'*80}")
        print(f"MAP #{map_num}: {map_name}")
        print(f"{'─'*80}")
        
        # Round 1 scoring
        print(f"\n  Round 1: {round1_attacker} attacks")
        print(f"    Time: {r1_time}")
        print(f"    ✅ Completed! {round1_attacker} gets 1 point")
        scores[round1_attacker] += 1
        r1_score = 1
        
        # Round 2 scoring
        print(f"\n  Round 2: {round2_attacker} attacks")
        print(f"    Time limit: {r1_time} (must beat R1)")
        print(f"    Actual time: {r2_time}")
        
        if r2_sec < r1_sec:
            print(f"    ✅ BEAT THE TIME! ({r2_sec}s < {r1_sec}s)")
            print(f"    {round2_attacker} gets 2 points")
            scores[round2_attacker] += 2
            r2_score = 2
            map_winner = round2_attacker
            map_result = f"{round2_attacker} 2-{r1_score}"
        else:
            print(f"    ❌ Did NOT beat time ({r2_sec}s >= {r1_sec}s)")
            print(f"    Defenders held! {round1_attacker} gets +1 point")
            scores[round1_attacker] += 1
            r2_score = 1
            map_winner = round1_attacker
            map_result = f"{round1_attacker} 2-0" if r2_sec == r1_sec else f"{round1_attacker} 2-0"
        
        print(f"\n  🏆 MAP RESULT: {map_result}")
        print(f"  📈 Running score: {team1_name} {scores[team1_name]} - {scores[team2_name]} {team2_name}")
        
        map_num += 1
        i += 2
    else:
        i += 1

print(f"\n{'='*80}")
print(f"🏁 FINAL SCORE:")
print(f"{'='*80}")
print(f"   {team1_name}: {scores[team1_name]} points")
print(f"   {team2_name}: {scores[team2_name]} points")

if scores[team1_name] > scores[team2_name]:
    print(f"\n🏆 WINNER: {team1_name}")
elif scores[team2_name] > scores[team1_name]:
    print(f"\n🏆 WINNER: {team2_name}")
else:
    print(f"\n🤝 TIE!")

print(f"{'='*80}\n")

# Verify against your hand count
print("✋ YOUR HAND COUNT:")
print("   6 maps at 2-0 (ties) = 6 maps won")
print("   4 maps at 1-2 (R2 beat time) = 4 maps lost")
print("   Expected: roughly 12-12 or close")
print(f"\n📊 CALCULATED: {team1_name} {scores[team1_name]}, {team2_name} {scores[team2_name]}")

conn.close()
