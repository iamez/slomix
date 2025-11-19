import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Check specific sessions
cursor.execute("""
    SELECT round_date, map_name, round_number 
    FROM rounds 
    WHERE round_date LIKE '2025-10-27-230%'
    ORDER BY round_date
""")

print("Sessions on Oct 27 ~23:00:")
for row in cursor.fetchall():
    print(f"  {row[0]} | {row[1]} | Round {row[2]}")

# Check all Oct 27 sessions
cursor.execute("""
    SELECT round_date, map_name, round_number 
    FROM rounds 
    WHERE round_date LIKE '2025-10-27%'
    ORDER BY round_date
""")

print("\nAll Oct 27 sessions:")
for row in cursor.fetchall():
    print(f"  {row[0]} | {row[1]} | Round {row[2]}")

conn.close()
