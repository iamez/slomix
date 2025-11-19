"""Check for duplicate Nov 2 midnight rounds"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Check all etl_adlernest rounds on Nov 2
cursor.execute("""
    SELECT id, round_date, round_time, map_name, round_number, match_id
    FROM rounds
    WHERE round_date LIKE '2025-11-02%' AND map_name = 'etl_adlernest'
    ORDER BY round_time
""")

print("All Nov 2 etl_adlernest rounds:")
for row in cursor.fetchall():
    print(f"  ID {row[0]}: {row[1]} {row[2]} R{row[3]} {row[4]} | match_id: {row[5]}")

print("\nChecking for duplicates with 000624 time...")
cursor.execute("""
    SELECT id, round_date, round_time, map_name, round_number, match_id, 
           COUNT(*) OVER (PARTITION BY round_date, round_time, map_name, round_number) as dup_count
    FROM rounds
    WHERE round_date LIKE '2025-11-02%' AND round_time = '000624'
""")

duplicates = cursor.fetchall()
if duplicates:
    print(f"Found {len(duplicates)} rounds with 000624 time:")
    for row in duplicates:
        print(f"  ID {row[0]}: R{row[4]} {row[3]} | match_id: {row[5]} | dup_count: {row[6]}")
else:
    print("No duplicates found")

conn.close()
