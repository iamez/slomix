"""
Check the most recent stats in the database vs raw files
"""
import sqlite3
import os

db_path = "etlegacy_production.db"

# Get the most recent session
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Find recent sessions
cursor.execute("""
    SELECT round_id, map_name, round_number, timestamp
    FROM rounds
    ORDER BY round_id DESC
    LIMIT 5
""")

print("📊 Most Recent Sessions:")
print("=" * 80)
for row in cursor.fetchall():
    print(f"Session {row[0]}: {row[1]} - Round {row[2]} - {row[3]}")

# Get the latest session
cursor.execute("""
    SELECT round_id, map_name, round_number
    FROM rounds
    ORDER BY round_id DESC
    LIMIT 1
""")

session = cursor.fetchone()
round_id, map_name, round_num = session

print(f"\n🔍 Analyzing Session {round_id}: {map_name} Round {round_num}")
print("=" * 80)

# Get player stats - check ALL fields
cursor.execute("""
    SELECT 
        player_name,
        kills, deaths, 
        damage_given, damage_received,
        team_damage_given, team_damage_received,
        gibs, headshot_kills,
        revives, times_revived,
        accuracy,
        time_dead_minutes,
        efficiency, kd_ratio
    FROM player_comprehensive_stats
    WHERE round_id = ? AND round_number = ?
    ORDER BY kills DESC
    LIMIT 3
""", (round_id, round_num))

print("\n📋 Top 3 Players from Database:")
for row in cursor.fetchall():
    name, kills, deaths, dmg_g, dmg_r, tdmg_g, tdmg_r, gibs, hs, revs, times_rev, acc, time_dead, eff, kd = row
    print(f"\n{name}:")
    print(f"  K/D: {kills}/{deaths} (KD: {kd})")
    print(f"  Damage: {dmg_g} given, {dmg_r} received")
    print(f"  Team Damage: {tdmg_g} given, {tdmg_r} received")
    print(f"  Gibs: {gibs}, Headshots: {hs}")
    print(f"  Revives: {revs}, Times Revived: {times_rev}")
    print(f"  Accuracy: {acc}%, Time Dead: {time_dead} min")
    print(f"  Efficiency: {eff}%")

# Check player_objective_stats too
cursor.execute("""
    SELECT 
        player_guid,
        dynamites_planted, dynamites_defused,
        objectives_stolen, objectives_returned,
        kill_assists, kill_steals
    FROM player_objective_stats
    WHERE round_id = ?
    LIMIT 3
""", (round_id,))

print("\n📊 Player Objective Stats:")
for row in cursor.fetchall():
    guid, dyn_p, dyn_d, obj_s, obj_r, assists, steals = row
    print(f"  GUID {guid[:8]}: Dyn Plant/Def: {dyn_p}/{dyn_d}, Obj S/R: {obj_s}/{obj_r}, Assists: {assists}")

conn.close()

# Now check the raw file
raw_file_path = f"bot/local_stats/2025-11-02-000624-etl_adlernest-round-2.txt"
if os.path.exists(raw_file_path):
    print(f"\n📄 Raw File: {raw_file_path}")
    print("=" * 80)
    with open(raw_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print(f"Total lines in file: {len(lines)}")
        print(f"\nFirst player line (sample):")
        # Find first player line (starts with GUID)
        for line in lines:
            if line.strip() and not line.startswith('*') and '\\' in line:
                print(line[:200] + "...")
                break
else:
    print(f"\n⚠️ Raw file not found: {raw_file_path}")
