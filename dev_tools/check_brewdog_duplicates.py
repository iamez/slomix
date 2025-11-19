#!/usr/bin/env python3
"""
Check if there are duplicate/multiple sessions for et_brewdog on 2025-09-09
"""
import sqlite3

db_path = "bot/etlegacy_production.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 100)
print("ALL et_brewdog SESSIONS ON 2025-09-09")
print("=" * 100)

cursor.execute("""
    SELECT id, round_date, map_name, round_number, actual_time
    FROM rounds
    WHERE round_date = '2025-09-09' AND map_name = 'et_brewdog'
    ORDER BY round_number, id
""")

sessions = cursor.fetchall()
print(f"\nFound {len(sessions)} sessions:")

for sess_id, date, map_name, round_num, actual_time in sessions:
    print(f"\n🎮 Session {sess_id}:")
    print(f"   Date: {date}")
    print(f"   Map: {map_name}")
    print(f"   Round: {round_num}")
    print(f"   Actual Time: {actual_time}")
    
    # Get player count and total time
    cursor.execute("""
        SELECT COUNT(*), SUM(time_played_seconds), MAX(time_played_seconds)
        FROM player_comprehensive_stats
        WHERE round_id = ?
    """, (sess_id,))
    
    count, total_time, max_time = cursor.fetchone()
    print(f"   Players: {count}")
    print(f"   Total time (all players): {total_time}s")
    print(f"   Max individual time: {max_time}s")

print("\n" + "=" * 100)
print("FILES FOR THIS DATE/MAP")
print("=" * 100)

from pathlib import Path
files = sorted(Path("local_stats").glob("2025-09-09-*-et_brewdog-*.txt"))
print(f"\nFound {len(files)} files:")
for f in files:
    print(f"   - {f.name}")

conn.close()
print("\n" + "=" * 100)
