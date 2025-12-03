import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Check ALL weapons for carniee in session 2134
cursor.execute('''
    SELECT weapon_name, kills, deaths, headshots, hits, shots
    FROM weapon_comprehensive_stats
    WHERE round_id = 2134 AND player_guid = '0A26D447'
    ORDER BY weapon_name
''')

print("All weapons for carniee (0A26D447) in session 2134:")
for row in cursor.fetchall():
    print(f"  {row[0]:20s} K:{row[1]:2d} D:{row[2]:2d} HS:{row[3]:2d} H:{row[4]:3d} S:{row[5]:3d}")

print("\nLooking for WS_MP40 specifically:")
cursor.execute('''
    SELECT * FROM weapon_comprehensive_stats
    WHERE round_id = 2134 AND player_guid = '0A26D447' AND weapon_name = 'WS_MP40'
''')
result = cursor.fetchone()
if result:
    print(f"  FOUND: {result}")
else:
    print("  NOT FOUND IN DATABASE")

conn.close()
