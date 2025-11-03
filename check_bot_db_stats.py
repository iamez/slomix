"""
Check the most recent stats in bot/database vs raw files
"""
import sqlite3
import os

db_path = "bot/etlegacy_production.db"

# Get the most recent session
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# First list tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("📋 Tables in database:")
for t in tables:
    print(f"  - {t[0]}")

# Find recent sessions
cursor.execute("""
    SELECT id, map_name, round_number, session_date
    FROM sessions
    ORDER BY id DESC
    LIMIT 5
""")

print("\n📊 Most Recent Sessions:")
print("=" * 80)
for row in cursor.fetchall():
    print(f"Session {row[0]}: {row[1]} - Round {row[2]} - {row[3]}")

# Get the latest session
cursor.execute("""
    SELECT id, map_name, round_number
    FROM sessions
    ORDER BY id DESC
    LIMIT 1
""")

session = cursor.fetchone()
session_id, map_name, round_num = session

print(f"\n🔍 Analyzing Session {session_id}: {map_name} Round {round_num}")
print("=" * 80)

# Get player stats - check ALL fields including the ones user says are missing
cursor.execute("""
    SELECT 
        player_name,
        kills, deaths, 
        damage_given, damage_received,
        team_damage_given, team_damage_received,
        gibs, headshot_kills,
        revives_given, times_revived,
        accuracy,
        time_dead_minutes,
        efficiency, kd_ratio
    FROM player_comprehensive_stats
    WHERE session_id = ? AND round_number = ?
    ORDER BY kills DESC
    LIMIT 5
""", (session_id, round_num))

print("\n📋 Top 5 Players from Database:")
print("=" * 80)
for row in cursor.fetchall():
    name, kills, deaths, dmg_g, dmg_r, tdmg_g, tdmg_r, gibs, hs, revs, times_rev, acc, time_dead, eff, kd = row
    print(f"\n{name}:")
    print(f"  K/D: {kills}/{deaths} (Ratio: {kd})")
    print(f"  Damage: {dmg_g} given ←→ {dmg_r} received")
    print(f"  Team Damage: {tdmg_g} given ←→ {tdmg_r} received  ⚠️")
    print(f"  Gibs: {gibs}, Headshots: {hs}  ⚠️")
    print(f"  Revives Given: {revs}  ⚠️, Times Revived: {times_rev}")
    print(f"  Accuracy: {acc}%, Time Dead: {time_dead} min")
    print(f"  Efficiency: {eff}%")

conn.close()

# Now check the corresponding raw file
# Find the raw file for this session
raw_files = os.listdir("bot/local_stats")
raw_files.sort(reverse=True)

# Match by map name and round
target_file = None
for f in raw_files[:20]:  # Check last 20 files
    if map_name in f and f"round-{round_num}.txt" in f:
        target_file = f
        break

if target_file:
    raw_file_path = f"bot/local_stats/{target_file}"
    print(f"\n📄 Raw File: {target_file}")
    print("=" * 80)
    with open(raw_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print(f"Total lines in file: {len(lines)}")
        print(f"\n🔍 Checking first 3 player lines for comparison:")
        print("=" * 80)
        
        player_count = 0
        for line in lines:
            if line.strip() and not line.startswith('*') and '\\' in line:
                # Parse player name
                parts = line.split('\\')
                if len(parts) >= 2:
                    player_name = parts[1]
                    # Remove color codes for display
                    import re
                    clean_name = re.sub(r'\^.', '', player_name)
                    
                    # Find the stats section (tab-separated values after the player data)
                    # The format has stats after many tab characters
                    stats_section = line.split('\t')
                    if len(stats_section) > 5:
                        try:
                            # Based on the field mapping report, the positions are:
                            # damage_given, damage_received, team_damage_given, team_damage_received,
                            # gibs, self_kills, team_kills, team_gibs, ...
                            # Then: xp, killing_spree, death_spree, kill_assists, kill_steals,
                            # headshot_kills, objectives_stolen, objectives_returned,
                            # dynamites_planted, dynamites_defused, times_revived
                            # Then: bullets_fired, dpm, time_played_minutes, tank_meatshield,
                            # time_dead_ratio, time_dead_minutes, kd_ratio, useful_kills,
                            # denied_playtime, multikills, useless_kills, full_selfkills,
                            # repairs_constructions, revives_given
                            
                            # Extract from stats section
                            dmg_g = stats_section[1].strip() if len(stats_section) > 1 else '?'
                            dmg_r = stats_section[2].strip() if len(stats_section) > 2 else '?'
                            tdmg_g = stats_section[3].strip() if len(stats_section) > 3 else '?'
                            tdmg_r = stats_section[4].strip() if len(stats_section) > 4 else '?'
                            gibs = stats_section[5].strip() if len(stats_section) > 5 else '?'
                            
                            # Headshots are much later (position 14 in stats section)
                            hs = stats_section[14].strip() if len(stats_section) > 14 else '?'
                            
                            # Revives given is at the end (position ~37)
                            revives = stats_section[37].strip() if len(stats_section) > 37 else '?'
                            
                            print(f"\n{clean_name} (RAW FILE):")
                            print(f"  Damage: {dmg_g} given ←→ {dmg_r} received")
                            print(f"  Team Damage: {tdmg_g} given ←→ {tdmg_r} received")
                            print(f"  Gibs: {gibs}, Headshots: {hs}")
                            print(f"  Revives Given: {revives}")
                            
                        except Exception as e:
                            print(f"  (Error parsing: {e})")
                    
                    player_count += 1
                    if player_count >= 3:
                        break
else:
    print(f"\n⚠️ Could not find matching raw file for {map_name} round {round_num}")
