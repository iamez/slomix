"""
Check if Oct 28 has distinct teams (not everyone on both sides)
"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Get deduplicated data for Oct 28, Round 1
cursor.execute("""
    WITH RankedStats AS (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY round_date, round_number, player_guid, team
                   ORDER BY time_played_minutes DESC, id DESC
               ) as rn
        FROM player_comprehensive_stats
        WHERE round_date = '2024-10-28' AND round_number = 1
    )
    SELECT player_guid, player_name, team
    FROM RankedStats
    WHERE rn = 1
    ORDER BY player_guid, team
""")

rows = cursor.fetchall()

# Group by GUID
from collections import defaultdict
player_teams = defaultdict(list)

for guid, name, team in rows:
    player_teams[guid].append((name, team))

print("="*80)
print("OCT 28 - ROUND 1 - PLAYER TEAM ANALYSIS")
print("="*80)

players_on_both = []
players_on_one = []

for guid, teams_data in player_teams.items():
    name = teams_data[0][0]
    teams = [t[1] for t in teams_data]
    
    if len(teams) == 2:
        print(f"❌ {name:<30} - ON BOTH TEAMS (Axis + Allies)")
        players_on_both.append(name)
    else:
        team_name = "Axis" if teams[0] == 1 else "Allies"
        print(f"✅ {name:<30} - {team_name} only")
        players_on_one.append(name)

print("\n" + "="*80)
print("VERDICT:")
print("="*80)
print(f"Players on ONE team only:  {len(players_on_one)}")
print(f"Players on BOTH teams:     {len(players_on_both)}")

if len(players_on_both) > 0:
    print("\n❌ THIS IS NOT A PROPER ORGANIZED MATCH!")
    print("   All players appear on both Axis AND Allies in same round.")
    print("   This is public/mixed server data, not stopwatch teams.")
else:
    print("\n✅ THIS IS A PROPER ORGANIZED MATCH!")
    print("   Players are on distinct teams.")

conn.close()
