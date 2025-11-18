import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

# Check player-level headshots for all players in session 2134
c.execute('''
    SELECT player_name, headshot_kills, kills, deaths 
    FROM player_comprehensive_stats 
    WHERE round_id=2134
    ORDER BY player_name
''')

print("Player-level headshots in database for session 2134:")
for r in c.fetchall():
    print(f"  {r[0]:20s} HS:{r[1]:3d} K:{r[2]:3d} D:{r[3]:3d}")

# Check weapon-level headshots
print("\nWeapon-level headshots summed by player:")
c.execute('''
    SELECT player_name, SUM(headshots) as total_hs
    FROM weapon_comprehensive_stats
    WHERE round_id=2134
    GROUP BY player_guid, player_name
    ORDER BY player_name
''')

for r in c.fetchall():
    print(f"  {r[0]:20s} HS:{r[1]:3d}")

conn.close()
