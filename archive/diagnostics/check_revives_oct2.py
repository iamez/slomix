import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

# Same query as !last_session uses
c.execute("""
    SELECT player_name, SUM(times_revived) as revives
    FROM player_comprehensive_stats
    WHERE session_date LIKE '2025-10-02%'
    GROUP BY player_name
    ORDER BY revives DESC
    LIMIT 10
""")

print("Revives on Oct 2 (using times_revived column):")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]} revives")

conn.close()
