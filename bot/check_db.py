import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('Tables in bot/etlegacy_production.db:')
for t in tables:
    print(f'  - {t[0]}')
    count = c.execute(f'SELECT COUNT(*) FROM {t[0]}').fetchone()[0]
    print(f'    Rows: {count}')

conn.close()
