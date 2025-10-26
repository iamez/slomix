import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Check vid's October 2nd time_played_seconds values
cursor.execute("""
    SELECT 
        s.id,
        s.map_name,
        s.round_number,
        s.actual_time,
        p.time_played_seconds,
        p.time_dead_ratio,
        p.denied_playtime,
        p.damage_given,
        CASE
            WHEN p.time_played_seconds > 0
            THEN (p.damage_given * 60.0) / p.time_played_seconds
            ELSE 0
        END as calculated_dpm
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE p.player_name = 'vid'
    AND SUBSTR(s.session_date, 1, 10) = '2025-10-02'
    ORDER BY s.id ASC
    LIMIT 5
""")

print("Vid's October 2nd time/DPM data (first 5 records):")
print(f"{'SID':<6} {'Map':<20} {'R':<3} {'ActualTime':<12} {'TimeSec':<8} {'Dead%':<6} {'Denied':<7} {'Damage':<7} {'DPM':<8}")
print("=" * 100)
for row in cursor.fetchall():
    print(f"{row[0]:<6} {row[1]:<20} {row[2]:<3} {row[3]:<12} {row[4]:<8} {row[5]:<6.1f} {row[6]:<7} {row[7]:<7} {row[8]:<8.1f}")

# Check if time_played_seconds matches actual_time from session
print("\n\n🔍 Comparing time_played_seconds vs actual_time:")
cursor.execute("""
    SELECT 
        s.id,
        s.map_name,
        s.actual_time,
        p.time_played_seconds,
        CASE 
            WHEN s.actual_time LIKE '%:%' THEN
                CAST(SUBSTR(s.actual_time, 1, INSTR(s.actual_time, ':') - 1) AS INTEGER) * 60 +
                CAST(SUBSTR(s.actual_time, INSTR(s.actual_time, ':') + 1) AS INTEGER)
            ELSE 0
        END as parsed_actual_seconds,
        p.time_dead_ratio
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE p.player_name = 'vid'
    AND SUBSTR(s.session_date, 1, 10) = '2025-10-02'
    ORDER BY s.id ASC
    LIMIT 10
""")

print(f"{'SID':<6} {'Map':<20} {'ActualTime':<12} {'DBTimeSec':<12} {'ParsedSec':<12} {'Dead%':<6} {'Match?':<8}")
print("=" * 100)
for row in cursor.fetchall():
    match = "✅" if row[3] == row[4] else f"❌ Diff: {row[3] - row[4]}s"
    print(f"{row[0]:<6} {row[1]:<20} {row[2]:<12} {row[3]:<12} {row[4]:<12} {row[5]:<6.1f} {match}")

# Check all October 2nd to see if there's a pattern
print("\n\n📊 Time patterns across all October 2nd players:")
cursor.execute("""
    SELECT 
        p.player_name,
        COUNT(*) as records,
        AVG(p.time_played_seconds) as avg_time_seconds,
        AVG(p.time_dead_ratio) as avg_dead_ratio,
        SUM(p.denied_playtime) as total_denied,
        AVG(CASE
            WHEN p.time_played_seconds > 0
            THEN (p.damage_given * 60.0) / p.time_played_seconds
            ELSE 0
        END) as avg_dpm
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE SUBSTR(s.session_date, 1, 10) = '2025-10-02'
    GROUP BY p.player_name
    ORDER BY avg_dpm DESC
""")

print(f"{'Player':<20} {'Records':<8} {'AvgTime(s)':<12} {'AvgDead%':<10} {'TotalDenied':<12} {'AvgDPM':<10}")
print("=" * 100)
for row in cursor.fetchall():
    print(f"{row[0]:<20} {row[1]:<8} {row[2]:<12.1f} {row[3]:<10.1f} {row[4]:<12} {row[5]:<10.1f}")

conn.close()
