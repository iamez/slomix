import os
import sqlite3

# Check both databases
dbs = [('Main DB', 'etlegacy_production.db'), ('Bot DB', 'bot/etlegacy_production.db')]

for name, path in dbs:
    if os.path.exists(path):
        print(f'\n{name} ({path}):')
        conn = sqlite3.connect(path)
        c = conn.cursor()
        tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        for t in tables:
            table_name = t[0]
            if table_name != 'sqlite_sequence':
                count = c.execute(f'SELECT COUNT(*) FROM {table_name}').fetchone()[0]
                print(f'  - {table_name}: {count} rows')
        conn.close()
    else:
        print(f'{name}: NOT FOUND')
