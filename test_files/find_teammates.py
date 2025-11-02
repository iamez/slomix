"""Find the actual team groupings by checking who plays together"""
import sqlite3
from collections import defaultdict

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

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

for guid, name, side, map_name, round_num in all_records:
    round_sides[(map_name, round_num)][guid] = side
    guid_to_name[guid] = name

# For each pair of players, count how many rounds they were on same side
from itertools import combinations
all_guids = list(guid_to_name.keys())

print("=" * 80)
print("PLAYER CO-OCCURRENCE MATRIX")
print("=" * 80)
print("\nShowing % of rounds played together on SAME side:\n")

results = []
for guid1, guid2 in combinations(all_guids, 2):
    same_side = 0
    total_together = 0
    
    for sides in round_sides.values():
        if guid1 in sides and guid2 in sides:
            total_together += 1
            if sides[guid1] == sides[guid2]:
                same_side += 1
    
    if total_together > 0:
        pct = same_side / total_together * 100
        results.append((guid_to_name[guid1], guid_to_name[guid2], same_side, total_together, pct))

# Sort by percentage
results.sort(key=lambda x: x[4], reverse=True)

print(f"{'Player 1':<20} {'Player 2':<20} {'Same/Total':<12} {'%'}")
print("-" * 70)
for p1, p2, same, total, pct in results:
    indicator = "✓ SAME TEAM" if pct > 80 else ("? MAYBE" if pct > 40 else "✗ DIFF TEAM")
    print(f"{p1:<20} {p2:<20} {same:2}/{total:2} = {pct:5.1f}%  {indicator}")

conn.close()
