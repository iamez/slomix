#!/usr/bin/env python3
"""Check session times for 2025-10-30"""

import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

c.execute("""
    SELECT map_name, round_number, time_limit, actual_time, winner_team
    FROM rounds
    WHERE round_date LIKE '2025-10-30%'
    ORDER BY id
""")

print(f"\n{'Map':<20} {'Round':<8} {'Limit':<10} {'Actual':<10} {'Winner'}")
print("=" * 65)

for map_name, rnd, limit, actual, winner in c.fetchall():
    print(f"{map_name:<20} R{rnd:<7} {limit:<10} {actual:<10} Team {winner}")

conn.close()
