import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Check vid's October 2nd stats
cursor.execute("""
    SELECT COUNT(*), SUM(kills), SUM(deaths), SUM(damage_given)
    FROM player_comprehensive_stats
    WHERE session_date LIKE '2025-10-02%'
    AND player_name = 'vid'
""")

result = cursor.fetchone()
print(f"\nvid's October 2nd stats from DATABASE:")
print(f"  Records: {result[0]}")
print(f"  Total kills: {result[1]}")
print(f"  Total deaths: {result[2]}")
print(f"  Total damage: {result[3]}")

# Check all players
cursor.execute("""
    SELECT 
        player_name,
        COUNT(*) as records,
        SUM(kills) as kills,
        SUM(deaths) as deaths
    FROM player_comprehensive_stats
    WHERE session_date LIKE '2025-10-02%'
    GROUP BY player_name
    ORDER BY kills DESC
""")

print(f"\n\nAll players on October 2nd:")
print(f"{'Player':<20} {'Records':<10} {'Kills':<10} {'Deaths':<10}")
print("="*60)
for row in cursor.fetchall():
    print(f"{row[0]:<20} {row[1]:<10} {row[2]:<10} {row[3]:<10}")

conn.close()
