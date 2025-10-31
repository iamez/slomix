import sqlite3
conn = sqlite3.connect('etlegacy_production.db')
print('Sessions table schema:')
for row in conn.execute('PRAGMA table_info(sessions)').fetchall():
    print(f'  {row[1]} ({row[2]})')

print('\nPlayer stats table schema (first 15):')
for row in conn.execute('PRAGMA table_info(player_comprehensive_stats)').fetchall()[:15]:
    print(f'  {row[1]} ({row[2]})')
conn.close()
