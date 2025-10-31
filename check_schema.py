import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print('=== Sessions Table Schema ===')
c.execute('PRAGMA table_info(sessions)')
for row in c.fetchall():
    print(f'  {row[1]:20} {row[2]}')

print('\n=== Sample Session (latest) ===')
c.execute('SELECT * FROM sessions ORDER BY id DESC LIMIT 1')
row = c.fetchone()
if row:
    print(f'  ID: {row[0]}')
    print(f'  Date: {row[1]}')
    print(f'  Map: {row[2]}')
    print(f'  Round: {row[3]}')
    print(f'  Time Limit: {row[4]}')
    print(f'  Actual Time: {row[5]}')

conn.close()
