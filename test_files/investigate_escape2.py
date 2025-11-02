"""Investigate the weird te_escape2 data"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

print("=" * 80)
print("INVESTIGATING te_escape2 ANOMALY")
print("=" * 80)

# Get all te_escape2 data
c.execute("""
    SELECT map_name, round_number, player_name, player_guid, team, kills, deaths
    FROM player_comprehensive_stats
    WHERE session_date = '2025-10-30' AND map_name = 'te_escape2'
    ORDER BY round_number, team, player_name
""")

data = c.fetchall()

print(f"\nTotal records for te_escape2: {len(data)}")

# Group by round
rounds = {}
for map_name, round_num, player, guid, team, kills, deaths in data:
    if round_num not in rounds:
        rounds[round_num] = {'team1': [], 'team2': []}
    
    if team == 1:
        rounds[round_num]['team1'].append((player, guid, kills, deaths))
    elif team == 2:
        rounds[round_num]['team2'].append((player, guid, kills, deaths))

print("\n" + "=" * 80)
print("ROUND-BY-ROUND ANALYSIS:")
print("=" * 80)

for round_num in sorted(rounds.keys()):
    print(f"\n{'='*80}")
    print(f"ROUND {round_num}:")
    print('='*80)
    
    team1 = rounds[round_num]['team1']
    team2 = rounds[round_num]['team2']
    
    print(f"\nTeam 1 ({len(team1)} players):")
    for player, guid, kills, deaths in team1:
        print(f"  {player:<20} {guid[:8]} | {kills}K/{deaths}D")
    
    print(f"\nTeam 2 ({len(team2)} players):")
    for player, guid, kills, deaths in team2:
        print(f"  {player:<20} {guid[:8]} | {kills}K/{deaths}D")
    
    # Check for duplicates
    all_players = [(p, g) for p, g, _, _ in team1] + [(p, g) for p, g, _, _ in team2]
    guids = [g for _, g in all_players]
    
    if len(guids) != len(set(guids)):
        print("\n⚠️  DUPLICATE PLAYERS DETECTED!")
        from collections import Counter
        guid_counts = Counter(guids)
        for guid, count in guid_counts.items():
            if count > 1:
                player_name = next(p for p, g in all_players if g == guid)
                print(f"  {player_name} ({guid[:8]}) appears {count} times")

# Compare with other maps
print("\n" + "=" * 80)
print("COMPARISON WITH OTHER MAPS:")
print("=" * 80)

c.execute("""
    SELECT DISTINCT map_name, round_number, COUNT(*) as player_count
    FROM player_comprehensive_stats
    WHERE session_date = '2025-10-30'
    GROUP BY map_name, round_number
    ORDER BY map_name, round_number
""")

map_data = c.fetchall()

print(f"\n{'Map':<20} {'Round':<8} {'Players'}")
print("-" * 50)
for map_name, round_num, count in map_data:
    indicator = " ⚠️ ANOMALY!" if count > 10 else ""
    print(f"{map_name:<20} {round_num:<8} {count}{indicator}")

# Check for player stats appearing multiple times in same round
print("\n" + "=" * 80)
print("CHECKING FOR DUPLICATE ENTRIES:")
print("=" * 80)

c.execute("""
    SELECT map_name, round_number, player_guid, player_name, COUNT(*) as entry_count
    FROM player_comprehensive_stats
    WHERE session_date = '2025-10-30'
    GROUP BY map_name, round_number, player_guid
    HAVING entry_count > 1
    ORDER BY map_name, round_number, entry_count DESC
""")

duplicates = c.fetchall()

if duplicates:
    print(f"\nFound {len(duplicates)} duplicate player entries:")
    for map_name, round_num, guid, player, count in duplicates:
        print(f"  {map_name:<20} Round {round_num} | {player:<20} appears {count}x")
else:
    print("\n✓ No duplicate entries found")

# Check session_ids for te_escape2
print("\n" + "=" * 80)
print("SESSION IDS FOR te_escape2:")
print("=" * 80)

c.execute("""
    SELECT DISTINCT session_id, round_number, COUNT(*) as records
    FROM player_comprehensive_stats
    WHERE session_date = '2025-10-30' AND map_name = 'te_escape2'
    GROUP BY session_id, round_number
    ORDER BY session_id, round_number
""")

sessions = c.fetchall()
print(f"\n{'Session ID':<12} {'Round':<8} {'Records'}")
print("-" * 40)
for sid, round_num, count in sessions:
    print(f"{sid:<12} {round_num:<8} {count}")

conn.close()

print("\n" + "=" * 80)
