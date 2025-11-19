#!/usr/bin/env python3
"""Show session order by ID"""

import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

c.execute("""
    SELECT id, map_name, round_number
    FROM rounds
    WHERE round_date LIKE '2025-10-30%'
    ORDER BY id
""")

for sess_id, map_name, rnd in c.fetchall():
    print(f"ID {sess_id:4d}: {map_name:<20} R{rnd}")

conn.close()
