"""Test the smart team detection algorithm"""
import sqlite3
from collections import defaultdict
from itertools import combinations

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

print("=" * 80)
print("TESTING SMART TEAM DETECTION ALGORITHM")
print("=" * 80)

# Get all records
c.execute("""
    SELECT player_guid, player_name, team, map_name, round_number
    FROM player_comprehensive_stats
    WHERE session_date = '2025-10-30'
    ORDER BY map_name, round_number
""")
all_records = c.fetchall()

# Build round-by-round side assignments
round_sides = defaultdict(dict)
guid_to_name = {}
all_guids = set()

for guid, name, side, map_name, round_num in all_records:
    round_sides[(map_name, round_num)][guid] = side
    guid_to_name[guid] = name
    all_guids.add(guid)

print(f"\nTotal players: {len(all_guids)}")
print(f"Total rounds: {len(round_sides)}")

# Count co-occurrences
cooccurrence = defaultdict(int)

for (map_name, round_num), sides in round_sides.items():
    guids_in_round = list(sides.keys())
    for guid1, guid2 in combinations(guids_in_round, 2):
        if sides[guid1] == sides[guid2]:
            cooccurrence[(guid1, guid2)] += 1

print(f"\nCo-occurrence pairs tracked: {len(cooccurrence)}")

# Build teams
team_a_guids = set()
team_b_guids = set()
unassigned = set(all_guids)

# Pick first player
seed_guid = next(iter(unassigned))
team_a_guids.add(seed_guid)
unassigned.remove(seed_guid)

print(f"\nSeed player: {guid_to_name[seed_guid]}")

# Assign based on co-occurrence
print("\nAssignment analysis:")
for guid in list(unassigned):
    cooccur_count = cooccurrence.get((min(seed_guid, guid), max(seed_guid, guid)), 0)
    total_rounds_together = sum(1 for sides in round_sides.values() if seed_guid in sides and guid in sides)
    
    if total_rounds_together > 0:
        same_side_ratio = cooccur_count / total_rounds_together
        team = "A" if same_side_ratio > 0.5 else "B"
        
        print(f"  {guid_to_name[guid]:<20} Same side: {cooccur_count}/{total_rounds_together} = {same_side_ratio:.1%} → Team {team}")
        
        if same_side_ratio > 0.5:
            team_a_guids.add(guid)
        else:
            team_b_guids.add(guid)
        unassigned.remove(guid)

team_b_guids.update(unassigned)

print("\n" + "=" * 80)
print("DETECTED TEAMS:")
print("=" * 80)

print(f"\nTeam A ({len(team_a_guids)} players):")
for guid in team_a_guids:
    print(f"  - {guid_to_name[guid]}")

print(f"\nTeam B ({len(team_b_guids)} players):")
for guid in team_b_guids:
    print(f"  - {guid_to_name[guid]}")

# Verify accuracy
print("\n" + "=" * 80)
print("VERIFICATION:")
print("=" * 80)

# Check if detected teams actually play together
for team_name, team_guids in [("Team A", team_a_guids), ("Team B", team_b_guids)]:
    print(f"\n{team_name} consistency check:")
    
    total_same = 0
    total_diff = 0
    
    for (map_name, round_num), sides in round_sides.items():
        team_players_in_round = [guid for guid in team_guids if guid in sides]
        
        if len(team_players_in_round) >= 2:
            # Check if they're all on same side
            team_sides = [sides[guid] for guid in team_players_in_round]
            if len(set(team_sides)) == 1:
                total_same += 1
            else:
                total_diff += 1
    
    accuracy = total_same / (total_same + total_diff) * 100 if (total_same + total_diff) > 0 else 0
    print(f"  Rounds together on same side: {total_same}")
    print(f"  Rounds split across sides: {total_diff}")
    print(f"  Accuracy: {accuracy:.1f}%")

conn.close()

print("\n" + "=" * 80)
print("✅ SMART DETECTION COMPLETE!")
print("=" * 80)
