"""Debug validator round matching"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Get Nov 2 rounds in DESC order (like validator does)
cursor.execute("""
    SELECT id, round_date, map_name, round_number
    FROM rounds
    WHERE round_date >= '2025-11-01'
    ORDER BY round_date DESC
    LIMIT 60
""")

print("Rounds in DESC order (how validator sees them):")
for i, (round_id, date, map_name, round_num) in enumerate(cursor.fetchall()[:40], 1):
    if '2025-11-02' in date and 'etl_adlernest' in map_name and round_num == 2:
        print(f"[{i}] *** Round {round_id}: {date} R{round_num} {map_name} *** <-- MIDNIGHT ROUND")
    else:
        print(f"[{i}] Round {round_id}: {date[:16]} R{round_num} {map_name}")

conn.close()
