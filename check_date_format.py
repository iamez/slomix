#!/usr/bin/env python3
"""Check session_date format in player_comprehensive_stats."""

import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Get actual session_date values
cursor.execute("""
    SELECT DISTINCT session_date
    FROM player_comprehensive_stats
    WHERE session_date LIKE '2025-10-05%'
    ORDER BY session_date
""")
player_dates = [r[0] for r in cursor.fetchall()]

# Get session_date values from sessions table
cursor.execute("""
    SELECT DISTINCT session_date
    FROM sessions
    WHERE session_date LIKE '2025-10-05%'
    ORDER BY session_date
""")
session_dates = [r[0] for r in cursor.fetchall()]

print("\n" + "="*70)
print("📅 SESSION_DATE FORMAT COMPARISON")
print("="*70)

print(f"\n🔍 In player_comprehensive_stats ({len(player_dates)} unique):")
for d in player_dates:
    print(f"  {d}")

print(f"\n🔍 In sessions table ({len(session_dates)} unique):")
for d in session_dates:
    print(f"  {d}")

print("\n" + "="*70)
print("❌ PROBLEM IDENTIFIED:")
print("="*70)
print("player_comprehensive_stats uses: '2025-10-05' (DATE ONLY)")
print("sessions table uses: '2025-10-05-200001' (DATE + TIMESTAMP)")
print("\nThey don't match! This is why data looks aggregated.")

conn.close()
