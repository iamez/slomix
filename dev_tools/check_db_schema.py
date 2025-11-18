import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]

print("Tables in database:")
for table in tables:
    print(f"\n{table}:")
    cursor.execute(f"PRAGMA table_info({table})")
    for row in cursor.fetchall():
        print(f"  {row[1]} ({row[2]})")

conn.close()
