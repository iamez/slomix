import sqlite3
import sys
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bot', 'etlegacy_production.db')
if not os.path.exists(DB_PATH):
    print('DB not found:', DB_PATH)
    sys.exit(2)

conn = sqlite3.connect(DB_PATH)
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='session_teams'")
exists = cur.fetchone() is not None
print('session_teams exists:', exists)
if exists:
    print('\nPRAGMA table_info(session_teams):')
    for row in conn.execute('PRAGMA table_info(session_teams)'):
        print(row)

    print('\nSample rows (limit 5):')
    for row in conn.execute('SELECT id, session_start_date, map_name, team_name, player_guids, player_names, created_at FROM session_teams LIMIT 5'):
        print(row)

conn.close()
