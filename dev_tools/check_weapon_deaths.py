import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT player_name, weapon_name, kills, deaths 
    FROM weapon_comprehensive_stats 
    WHERE round_id = 2134 
    ORDER BY player_name, weapon_name
''')

rows = cursor.fetchall()
print(f"Session 2134 (Round 1) - Weapon stats:")
print(f"Total rows: {len(rows)}\n")

deaths_count = sum(1 for row in rows if row[3] > 0)
print(f"Weapons with deaths > 0: {deaths_count}")
print(f"Weapons with deaths = 0: {len(rows) - deaths_count}\n")

print("All weapon entries:")
for row in rows:
    print(f"  {row[0]:20s} {row[1]:25s} Kills:{row[2]:3d} Deaths:{row[3]:3d}")

conn.close()
