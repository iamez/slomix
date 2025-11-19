#!/usr/bin/env python3
"""Check Nov 1-2 sessions to understand the last_round issue"""
import sqlite3

db_path = "bot/etlegacy_production.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 100)
print("SESSIONS ON NOV 1-2, 2025")
print("=" * 100)

cursor.execute("""
    SELECT id, round_date, round_time, map_name, round_number, match_id
    FROM rounds
    WHERE round_date >= '2025-11-01'
    ORDER BY round_date, round_time, id
""")

rows = cursor.fetchall()

print(f"\nFound {len(rows)} sessions:")
print()

for row in rows:
    sess_id, date, time, map_name, round_num, match_id = row
    print(f"ID={sess_id:4d} | {date} {time} | {map_name:20s} | R{round_num} | match_id={match_id}")

# Check what the LAST session actually is
print("\n" + "=" * 100)
print("WHAT IS THE ACTUAL LAST SESSION?")
print("=" * 100)

cursor.execute("""
    SELECT id, round_date, round_time, map_name, round_number
    FROM rounds
    ORDER BY id DESC
    LIMIT 5
""")

last_sessions = cursor.fetchall()
print("\nLast 5 sessions by ID (most recent first):")
for row in last_sessions:
    sess_id, date, time, map_name, round_num = row
    print(f"ID={sess_id:4d} | {date} {time} | {map_name:20s} | R{round_num}")

conn.close()

print("\n" + "=" * 100)
