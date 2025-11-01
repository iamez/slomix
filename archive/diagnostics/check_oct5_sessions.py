#!/usr/bin/env python3
"""Check October 5th sessions in database."""

import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Check sessions table
cursor.execute("""
    SELECT session_date, map_name, round_number
    FROM sessions
    WHERE session_date LIKE '2025-10-05%'
    ORDER BY session_date
""")
sessions = cursor.fetchall()

print(f"\n📊 October 5th sessions in database: {len(sessions)}")
for r in sessions:
    print(f"  {r[0]} | {r[1]:20s} | Round {r[2]}")

# Check processed_files table
cursor.execute("""
    SELECT filename
    FROM processed_files
    WHERE filename LIKE '2025-10-05%'
    ORDER BY filename
""")
files = cursor.fetchall()

print(f"\n📁 October 5th files in processed_files: {len(files)}")
for f in files:
    print(f"  {f[0]}")

conn.close()
