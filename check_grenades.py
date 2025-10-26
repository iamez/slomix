import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

# Check grenade stats
c.execute("""
    SELECT weapon_name, SUM(kills) as kills, SUM(shots) as shots, SUM(hits) as hits
    FROM weapon_comprehensive_stats
    WHERE weapon_name LIKE '%GRENADE%'
    GROUP BY weapon_name
""")

print("Grenade Weapons:")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,} kills | {row[2]:,} shots | {row[3]:,} hits")

# Check launcher
c.execute("""
    SELECT weapon_name, SUM(kills) as kills, SUM(shots) as shots, SUM(hits) as hits
    FROM weapon_comprehensive_stats
    WHERE weapon_name LIKE '%LAUNCHER%'
    GROUP BY weapon_name
""")

print("\nGrenade Launcher:")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,} kills | {row[2]:,} shots | {row[3]:,} hits")

# Check top grenade users
c.execute("""
    SELECT player_name, SUM(kills) as kills, SUM(shots) as shots, SUM(hits) as hits
    FROM weapon_comprehensive_stats
    WHERE weapon_name = 'WS_GRENADE'
    GROUP BY player_name
    ORDER BY kills DESC
    LIMIT 5
""")

print("\nTop 5 Grenadiers (WS_GRENADE):")
for row in c.fetchall():
    accuracy = (row[3] / row[2] * 100) if row[2] > 0 else 0
    print(f"  {row[0]}: {row[1]:,} kills | {row[2]:,} throws | {row[3]:,} hits ({accuracy:.1f}% acc)")

conn.close()
