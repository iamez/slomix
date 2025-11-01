import sqlite3

# Check the backup database from this morning
conn = sqlite3.connect('backups/fiveeyes_pre_implementation_20251006_075852/etlegacy_production.db')
cursor = conn.cursor()

# Check vid's October 2nd stats
cursor.execute("""
    SELECT 
        COUNT(*) as records,
        SUM(kills) as total_kills,
        SUM(deaths) as total_deaths,
        AVG(time_played_seconds) as avg_time_per_round,
        SUM(time_played_seconds) as total_time_seconds
    FROM player_comprehensive_stats
    WHERE player_name = 'vid'
    AND session_id IN (
        SELECT id FROM sessions 
        WHERE SUBSTR(session_date, 1, 10) = '2025-10-02'
    )
""")

row = cursor.fetchone()
print(f"📊 Vid's October 2nd stats in BACKUP database:")
print(f"  Records: {row[0]}")
print(f"  Total kills: {row[1]}")
print(f"  Total deaths: {row[2]}")
print(f"  Avg time/round: {row[3]:.1f} seconds")
print(f"  Total time: {row[4]} seconds = {row[4]//60} minutes {row[4]%60} seconds")

# Check if everyone had same time
cursor.execute("""
    SELECT 
        player_name,
        COUNT(*) as records,
        AVG(time_played_seconds) as avg_time,
        SUM(time_played_seconds) as total_time
    FROM player_comprehensive_stats
    WHERE session_id IN (
        SELECT id FROM sessions 
        WHERE SUBSTR(session_date, 1, 10) = '2025-10-02'
    )
    GROUP BY player_name
    ORDER BY player_name
""")

print(f"\n📊 All players October 2nd (from backup):")
print(f"{'Player':<20} {'Records':<8} {'AvgTime/Round':<15} {'TotalTime':<15}")
print("=" * 70)
for row in cursor.fetchall():
    total_mins = row[3] // 60
    total_secs = row[3] % 60
    print(f"{row[0]:<20} {row[1]:<8} {row[2]:<15.1f} {total_mins}m {total_secs}s")

conn.close()
