import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

cursor.execute('SELECT sql FROM sqlite_master WHERE name = "weapon_comprehensive_stats"')
schema = cursor.fetchone()[0]
print(schema)

conn.close()
