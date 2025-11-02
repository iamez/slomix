"""
Analyze team assignment patterns to see if we can predict actual teams
"""
import sqlite3
from collections import defaultdict

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

print("=" * 80)
print("TEAM ASSIGNMENT PATTERN ANALYSIS")
print("=" * 80)

# Get all data for the session
c.execute("""
    SELECT map_name, round_number, player_name, player_guid, team
    FROM player_comprehensive_stats
    WHERE session_date = '2025-10-30'
    ORDER BY map_name, round_number, player_name
""")

data = c.fetchall()

# Group by map
maps = {}
for map_name, round_num, player, guid, team in data:
    if map_name not in maps:
        maps[map_name] = {}
    if round_num not in maps[map_name]:
        maps[map_name][round_num] = []
    maps[map_name][round_num].append((player, guid, team))

# Analyze pattern
print("\nPATTERN ANALYSIS:")
print("-" * 80)

for map_name, rounds in sorted(maps.items()):
    print(f"\n{map_name}:")
    
    for round_num in sorted(rounds.keys()):
        players = rounds[round_num]
        team1 = [p for p in players if p[2] == 1]
        team2 = [p for p in players if p[2] == 2]
        
        print(f"  Round {round_num}:")
        print(f"    Team 1 ({len(team1)}): {', '.join(p[0] for p in team1)}")
        print(f"    Team 2 ({len(team2)}): {', '.join(p[0] for p in team2)}")
        print()

# Check if teams swap between rounds
print("\n" + "=" * 80)
print("TEAM SWAP PATTERN CHECK:")
print("=" * 80)

for map_name, rounds in sorted(maps.items()):
    if len(rounds) < 2:
        continue
    
    print(f"\n{map_name}:")
    
    # Get rounds
    round_nums = sorted(rounds.keys())
    if len(round_nums) < 2:
        continue
    
    r1 = round_nums[0]
    r2 = round_nums[1]
    
    # Build GUID->team mapping for each round
    r1_mapping = {guid: team for _, guid, team in rounds[r1]}
    r2_mapping = {guid: team for _, guid, team in rounds[r2]}
    
    # Check if they swapped
    swapped = 0
    stayed = 0
    
    for guid in r1_mapping:
        if guid in r2_mapping:
            if r1_mapping[guid] != r2_mapping[guid]:
                swapped += 1
            else:
                stayed += 1
    
    if swapped > stayed:
        print(f"  ✓ TEAMS SWAPPED between round {r1} and {r2}")
        print(f"    {swapped} players swapped sides, {stayed} stayed")
    else:
        print(f"  ✗ Teams DID NOT swap between round {r1} and {r2}")
        print(f"    {stayed} players stayed, {swapped} swapped")

# Check if first round team assignment is consistent across maps
print("\n" + "=" * 80)
print("CONSISTENCY CHECK: Do same players start on same side each map?")
print("=" * 80)

first_rounds = {}
for map_name, rounds in sorted(maps.items()):
    round_nums = sorted(rounds.keys())
    if round_nums:
        first_round = round_nums[0]
        first_rounds[map_name] = {guid: team for _, guid, team in rounds[first_round]}

# Compare first rounds
if len(first_rounds) >= 2:
    map_names = list(first_rounds.keys())
    
    for i in range(len(map_names) - 1):
        map1 = map_names[i]
        map2 = map_names[i + 1]
        
        print(f"\nComparing {map1} vs {map2} (first rounds):")
        
        same_team = 0
        diff_team = 0
        
        for guid in first_rounds[map1]:
            if guid in first_rounds[map2]:
                if first_rounds[map1][guid] == first_rounds[map2][guid]:
                    same_team += 1
                else:
                    diff_team += 1
        
        if same_team > diff_team:
            print(f"  ✓ Players START on SAME sides: {same_team} same, {diff_team} different")
            print(f"    → Team assignments are CONSISTENT across maps!")
        else:
            print(f"  ✗ Players START on DIFFERENT sides: {diff_team} different, {same_team} same")
            print(f"    → Team assignments vary between maps")

conn.close()

print("\n" + "=" * 80)
print("CONCLUSION:")
print("=" * 80)
print("""
If pattern shows:
1. Teams SWAP between rounds (stopwatch mode)
2. Players START on SAME side in round 1 of each map
   → We CAN use round 1 assignments to identify actual teams!
   
If players start on different sides across maps:
   → We CANNOT reliably detect teams without external roster
""")
