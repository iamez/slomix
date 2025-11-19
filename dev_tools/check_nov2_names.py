import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Check round 2134 player names
cursor.execute('''
    SELECT DISTINCT player_guid, player_name 
    FROM player_comprehensive_stats 
    WHERE round_id = 2134 
    ORDER BY player_name
''')

print("Players in session 2134:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

conn.close()
