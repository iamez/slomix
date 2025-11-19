import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Check dates in sessions table
cursor.execute("SELECT DISTINCT SUBSTR(round_date, 1, 10) as date FROM rounds ORDER BY date")
dates = cursor.fetchall()

print("Dates in database sessions table:")
for row in dates:
    print(f"  {row[0]}")

# Check sample round_date format
cursor.execute("SELECT round_date, map_name, round_number FROM rounds LIMIT 5")
samples = cursor.fetchall()

print("\nSample sessions:")
for row in samples:
    print(f"  {row[0]} - {row[1]} - Round {row[2]}")

conn.close()
