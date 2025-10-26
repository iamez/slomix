import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print("Checking for duplicate session imports...\n")

# Check if sessions table has duplicates
dups = c.execute('''
    SELECT session_date, map_name, round_number, COUNT(*) as cnt
    FROM sessions
    GROUP BY session_date, map_name, round_number
    HAVING cnt > 1
    LIMIT 10
''').fetchall()

if dups:
    print(f"⚠️ Found {len(dups)} duplicate sessions:")
    for row in dups:
        print(f"  {row[0]} - {row[1]} R{row[2]}: {row[3]} times")
else:
    print("✅ No duplicate sessions in sessions table")

# Check EXACT duplicate records (same session_id, player_guid, AND stats)
print("\nChecking for exact duplicate player records...")
exact_dups = c.execute('''
    SELECT 
        session_id, player_guid, player_name,
        kills, deaths, time_played_seconds,
        COUNT(*) as cnt
    FROM player_comprehensive_stats
    GROUP BY session_id, player_guid, kills, deaths, time_played_seconds
    HAVING cnt > 1
    LIMIT 5
''').fetchall()

if exact_dups:
    print(f"\n⚠️  Found exact duplicate records:")
    for row in exact_dups:
        print(f"  Session {row[0]}: {row[2]} (GUID: {row[1]})")
        print(f"    {row[3]} kills, {row[4]} deaths, {row[5]}s - appears {row[6]} times")
else:
    print("✅ No exact duplicates found")

conn.close()
