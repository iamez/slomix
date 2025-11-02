#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

c.execute('''
    SELECT DISTINCT substr(session_start_date, 1, 10) as date
    FROM session_teams
    ORDER BY date
''')

print("Dates in session_teams:")
for row in c.fetchall():
    print(f"  {row[0]}")

conn.close()
