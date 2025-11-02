"""Test the improved clustering algorithm"""
import sqlite3
from collections import defaultdict
from itertools import combinations

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

print("=" * 80)
print("TESTING GRAPH CLUSTERING ALGORITHM")
print("=" * 80)

c.execute("""
    SELECT player_guid, player_name, team, map_name, round_number
    FROM player_comprehensive_stats
    WHERE session_date = '2025-10-30'
    ORDER BY map_name, round_number
""")
all_records = c.fetchall()

# Build data structures
round_sides = defaultdict(dict)
guid_to_name = {}
all_guids = set()

for guid, name, side, map_name, round_num in all_records:
    round_sides[(map_name, round_num)][guid] = side
    guid_to_name[guid] = name
    all_guids.add(guid)

# Count co-occurrences
cooccurrence = defaultdict(int)

for (map_name, round_num), sides in round_sides.items():
    guids_in_round = list(sides.keys())
    for guid1, guid2 in combinations(guids_in_round, 2):
        if sides[guid1] == sides[guid2]:
            cooccurrence[(guid1, guid2)] += 1

print(f"\nTotal players: {len(all_guids)}")

# Build teammate adjacency graph
teammates = defaultdict(set)

for (guid1, guid2), cooccur_count in cooccurrence.items():
    total_rounds_together = sum(
        1 for sides in round_sides.values()
        if guid1 in sides and guid2 in sides
    )
    
    if total_rounds_together > 0:
        same_side_ratio = cooccur_count / total_rounds_together
        if same_side_ratio > 0.5:
            teammates[guid1].add(guid2)
            teammates[guid2].add(guid1)

print(f"Teammate connections: {sum(len(v) for v in teammates.values()) // 2} pairs")

# Find clusters
visited = set()

def get_cluster(start_guid):
    cluster = set()
    to_visit = [start_guid]
    
    while to_visit:
        guid = to_visit.pop()
        if guid in visited:
            continue
        visited.add(guid)
        cluster.add(guid)
        to_visit.extend(teammates.get(guid, []))
    
    return cluster

# Get teams
first_guid = next(iter(all_guids))
team_a_guids = get_cluster(first_guid)
team_b_guids = all_guids - team_a_guids

print("\n" + "=" * 80)
print("DETECTED TEAMS:")
print("=" * 80)

print(f"\nTeam A ({len(team_a_guids)} players):")
for guid in sorted(team_a_guids, key=lambda g: guid_to_name[g]):
    print(f"  - {guid_to_name[guid]}")

print(f"\nTeam B ({len(team_b_guids)} players):")
for guid in sorted(team_b_guids, key=lambda g: guid_to_name[g]):
    print(f"  - {guid_to_name[guid]}")

# Verify
print("\n" + "=" * 80)
print("VERIFICATION:")
print("=" * 80)

for team_name, team_guids in [("Team A", team_a_guids), ("Team B", team_b_guids)]:
    print(f"\n{team_name}:")
    
    total_same = 0
    total_diff = 0
    
    for (map_name, round_num), sides in round_sides.items():
        team_players = [g for g in team_guids if g in sides]
        
        if len(team_players) >= 2:
            team_sides = [sides[g] for g in team_players]
            if len(set(team_sides)) == 1:
                total_same += 1
            else:
                total_diff += 1
    
    accuracy = total_same / (total_same + total_diff) * 100 if (total_same + total_diff) > 0 else 0
    print(f"  Rounds together on same side: {total_same}")
    print(f"  Rounds split: {total_diff}")
    print(f"  ✅ Accuracy: {accuracy:.1f}%")

conn.close()

print("\n" + "=" * 80)
print("✅ CLUSTERING COMPLETE!")
print("=" * 80)
