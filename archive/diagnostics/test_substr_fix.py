#!/usr/bin/env python3
"""Test session_date SUBSTR fix"""

import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

# Test SUBSTR approach
print("=== Testing SUBSTR(session_date, 1, 10) ===")
c.execute('''
    SELECT DISTINCT SUBSTR(session_date, 1, 10) as date
    FROM sessions
    ORDER BY date DESC
    LIMIT 5
''')
dates = c.fetchall()
print("Recent dates (first 10 chars):")
for d in dates:
    print(f"  {d[0]}")

print("\n=== Count Oct 2 sessions with SUBSTR ===")
c.execute('''
    SELECT COUNT(*)
    FROM sessions
    WHERE SUBSTR(session_date, 1, 10) = "2025-10-02"
''')
print(f"Oct 2 sessions: {c.fetchone()[0]}")

print("\n=== Bot query FIXED ===")
c.execute('''
    SELECT DISTINCT SUBSTR(session_date, 1, 10) as date
    FROM sessions
    ORDER BY date DESC
    LIMIT 1
''')
latest_date = c.fetchone()[0]
print(f"Latest date: {latest_date}")

# Get all session IDs for this date
c.execute('''
    SELECT id, map_name, round_number
    FROM sessions
    WHERE SUBSTR(session_date, 1, 10) = ?
    ORDER BY id ASC
''', (latest_date,))
sessions = c.fetchall()
print(f"\nAll sessions for {latest_date}: {len(sessions)} sessions")
for s in sessions[:5]:
    print(f"  ID {s[0]}: {s[1]} R{s[2]}")
print(f"  ... and {len(sessions) - 5} more")

# Count maps
c.execute('''
    SELECT DISTINCT map_name
    FROM sessions
    WHERE SUBSTR(session_date, 1, 10) = ?
''', (latest_date,))
maps = c.fetchall()
print(f"\nUnique maps: {len(maps)}")
for m in maps:
    print(f"  {m[0]}")

conn.close()
