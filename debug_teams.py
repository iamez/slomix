import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

c.execute("""
    SELECT player_name, player_guid, team, map_name, round_number 
    FROM player_comprehensive_stats 
    WHERE session_date='2025-10-30' 
    ORDER BY id 
    LIMIT 20
""")

print("First 20 records:")
for r in c.fetchall():
    print(f"{r[0]:<20} {r[1][:8]} Team {r[2]} | {r[3]:<20} Round {r[4]}")

conn.close()
