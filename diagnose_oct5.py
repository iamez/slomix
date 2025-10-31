#!/usr/bin/env python3
"""Diagnose October 5th player stats issue."""

import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Check player_comprehensive_stats for October 5th
print("\n" + "="*70)
print("🔍 OCTOBER 5TH PLAYER STATS BREAKDOWN")
print("="*70)

cursor.execute("""
    SELECT session_date, map_name, round_number, COUNT(*) as player_records
    FROM player_comprehensive_stats
    WHERE session_date LIKE '2025-10-05%'
    GROUP BY session_date, map_name, round_number
    ORDER BY session_date
""")
results = cursor.fetchall()

print(f"\nPlayer records per session:")
for row in results:
    print(f"  {row[0]} | {row[1]:20s} | R{row[2]} | {row[3]} player records")

print(f"\n✅ Total sessions with player data: {len(results)}")
print(f"✅ Total player records: {sum([r[3] for r in results])}")

# Check sessions table for October 5th
print("\n" + "="*70)
print("🔍 OCTOBER 5TH SESSIONS (from sessions table)")
print("="*70)

cursor.execute("""
    SELECT session_date, map_name, round_number
    FROM sessions
    WHERE session_date LIKE '2025-10-05%'
    ORDER BY session_date
""")
sessions = cursor.fetchall()

print(f"\nSessions in sessions table: {len(sessions)}")
for s in sessions:
    print(f"  {s[0]} | {s[1]:20s} | R{s[2]}")

# Compare
print("\n" + "="*70)
print("📊 COMPARISON")
print("="*70)
print(f"Sessions in sessions table: {len(sessions)}")
print(f"Sessions with player data:  {len(results)}")
print(f"\n❌ MISSING: {len(sessions) - len(results)} sessions have NO player stats!")

conn.close()
