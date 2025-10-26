import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('\nTables:', [t[0] for t in tables])

# Check if player_stats exists
has_player_stats = any(t[0] == 'player_stats' for t in tables)
print(f'\nHas player_stats table: {has_player_stats}')

if has_player_stats:
    cols = c.execute('PRAGMA table_info(player_stats)').fetchall()
    print('\nplayer_stats columns:')
    for col in cols:
        print(f'  {col[1]}')

conn.close()
