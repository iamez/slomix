#!/usr/bin/env python3
"""Check R2 backfill data - see what actually got populated."""

import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

print("\nR2 ROUNDS - Oct 30th data:\n")
print(f"{'Date':<20} {'Map':<20} {'Orig':<10} {'Beat':<10} {'Done':<10}")
print("-"*70)

c.execute("""
    SELECT session_date, map_name, round_number, 
           original_time_limit, time_to_beat, completion_time, map_id
    FROM sessions 
    WHERE round_number = 2 
    AND session_date LIKE '2025-10-30%'
    ORDER BY session_date
""")

for row in c.fetchall():
    date, map_name, rnd, orig, beat, done, map_id = row
    print(f"{date:<20} {map_name:<20} {orig or 'NULL':<10} {beat or 'NULL':<10} {done or 'NULL':<10} (map_id={map_id})")

print("\n\nR1 ROUNDS for comparison:\n")
print(f"{'Date':<20} {'Map':<20} {'Orig':<10} {'Beat':<10} {'Done':<10}")
print("-"*70)

c.execute("""
    SELECT session_date, map_name, round_number, 
           original_time_limit, time_to_beat, completion_time, map_id
    FROM sessions 
    WHERE round_number = 1 
    AND session_date LIKE '2025-10-30%'
    ORDER BY session_date
""")

for row in c.fetchall():
    date, map_name, rnd, orig, beat, done, map_id = row
    print(f"{date:<20} {map_name:<20} {orig or 'NULL':<10} {beat or 'NULL':<10} {done or 'NULL':<10} (map_id={map_id})")

conn.close()
