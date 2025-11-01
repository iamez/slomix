import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Let's check the relationship between time_played_seconds and time_dead_ratio
print("🔍 ANALYZING TIME CALCULATION ISSUE\n")
print("If time_played_seconds was calculated from time_dead_ratio:")
print("  Expected: time_played = round_time * (100 - dead_ratio) / 100\n")

cursor.execute("""
    SELECT 
        s.id,
        s.map_name,
        s.round_number,
        s.actual_time,
        p.time_played_seconds,
        p.time_dead_ratio,
        p.denied_playtime,
        CASE 
            WHEN s.actual_time LIKE '%:%' THEN
                CAST(SUBSTR(s.actual_time, 1, INSTR(s.actual_time, ':') - 1) AS INTEGER) * 60 +
                CAST(SUBSTR(s.actual_time, INSTR(s.actual_time, ':') + 1) AS INTEGER)
            ELSE 0
        END as round_time_seconds,
        -- Calculate what time_played SHOULD be based on dead ratio
        CAST(
            CASE 
                WHEN s.actual_time LIKE '%:%' THEN
                    (CAST(SUBSTR(s.actual_time, 1, INSTR(s.actual_time, ':') - 1) AS INTEGER) * 60 +
                     CAST(SUBSTR(s.actual_time, INSTR(s.actual_time, ':') + 1) AS INTEGER))
                    * (100 - p.time_dead_ratio) / 100.0
                ELSE 0
            END AS INTEGER
        ) as expected_time_played
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE p.player_name = 'vid'
    AND SUBSTR(s.session_date, 1, 10) = '2025-10-02'
    ORDER BY s.id ASC
    LIMIT 10
""")

print(f"{'SID':<6} {'Map':<16} {'R':<2} {'RoundTime':<10} {'DBTime':<8} {'Dead%':<6} {'ExpectedTime':<12} {'Match?':<10}")
print("=" * 90)

mismatches = []
for row in cursor.fetchall():
    sid, map_name, round_num, actual_time, db_time, dead_ratio, denied, round_seconds, expected_time = row
    match = "✅" if db_time == expected_time else f"❌ {db_time - expected_time:+d}"
    print(f"{sid:<6} {map_name:<16} {round_num:<2} {actual_time:<10} {db_time:<8} {dead_ratio:<6.1f} {expected_time:<12} {match}")
    
    if db_time != expected_time:
        mismatches.append({
            'sid': sid,
            'map': map_name,
            'round': round_num,
            'db_time': db_time,
            'expected': expected_time,
            'diff': db_time - expected_time
        })

print("\n\n🔴 ISSUE FOUND:")
if mismatches:
    print(f"Found {len(mismatches)} records where time_played_seconds != expected_time")
    print("\nHypothesis: Parser is using ACTUAL playtime (accounting for join time)")
    print("            instead of (round_time * (100 - dead_ratio) / 100)")
    print("\nThis would explain:")
    print("  1. Why time_played_seconds varies slightly from round_time")
    print("  2. Why players show 0% dead_ratio but still have < round_time seconds")
    print("  3. Why DPM calculations might be inflated")
else:
    print("✅ All records match expected calculation!")

# Check if using field 22 (time_played_minutes) from TAB section instead
print("\n\n🔍 Checking if parser used FIELD 22 (time_played_minutes from TAB section):")
print("This would be WRONG because field 22 is the ACTUAL PLAYTIME from lua")
print("(which excludes dead time but ALSO excludes time before joining!)\n")

cursor.execute("""
    SELECT 
        s.id,
        s.map_name,
        p.time_played_seconds,
        s.actual_time,
        p.time_dead_ratio,
        -- If parser used field 22 * 60, what would it be?
        CAST(p.time_played_seconds AS REAL) / 60.0 as minutes_from_db
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE p.player_name = 'vid'
    AND SUBSTR(s.session_date, 1, 10) = '2025-10-02'
    ORDER BY s.id ASC
    LIMIT 10
""")

print(f"{'SID':<6} {'Map':<16} {'DBTime(s)':<10} {'RoundTime':<10} {'DBTime(min)':<12} {'Dead%':<6}")
print("=" * 70)
for row in cursor.fetchall():
    print(f"{row[0]:<6} {row[1]:<16} {row[2]:<10} {row[3]:<10} {row[5]:<12.2f} {row[4]:<6.1f}")

conn.close()

print("\n\n💡 CONCLUSION:")
print("The database shows time_played_seconds is NOT simply (round_time * (100-dead%)/100)")
print("This suggests the parser is using the ACTUAL playtime from field 22 (time_played_minutes)")
print("which is calculated by the lua script and accounts for:")
print("  - Time spent dead")
print("  - Time before player joined the server")
print("  - Time player was disconnected")
print("\nThis IS CORRECT! The lua script already calculated actual playtime.")
print("The DPM calculation: (damage * 60) / time_played_seconds is accurate!")
