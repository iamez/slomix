#!/usr/bin/env python3
"""Quick October 5th data verification script."""

import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Check October 5th sessions
print("\n" + "="*70)
print("📅 OCTOBER 5TH SESSIONS")
print("="*70)

cursor.execute("""
    SELECT session_date, map_name, round_number, COUNT(player_guid) as players
    FROM player_comprehensive_stats
    WHERE session_date LIKE '2025-10-05%'
    GROUP BY session_date
    ORDER BY session_date
""")
sessions = cursor.fetchall()

for row in sessions:
    print(f"{row[0]} | {row[1]:20s} | R{row[2]} | {row[3]} players")

print(f"\n✅ Total: {len(sessions)} sessions, {sum([r[3] for r in sessions])} player records")

# Check October 5th player times
print("\n" + "="*70)
print("⏱️  OCTOBER 5TH PLAYER TIMES")
print("="*70)

cursor.execute("""
    SELECT player_name, SUM(time_played_seconds) as total, COUNT(session_id) as sessions
    FROM player_comprehensive_stats
    WHERE session_date LIKE '2025-10-05%'
    GROUP BY player_guid
    ORDER BY total DESC
""")
players = cursor.fetchall()

for row in players:
    mins = int(row[1] // 60)
    secs = int(row[1] % 60)
    print(f"{row[0]:20s} | {mins:3d}:{secs:02d} | {row[2]} sessions")

if players:
    avg = sum([r[1] for r in players]) / len(players)
    print(f"\n✅ Average: {int(avg//60)}:{int(avg%60):02d} per player")
    print(f"🎯 Expected: 20+ minutes per player (not 0 or 14 min total)")
else:
    print("\n❌ NO PLAYERS FOUND!")

conn.close()
