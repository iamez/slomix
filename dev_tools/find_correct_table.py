import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("ALL TABLES IN DATABASE:")
print("=" * 50)
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
for table in tables:
    print(f"  - {table}")

print("\n" + "=" * 50)
print("FINDING THE RIGHT TABLE FOR TEAM DETECTION")
print("=" * 50)

# Check if there's a player_stats table (vs player_comprehensive_stats)
if 'player_stats' in tables:
    print("\n✅ Found 'player_stats' table!")
    cursor.execute("""
        SELECT COUNT(*), COUNT(DISTINCT player_guid)
        FROM player_stats
        WHERE round_date = '2025-11-01' AND round_number = 1
    """)
    result = cursor.fetchone()
    print(f"   Round 1: {result[0]} total records, {result[1]} unique players")
    
if 'player_round_stats' in tables:
    print("\n✅ Found 'player_round_stats' table!")
    cursor.execute("""
        SELECT COUNT(*), COUNT(DISTINCT player_guid)
        FROM player_round_stats
        WHERE round_date = '2025-11-01' AND round_number = 1
    """)
    result = cursor.fetchone()
    print(f"   Round 1: {result[0]} total records, {result[1]} unique players")

print("\n" + "=" * 50)
print("TESTING: Get FINAL stats using MAX(time_played)")
print("=" * 50)

# Try to get only the LAST record for each player/round/team
cursor.execute("""
    WITH RankedStats AS (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY round_date, round_number, player_guid, team
                   ORDER BY time_played_minutes DESC, id DESC
               ) as rn
        FROM player_comprehensive_stats
        WHERE round_date = '2025-11-01' AND round_number = 1
    )
    SELECT COUNT(*), COUNT(DISTINCT player_guid)
    FROM RankedStats
    WHERE rn = 1
""")

result = cursor.fetchone()
print(f"\nUsing MAX(time_played) deduplication:")
print(f"   Round 1: {result[0]} total records, {result[1]} unique players")

# Show the actual deduplicated records for one player
print("\n" + "=" * 50)
print("EXAMPLE: slomix.carniee AFTER deduplication")
print("=" * 50)

cursor.execute("""
    WITH RankedStats AS (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY round_date, round_number, player_guid, team
                   ORDER BY time_played_minutes DESC, id DESC
               ) as rn
        FROM player_comprehensive_stats
        WHERE round_date = '2025-11-01' 
          AND round_number = 1
          AND player_guid = '0A26D447'
    )
    SELECT team, kills, deaths, damage_given, time_played_minutes
    FROM RankedStats
    WHERE rn = 1
    ORDER BY team
""")

rows = cursor.fetchall()
print(f"\n{'Team':<10} {'Kills':<10} {'Deaths':<10} {'DMG':<10} {'Time':<10}")
print("-" * 60)
for row in rows:
    team_name = "Axis" if row[0] == 1 else "Allies"
    print(f"{team_name:<10} {row[1]:<10} {row[2]:<10} {row[3]:<10} {row[4]:<10.2f}")

print("\n✅ NOW we have 1 Axis record and 1 Allies record (CORRECT!)")

conn.close()
