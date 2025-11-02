import sqlite3
from collections import defaultdict
from itertools import combinations

db_path = 'bot/etlegacy_production.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Test on the 2025-10-30 session with multiple te_escape2 plays
session_date = '2025-10-30'

# Get all player-side pairings WITH session_id
query = """
    SELECT player_guid, player_name, team, session_id, map_name, round_number
    FROM player_comprehensive_stats
    WHERE session_date LIKE ? AND map_name = 'te_escape2'
    ORDER BY session_id, map_name, round_number
"""
cursor.execute(query, (f'{session_date}%',))
all_records = cursor.fetchall()

print(f"Testing team detection on {session_date}")
print(f"Found {len(all_records)} te_escape2 records\n")

# Build round-by-round side assignments: (session_id, map, round) -> {guid: side}
round_sides = defaultdict(dict)
guid_to_name = {}
all_guids = set()

for guid, name, side, sess_id, map_name, round_num in all_records:
    round_sides[(sess_id, map_name, round_num)][guid] = side
    guid_to_name[guid] = name
    all_guids.add(guid)

print(f"Unique rounds (by session_id, map, round): {len(round_sides)}")
for key in sorted(round_sides.keys()):
    print(f"  Session {key[0]}, {key[1]}, Round {key[2]}: {len(round_sides[key])} players")

# Count how often each pair of players is on the SAME side
cooccurrence = defaultdict(int)

for (sess_id, map_name, round_num), sides in round_sides.items():
    guids_in_round = list(sides.keys())
    for guid1, guid2 in combinations(guids_in_round, 2):
        if sides[guid1] == sides[guid2]:
            cooccurrence[(guid1, guid2)] += 1

# Build adjacency
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

# Find clusters
team_a_guids = set()
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

if all_guids:
    first_guid = next(iter(all_guids))
    team_a_guids = get_cluster(first_guid)
    team_b_guids = all_guids - team_a_guids
    
    print(f"\n✅ Team Detection Results:")
    print(f"\nTeam A ({len(team_a_guids)} players):")
    for guid in sorted(team_a_guids):
        print(f"  - {guid_to_name[guid]}")
    
    print(f"\nTeam B ({len(team_b_guids)} players):")
    for guid in sorted(team_b_guids):
        print(f"  - {guid_to_name[guid]}")
    
    # Verify by checking actual round assignments
    print(f"\n📊 Verification - checking round assignments:")
    for (sess_id, map_name, round_num), sides in sorted(round_sides.items()):
        print(f"\n  Session {sess_id}, Round {round_num}:")
        side_1 = [guid_to_name[g] for g, s in sides.items() if s == 1]
        side_2 = [guid_to_name[g] for g, s in sides.items() if s == 2]
        print(f"    Side 1: {', '.join(side_1)}")
        print(f"    Side 2: {', '.join(side_2)}")
        
        # Check if detected teams match this round
        team_a_names = [guid_to_name[g] for g in team_a_guids if g in sides]
        team_b_names = [guid_to_name[g] for g in team_b_guids if g in sides]
        
        team_a_side = sides.get(next(iter(team_a_guids & sides.keys()), None))
        team_b_side = sides.get(next(iter(team_b_guids & sides.keys()), None))
        
        if team_a_side == 1 and team_b_side == 2:
            print(f"    ✅ Team A on Side 1, Team B on Side 2")
        elif team_a_side == 2 and team_b_side == 1:
            print(f"    ✅ Team A on Side 2, Team B on Side 1")
        else:
            print(f"    ❌ Mixed teams detected!")

conn.close()
