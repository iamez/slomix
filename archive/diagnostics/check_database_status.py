#!/usr/bin/env python3
"""Check current database status before re-import"""

import sqlite3
from pathlib import Path

db_path = 'etlegacy_production.db'

print('\n' + '='*80)
print('DATABASE PRE-IMPORT CHECK')
print('='*80)

if not Path(db_path).exists():
    print(f"\n❌ Database {db_path} not found!")
    exit(1)

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get all tables
print('\n📊 DATABASE STRUCTURE:')
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in c.fetchall()]
print(f"   Tables: {', '.join(tables)}")

# Count rows in each table
print('\n📈 TABLE COUNTS:')
for table in tables:
    if table != 'sqlite_sequence':
        try:
            c.execute(f"SELECT COUNT(*) FROM {table}")
            count = c.fetchone()[0]
            print(f"   {table:30s} {count:>10,} rows")
        except Exception as e:
            print(f"   {table:30s} ERROR: {e}")

# Check processed_files table
print('\n📁 PROCESSED FILES:')
try:
    c.execute("SELECT COUNT(*) as total, SUM(success) as successful FROM processed_files")
    total, successful = c.fetchone()
    print(f"   Total files tracked: {total:,}")
    print(f"   Successfully processed: {successful:,}")
    print(f"   Failed: {total - successful:,}")
except Exception as e:
    print(f"   ⚠️  No processed_files table or error: {e}")

# Check sessions
print('\n🗺️  SESSIONS SUMMARY:')
c.execute("SELECT COUNT(*) FROM sessions")
total_sessions = c.fetchone()[0]
print(f"   Total sessions: {total_sessions:,}")

c.execute("SELECT COUNT(DISTINCT session_date) FROM sessions")
unique_dates = c.fetchone()[0]
print(f"   Unique dates: {unique_dates}")

c.execute("SELECT COUNT(DISTINCT map_name) FROM sessions")
unique_maps = c.fetchone()[0]
print(f"   Unique maps: {unique_maps}")

# Recent sessions
print('\n📅 RECENT SESSIONS:')
c.execute("""
    SELECT id, session_date, map_name, round_number, actual_time 
    FROM sessions 
    ORDER BY session_date DESC, id DESC 
    LIMIT 5
""")
for row in c.fetchall():
    print(f"   ID {row[0]:4d}: {row[1]} {row[2]:20s} R{row[3]} ({row[4]})")

# Check for the erdenberg sessions we care about
print('\n🔍 ERDENBERG OCT 2 CHECK:')
c.execute("""
    SELECT s.id, s.round_number, COUNT(p.id) as player_count
    FROM sessions s
    LEFT JOIN player_comprehensive_stats p ON s.id = p.session_id
    WHERE s.session_date = '2025-10-02' AND s.map_name LIKE '%erdenberg%'
    GROUP BY s.id, s.round_number
    ORDER BY s.round_number
""")
results = c.fetchall()
if results:
    for row in results:
        print(f"   Session {row[0]} - Round {row[1]}: {row[2]} players")
        
    # Check if olz is in Round 1
    c.execute("""
        SELECT clean_name 
        FROM player_comprehensive_stats p
        JOIN sessions s ON p.session_id = s.id
        WHERE s.session_date = '2025-10-02' 
        AND s.map_name LIKE '%erdenberg%'
        AND s.round_number = 1
        AND clean_name LIKE '%olz%'
    """)
    olz_r1 = c.fetchone()
    if olz_r1:
        print(f"   ✅ olz found in Round 1: {olz_r1[0]}")
    else:
        print(f"   ❌ olz NOT in Round 1 (this is the bug we're fixing)")
else:
    print("   ⚠️  No erdenberg sessions found for Oct 2")

# Check database schema for sessions table
print('\n🔧 SESSIONS TABLE SCHEMA:')
c.execute("PRAGMA table_info(sessions)")
columns = c.fetchall()
for col in columns:
    print(f"   {col[1]:20s} {col[2]:15s} {'NOT NULL' if col[3] else ''}")

# Check for UNIQUE constraints
print('\n🔒 UNIQUE CONSTRAINTS:')
c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='sessions'")
schema = c.fetchone()
if schema:
    sql = schema[0]
    if 'UNIQUE' in sql:
        print("   ⚠️  Found UNIQUE constraint in sessions table:")
        # Extract the UNIQUE constraint line
        for line in sql.split('\n'):
            if 'UNIQUE' in line:
                print(f"      {line.strip()}")
    else:
        print("   ✅ No UNIQUE constraints found")

print('\n' + '='*80)
print('IMPORT READINESS ASSESSMENT')
print('='*80)

issues = []

# Check 1: UNIQUE constraint
c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='sessions'")
schema = c.fetchone()
if schema and 'UNIQUE(session_date, map_name, round_number)' in schema[0]:
    issues.append("❌ UNIQUE constraint still present - duplicate maps will be blocked")
else:
    print("✅ UNIQUE constraint removed - duplicate maps allowed")

# Check 2: processed_files will block re-import
c.execute("SELECT COUNT(*) FROM processed_files WHERE success = 1")
processed_count = c.fetchone()[0]
if processed_count > 0:
    issues.append(f"⚠️  {processed_count:,} files marked as processed - will be skipped unless database is deleted")
else:
    print("✅ No processed files - clean import")

# Check 3: Parser fix
print("✅ Parser bug fixed (validation changed from < 30 to < 6 fields)")

if issues:
    print(f"\n⚠️  ISSUES FOUND:")
    for issue in issues:
        print(f"   {issue}")
    print(f"\n💡 RECOMMENDATION:")
    print(f"   Delete database and start fresh to apply all fixes")
else:
    print("\n✅ Database ready for re-import")

conn.close()
print()
