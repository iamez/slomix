import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cols = conn.execute('PRAGMA table_info(player_aliases)').fetchall()

print('\n📋 player_aliases table structure:')
for col in cols:
    print(f'  - {col[1]} ({col[2]})')

conn.close()
