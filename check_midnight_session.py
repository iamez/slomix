import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Check the midnight-spanning etl_adlernest session
cursor.execute("""
    SELECT id, session_date, map_name, round_number, map_id, winner_team
    FROM sessions 
    WHERE (session_date LIKE '2025-11-01-235%' OR session_date LIKE '2025-11-02-000%')
    AND map_name = 'etl_adlernest'
    ORDER BY id
""")

print("Midnight-spanning etl_adlernest session:")
for row in cursor.fetchall():
    print(f"  ID {row[0]}: {row[1]} - {row[2]} R{row[3]} - map_id={row[4]} - winner={row[5]}")

print("\n" + "="*70)
print("Most recent sessions in database:")
cursor.execute("""
    SELECT id, session_date, map_name, round_number, map_id
    FROM sessions 
    ORDER BY id DESC 
    LIMIT 10
""")

for row in cursor.fetchall():
    print(f"  ID {row[0]}: {row[1]} - {row[2]} R{row[3]} - map_id={row[4]}")

conn.close()
