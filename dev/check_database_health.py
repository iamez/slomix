#!/usr/bin/env python3
"""
Check and fix database schema issues
"""

import sqlite3
import sys

def check_schema():
    """Check current database schema"""
    print("\n=== CHECKING DATABASE SCHEMA ===\n")
    
    conn = sqlite3.connect('etlegacy_production.db')
    cur = conn.cursor()
    
    # Check sessions table
    print("Sessions table columns:")
    columns = cur.execute('PRAGMA table_info(sessions)').fetchall()
    col_names = [row[1] for row in columns]
    for row in columns:
        print(f"  ✓ {row[1]} ({row[2]})")
    
    # Check for missing columns
    required = ['id', 'session_date', 'map_name', 'round_number', 
                'time_limit', 'actual_time', 'created_at']
    missing = [col for col in required if col not in col_names]
    
    if missing:
        print(f"\n❌ Missing columns: {missing}")
        return False
    else:
        print(f"\n✅ All required columns present")
        return True
    
    conn.close()

def check_data_integrity():
    """Check data quality"""
    print("\n=== CHECKING DATA INTEGRITY ===\n")
    
    conn = sqlite3.connect('etlegacy_production.db')
    cur = conn.cursor()
    
    # Count records
    sessions = cur.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    players = cur.execute("SELECT COUNT(*) FROM player_comprehensive_stats").fetchone()[0]
    weapons = cur.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats").fetchone()[0]
    
    print(f"Sessions: {sessions:,}")
    print(f"Players: {players:,}")
    print(f"Weapons: {weapons:,}")
    
    # Check for orphaned records
    orphaned_players = cur.execute("""
        SELECT COUNT(*) FROM player_comprehensive_stats 
        WHERE session_id NOT IN (SELECT id FROM sessions)
    """).fetchone()[0]
    
    orphaned_weapons = cur.execute("""
        SELECT COUNT(*) FROM weapon_comprehensive_stats 
        WHERE session_id NOT IN (SELECT id FROM sessions)
    """).fetchone()[0]
    
    if orphaned_players > 0:
        print(f"❌ Orphaned player records: {orphaned_players}")
    else:
        print(f"✅ No orphaned player records")
    
    if orphaned_weapons > 0:
        print(f"❌ Orphaned weapon records: {orphaned_weapons}")
    else:
        print(f"✅ No orphaned weapon records")
    
    # Check Round 1 vs Round 2
    round1 = cur.execute("SELECT COUNT(*) FROM sessions WHERE round_number = 1").fetchone()[0]
    round2 = cur.execute("SELECT COUNT(*) FROM sessions WHERE round_number = 2").fetchone()[0]
    
    print(f"\nRound 1 sessions: {round1:,}")
    print(f"Round 2 sessions: {round2:,}")
    print(f"Ratio: {round2/round1:.2f} (should be ~1.0)")
    
    # Check for 0:00 times
    zero_times = cur.execute("""
        SELECT COUNT(*) FROM sessions 
        WHERE actual_time = '0:00'
    """).fetchone()[0]
    
    print(f"\nSessions with 0:00 time: {zero_times:,}")
    
    conn.close()
    
    return orphaned_players == 0 and orphaned_weapons == 0

if __name__ == "__main__":
    schema_ok = check_schema()
    data_ok = check_data_integrity()
    
    if schema_ok and data_ok:
        print("\n✅ Database is healthy!")
        sys.exit(0)
    else:
        print("\n⚠️ Database has issues that need attention")
        sys.exit(1)
