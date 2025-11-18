#!/usr/bin/env python3
"""Check for duplicate map_id assignments."""

import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

print("\nChecking Oct 30 map_id assignments:\n")

c.execute("""
    SELECT map_id, COUNT(*) as cnt, map_name
    FROM rounds 
    WHERE round_date LIKE '2025-10-30%'
    GROUP BY map_id
    ORDER BY map_id
""")

print(f"{'Map ID':<10} {'Count':<10} {'Map Name'}")
print("-"*50)

for row in c.fetchall():
    map_id, cnt, map_name = row
    status = "✅ OK" if cnt == 2 else "⚠️ PROBLEM"
    print(f"{map_id:<10} {cnt:<10} {map_name:<30} {status}")

print("\n\nDetailed view of problematic map_ids:\n")

c.execute("""
    SELECT map_id, round_date, map_name, round_number, 
           completion_time, time_to_beat
    FROM rounds 
    WHERE round_date LIKE '2025-10-30%'
    AND map_id IN (
        SELECT map_id FROM rounds 
        WHERE round_date LIKE '2025-10-30%'
        GROUP BY map_id HAVING COUNT(*) > 2
    )
    ORDER BY map_id, round_date
""")

current_id = None
for row in c.fetchall():
    map_id, date, name, rnd, done, beat = row
    if map_id != current_id:
        print(f"\n--- Map ID {map_id} ({name}) ---")
        current_id = map_id
    print(f"  {date} R{rnd}: done={done}, beat={beat}")

conn.close()
