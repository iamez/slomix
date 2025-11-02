"""
Deep dive into Oct 28 Round 1 RAW data
"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("="*80)
print("OCT 28, 2024 - RAW DATA INSPECTION")
print("="*80)

# First, what maps were played?
cursor.execute("""
    SELECT DISTINCT map_name
    FROM player_comprehensive_stats
    WHERE session_date = '2024-10-28'
""")

maps = [row[0] for row in cursor.fetchall()]
print(f"\nMaps played on Oct 28: {maps}")

# Take the first map
first_map = maps[0] if maps else None
print(f"First map: {first_map}\n")

# Get ALL records for Round 1 of first map (no deduplication yet)
print("="*80)
print(f"ROUND 1 - {first_map} - ALL RAW RECORDS")
print("="*80)

cursor.execute("""
    SELECT 
        id,
        player_guid,
        player_name,
        team,
        kills,
        deaths,
        damage_given,
        time_played_minutes,
        round_number
    FROM player_comprehensive_stats
    WHERE session_date = '2024-10-28'
      AND map_name = ?
      AND round_number = 1
    ORDER BY player_guid, team, time_played_minutes
""", (first_map,))

rows = cursor.fetchall()

print(f"\nTotal records: {len(rows)}\n")

# Group by player
from collections import defaultdict
by_player = defaultdict(list)

for row in rows:
    guid = row[1]
    by_player[guid].append({
        'id': row[0],
        'name': row[2],
        'team': row[3],
        'kills': row[4],
        'deaths': row[5],
        'damage': row[6],
        'time': row[7],
        'round': row[8]
    })

print(f"Unique players (by GUID): {len(by_player)}\n")

# Show each player's records
for guid, records in sorted(by_player.items(), key=lambda x: x[1][0]['name']):
    player_name = records[0]['name']
    print(f"{'='*80}")
    print(f"Player: {player_name} (GUID: {guid})")
    print(f"{'='*80}")
    print(f"Number of records: {len(records)}\n")
    
    print(f"{'ID':<8} {'Team':<10} {'Time':<10} {'K':<5} {'D':<5} {'DMG':<8}")
    print("-"*80)
    
    for rec in records:
        team_name = "Axis" if rec['team'] == 1 else "Allies"
        print(f"{rec['id']:<8} {team_name:<10} {rec['time']:<10.2f} {rec['kills']:<5} {rec['deaths']:<5} {rec['damage']:<8}")
    
    print()

# Now show: if we take ONLY the LAST record per player per team
print("="*80)
print("DEDUPLICATION: Taking LAST record per player per team")
print("="*80)

final_records = {}

for guid, records in by_player.items():
    # Group by team
    by_team = defaultdict(list)
    for rec in records:
        by_team[rec['team']].append(rec)
    
    # Take the last (max time) for each team
    for team, team_records in by_team.items():
        last = max(team_records, key=lambda x: (x['time'], x['id']))
        if guid not in final_records:
            final_records[guid] = {}
        final_records[guid][team] = last

print(f"\nAfter deduplication:\n")

# Show which teams each player appears on
for guid, teams in sorted(final_records.items(), key=lambda x: list(x[1].values())[0]['name']):
    name = list(teams.values())[0]['name']
    team_list = []
    
    if 1 in teams:  # Axis
        team_list.append(f"Axis (K:{teams[1]['kills']}, D:{teams[1]['deaths']}, Time:{teams[1]['time']:.1f}m)")
    if 2 in teams:  # Allies
        team_list.append(f"Allies (K:{teams[2]['kills']}, D:{teams[2]['deaths']}, Time:{teams[2]['time']:.1f}m)")
    
    print(f"{name:<30} → {' AND '.join(team_list)}")

# Summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)

players_on_both = sum(1 for teams in final_records.values() if len(teams) == 2)
players_on_one = sum(1 for teams in final_records.values() if len(teams) == 1)

print(f"Players appearing on ONE team only:  {players_on_one}")
print(f"Players appearing on BOTH teams:     {players_on_both}")

if players_on_both > 0:
    print("\n💡 INTERPRETATION:")
    print("   These players switched teams during Round 1.")
    print("   The game logged stats at multiple points as they played on different sides.")
    print("   This is typical of pub/casual servers with team auto-balance or voluntary switches.")

conn.close()
