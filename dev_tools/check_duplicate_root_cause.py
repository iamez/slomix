import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Check for duplicates
cursor.execute("""
    SELECT player_name, player_guid, team, round_number, 
           kills, deaths, damage_given, time_played_minutes
    FROM player_comprehensive_stats
    WHERE round_date = '2025-11-01' 
    AND round_number = 1
    AND player_guid = '0A26D447'
    ORDER BY team, time_played_minutes
""")

rows = cursor.fetchall()
print(f"slomix.carniee (GUID: 0A26D447) - {len(rows)} entries in Round 1:\n")
print(f"{'Team':<10} {'Round':<10} {'Kills':<10} {'Deaths':<10} {'DMG':<10} {'Time':<10}")
print("-" * 70)
for row in rows:
    team_name = "Axis" if row[2] == 1 else "Allies"
    print(f"{team_name:<10} {row[3]:<10} {row[4]:<10} {row[5]:<10} {row[6]:<10} {row[7]:<10.2f}")

print("\n" + "="*70)
print("ANALYSIS: Why are there multiple records for the same player/round/team?")
print("="*70)

# Check if there's a weapon or class breakdown
cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
columns = [row[1] for row in cursor.fetchall()]
print(f"\nChecking for breakdown columns...")
if 'weapon' in columns or 'class' in columns or 'weapon_id' in columns or 'class_id' in columns:
    print("✅ Found weapon/class columns!")
else:
    print("❌ No weapon/class columns found")
    print(f"\nAll columns: {columns}")

conn.close()
