import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Get all table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]

print("All tables:")
for table in tables:
    print(f"  - {table}")

# Check rounds table structure
if 'rounds' in tables:
    cursor.execute('PRAGMA table_info(rounds)')
    print("\nRounds table columns:")
    for col in cursor.fetchall():
        print(f"  {col[1]} ({col[2]})")

conn.close()
