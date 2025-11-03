import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cur = conn.cursor()

print('Tables in database:')
cur.execute('SELECT name FROM sqlite_master WHERE type="table"')
for row in cur.fetchall():
    print(f'  - {row[0]}')

print('\nweapon_comprehensive_stats schema:')
cur.execute('PRAGMA table_info(weapon_comprehensive_stats)')
cols = cur.fetchall()
print(f'Columns ({len(cols)}):')
for col in cols:
    null_constraint = 'NOT NULL' if col[3] else 'NULL'
    print(f'  {col[1]:25s} {col[2]:10s} {null_constraint}')

print(f'\nRow count: {cur.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats").fetchone()[0]}')

conn.close()
