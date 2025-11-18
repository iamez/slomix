import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("\n=== SESSIONS TABLE SCHEMA ===")
cursor.execute('PRAGMA table_info(sessions)')
cols = cursor.fetchall()
for col in cols:
    print(f"  {col[1]:20} {col[2]:15} NotNull:{col[3]} Default:{col[4]} PK:{col[5]}")

print("\n=== SAMPLE SESSIONS DATA ===")
cursor.execute('SELECT id, round_date, round_time, match_id, map_name, round_number FROM rounds LIMIT 10')
rows = cursor.fetchall()
for row in rows:
    print(f"  ID:{row[0]} Date:{row[1]} Time:{row[2]} Match:{row[3][:30]}... Map:{row[4]} R{row[5]}")

print("\n=== TOTAL SESSIONS ===")
cursor.execute('SELECT COUNT(*) FROM rounds')
total = cursor.fetchone()[0]
print(f"  Total: {total} sessions")

print("\n=== DISTINCT DATES ===")
cursor.execute('SELECT DISTINCT round_date FROM rounds ORDER BY round_date')
dates = cursor.fetchall()
for date in dates:
    cursor.execute('SELECT COUNT(*) FROM rounds WHERE round_date = ?', (date[0],))
    count = cursor.fetchone()[0]
    print(f"  {date[0]}: {count} sessions")

conn.close()
