import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

# Get all columns
cols = c.execute('PRAGMA table_info(player_comprehensive_stats)').fetchall()

print('\n=== ALL COLUMNS IN player_comprehensive_stats ===')
for col in cols:
    print(f'{col[0]:2d}. {col[1]}')

# Find objective-related columns
print('\n=== OBJECTIVE-RELATED COLUMNS ===')
objective_keywords = [
    'xp',
    'assist',
    'dynamite',
    'objective',
    'revive',
    'multi',
    'double',
    'triple',
    'quad',
    'mega',
    'flag',
    'document',
]
for col in cols:
    col_name = col[1].lower()
    if any(keyword in col_name for keyword in objective_keywords):
        print(f'  - {col[1]}')

# Check some sample data
print('\n=== SAMPLE OBJECTIVE DATA (Top 3 by XP) ===')
query = """
SELECT player_name, xp, kill_assists, dynamites_planted, dynamites_defused,
       objectives_stolen, objectives_returned, times_revived,
       double_kills, triple_kills, quad_kills, multi_kills, mega_kills
FROM player_comprehensive_stats
ORDER BY xp DESC
LIMIT 3
"""
rows = c.execute(query).fetchall()
for row in rows:
    print(f'\n{row[0]}:')
    print(f'  XP: {row[1]}, Assists: {row[2]}')
    print(f'  Dynamites P/D: {row[3]}/{row[4]}')
    print(f'  Objectives S/R: {row[5]}/{row[6]}')
    print(f'  Times Revived: {row[7]}')
    print(f'  Multikills - 2x:{row[8]}, 3x:{row[9]}, 4x:{row[10]}, Multi:{row[11]}, Mega:{row[12]}')

conn.close()
