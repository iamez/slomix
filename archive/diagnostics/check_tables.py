import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables in database:")
for table in tables:
    print(f"  - {table[0]}")
conn.close()
