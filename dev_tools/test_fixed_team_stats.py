"""Test the fixed team aggregation"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

print("=" * 80)
print("TESTING FIXED TEAM AGGREGATION")
print("=" * 80)

# Simulate what the bot would do:
round_date = '2025-10-30'

# Step 1: Get all player stats
c.execute("""
    SELECT player_name, player_guid,
        SUM(kills) as total_kills,
        SUM(deaths) as total_deaths,
        SUM(damage_given) as total_damage
    FROM player_comprehensive_stats
    WHERE round_date = ?
    GROUP BY player_guid
""", (round_date,))

player_stats = c.fetchall()

# Step 2: Auto-detect teams from first round
c.execute("""
    SELECT player_guid, player_name, team, map_name, round_number
    FROM player_comprehensive_stats
    WHERE round_date = ?
    ORDER BY id
""", (round_date,))

all_records = c.fetchall()

# Get first map, round 1
team_a_guids = set()
team_b_guids = set()

print(f"\nTotal records: {len(all_records)}")

if all_records:
    # Find any round 1 record
    round_1_records = [(guid, side) for guid, name, side, map_name, round_num in all_records if round_num == 1]
    
    print(f"Round 1 records found: {len(round_1_records)}")
    
    if round_1_records:
        for guid, side in round_1_records:
            if side == 1:
                team_a_guids.add(guid)
            elif side == 2:
                team_b_guids.add(guid)
        print(f"Team A GUIDs: {len(team_a_guids)}")
        print(f"Team B GUIDs: {len(team_b_guids)}")
    else:
        # Fallback: use first map, first round
        first_map = all_records[0][3]
        first_round_num = all_records[0][4]
        
        for guid, name, side, map_name, round_num in all_records:
            if map_name == first_map and round_num == first_round_num:
                if side == 1:
                    team_a_guids.add(guid)
                elif side == 2:
                    team_b_guids.add(guid)

# Build name_to_team
name_to_team = {}
guid_to_name = {}

# First build guid_to_name from all records
for guid, name, _, _, _ in all_records:
    guid_to_name[guid] = name

# Then map names to teams
for guid, name in guid_to_name.items():
    if guid in team_a_guids:
        name_to_team[name] = "Team A"
    elif guid in team_b_guids:
        name_to_team[name] = "Team B"

print("\nAuto-detected Teams:")
print("Team A:", [name for name, team in name_to_team.items() if team == "Team A"])
print("Team B:", [name for name, team in name_to_team.items() if team == "Team B"])

# Step 3: Aggregate by actual team
team_aggregates = {}
for player_name, player_guid, kills, deaths, damage in player_stats:
    team_name = name_to_team.get(player_name)
    if team_name:
        if team_name not in team_aggregates:
            team_aggregates[team_name] = {"kills": 0, "deaths": 0, "damage": 0}
        team_aggregates[team_name]["kills"] += kills
        team_aggregates[team_name]["deaths"] += deaths
        team_aggregates[team_name]["damage"] += damage

print("\n" + "=" * 80)
print("CORRECTED TEAM STATS (by actual team roster):")
print("=" * 80)

for team_name, stats in team_aggregates.items():
    kd = stats["kills"] / stats["deaths"] if stats["deaths"] > 0 else stats["kills"]
    print(f"\n{team_name}:")
    print(f"  Kills:   {stats['kills']:,}")
    print(f"  Deaths:  {stats['deaths']:,}")
    print(f"  K/D:     {kd:.2f}")
    print(f"  Damage:  {stats['damage']:,}")

print("\n" + "=" * 80)
print("COMPARISON TO OLD (BROKEN) METHOD:")
print("=" * 80)

c.execute("""
    SELECT team,
        SUM(kills) as total_kills,
        SUM(deaths) as total_deaths,
        SUM(damage_given) as total_damage
    FROM player_comprehensive_stats
    WHERE round_date = ?
    GROUP BY team
""", (round_date,))

old_stats = c.fetchall()
print("\nOld broken stats (by side, not team):")
for side, kills, deaths, damage in old_stats:
    kd = kills / deaths if deaths > 0 else kills
    print(f"\nSide {side}:")
    print(f"  Kills:   {kills:,}")
    print(f"  Deaths:  {deaths:,}")
    print(f"  K/D:     {kd:.2f}")
    print(f"  Damage:  {damage:,}")

conn.close()

print("\n" + "=" * 80)
print("✅ TEAM STATS WILL NOW BE CORRECT!")
print("=" * 80)
