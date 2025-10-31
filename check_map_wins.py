import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# First, check column names
cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
date_cols = [c[1] for c in cursor.fetchall() if 'date' in c[1].lower() or 'time' in c[1].lower()]
print(f"Date/time columns: {date_cols}\n")

# Get maps for October 2nd
cursor.execute('''
    SELECT DISTINCT map_name 
    FROM player_comprehensive_stats 
    WHERE session_date LIKE '2025-10-02%'
''')
maps = [r[0] for r in cursor.fetchall()]

print(f"Total maps: {len(maps)}")
for i, m in enumerate(maps, 1):
    print(f"{i}. {m}")

# Check if we have objective_captured or time data
cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
cols = [c[1] for c in cursor.fetchall() if 'obj' in c[1].lower() or 'time' in c[1].lower() or 'capt' in c[1].lower()]
print(f"\nObjective/time columns: {cols}")

conn.close()
