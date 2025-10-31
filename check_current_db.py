#!/usr/bin/env python3
"""Check current database schema"""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Check player_comprehensive_stats columns
cursor.execute('PRAGMA table_info(player_comprehensive_stats)')
player_cols = cursor.fetchall()

# Check sessions columns
cursor.execute('PRAGMA table_info(sessions)')
session_cols = cursor.fetchall()

# Check all tables
cursor.execute('SELECT name FROM sqlite_master WHERE type="table" ORDER BY name')
tables = cursor.fetchall()

print(f"\n🔍 DATABASE SCHEMA CHECK")
print("=" * 80)
print(f"\n📊 Player stats columns: {len(player_cols)}")
if len(player_cols) == 54:
    print("   ✅ UNIFIED SCHEMA (53 cols + id = 54 total) - BOT COMPATIBLE")
elif len(player_cols) == 61:
    print("   ⚠️  EXTENDED SCHEMA (60 cols + id = 61 total) - MAY CAUSE ISSUES")
else:
    print(f"   ❌ UNEXPECTED SCHEMA ({len(player_cols)} cols)")

print(f"\n📅 Sessions columns: {len(session_cols)}")
print("   Columns:", ', '.join([col[1] for col in session_cols]))

print(f"\n📋 All tables ({len(tables)}):")
for table in tables:
    print(f"   - {table[0]}")

# Check if session_teams exists
if 'session_teams' in [t[0] for t in tables]:
    cursor.execute('SELECT COUNT(*) FROM session_teams')
    count = cursor.fetchone()[0]
    print(f"\n✅ session_teams table exists ({count} records)")
else:
    print("\n⚠️  session_teams table MISSING")

conn.close()
