import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

# Check syringe data for Oct 2
c.execute("""
    SELECT player_name, SUM(kills) as revives
    FROM weapon_comprehensive_stats
    WHERE weapon_name = 'WS_SYRINGE'
    AND session_date LIKE '2025-10-02%'
    GROUP BY player_name
    ORDER BY revives DESC
    LIMIT 10
""")

print("Syringe kills (revives given) on Oct 2:")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]} revives")

conn.close()
