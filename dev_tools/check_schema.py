import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Get rounds table schema
cursor.execute("PRAGMA table_info(sessions)")
print("Sessions table columns:")
for col in cursor.fetchall():
    print(f"  {col[1]} ({col[2]})")

print()

# Get player_comprehensive_stats schema
cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
print("player_comprehensive_stats columns:")
for col in cursor.fetchall():
    print(f"  {col[1]} ({col[2]})")

conn.close()
