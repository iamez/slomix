#!/usr/bin/env python3
"""
Check database integrity and show October 2, 2025 data
"""
import sqlite3
from pathlib import Path

def check_database():
    db_path = Path(__file__).parent / "bot" / "etlegacy_production.db"
    
    print("="*70)
    print("DATABASE INTEGRITY CHECK")
    print("="*70)
    print(f"Database: {db_path}")
    print()
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Overall stats
    total_sessions = c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
    total_players = c.execute('SELECT COUNT(*) FROM player_comprehensive_stats').fetchone()[0]
    total_weapons = c.execute('SELECT COUNT(*) FROM weapon_comprehensive_stats').fetchone()[0]
    
    print(f"Total Sessions: {total_sessions:,}")
    print(f"Total Player Records: {total_players:,}")
    print(f"Total Weapon Records: {total_weapons:,}")
    
    # Check for date range
    date_range = c.execute(
        'SELECT MIN(session_date), MAX(session_date) FROM sessions'
    ).fetchone()
    print(f"\nDate Range: {date_range[0]} to {date_range[1]}")
    
    # Count sessions by date (recent dates)
    print("\n--- Recent Sessions by Date ---")
    recent = c.execute('''
        SELECT session_date, COUNT(*) as session_count
        FROM sessions
        WHERE session_date >= '2025-10-01'
        ORDER BY session_date DESC
        LIMIT 10
    ''').fetchall()
    
    for date, count in recent:
        print(f"  {date}: {count} sessions")
    
    print("\n" + "="*70)
    print("OCTOBER 2, 2025 - DETAILED DATA")
    print("="*70)
    
    # Get October 2 sessions
    oct2_sessions = c.execute('''
        SELECT id, session_date, map_name, round_number, 
               time_limit, actual_time
        FROM sessions
        WHERE session_date = '2025-10-02'
        ORDER BY id
    ''').fetchall()
    
    if not oct2_sessions:
        print("⚠️  NO SESSIONS FOUND for October 2, 2025")
        print("\nChecking if any sessions exist around that date...")
        nearby = c.execute('''
            SELECT session_date, COUNT(*)
            FROM sessions
            WHERE session_date BETWEEN '2025-09-30' AND '2025-10-05'
            GROUP BY session_date
            ORDER BY session_date
        ''').fetchall()
        print("\nNearby dates:")
        for date, count in nearby:
            print(f"  {date}: {count} sessions")
    else:
        print(f"\nFound {len(oct2_sessions)} sessions on 2025-10-02:\n")
        
        for session in oct2_sessions:
            session_id, date, map_name, rounds, time_limit, actual = session
            
            # Get player count for this session
            player_count = c.execute('''
                SELECT COUNT(DISTINCT player_name)
                FROM player_comprehensive_stats
                WHERE session_id = ?
            ''', (session_id,)).fetchone()[0]
            
            # Get total kills for verification
            total_kills = c.execute('''
                SELECT SUM(kills)
                FROM player_comprehensive_stats
                WHERE session_id = ?
            ''', (session_id,)).fetchone()[0] or 0
            
            print(f"Session {session_id}:")
            print(f"  Map: {map_name}")
            print(f"  Round: {rounds}")
            print(f"  Time Limit: {time_limit} | Actual: {actual}")
            print(f"  Players: {player_count}")
            print(f"  Total Kills: {total_kills}")
            print()
    
    # Check for any data integrity issues
    print("="*70)
    print("DATA INTEGRITY CHECKS")
    print("="*70)
    
    # Check for sessions without players
    orphan_sessions = c.execute('''
        SELECT COUNT(*)
        FROM sessions s
        LEFT JOIN player_comprehensive_stats p ON s.id = p.session_id
        WHERE p.id IS NULL
    ''').fetchone()[0]
    
    # Check for players without sessions
    orphan_players = c.execute('''
        SELECT COUNT(*)
        FROM player_comprehensive_stats p
        LEFT JOIN sessions s ON p.session_id = s.id
        WHERE s.id IS NULL
    ''').fetchone()[0]
    
    # Check for NULL critical fields
    null_checks = [
        ('Sessions with NULL date',
         'SELECT COUNT(*) FROM sessions WHERE session_date IS NULL'),
        ('Sessions with NULL map_name',
         'SELECT COUNT(*) FROM sessions WHERE map_name IS NULL'),
        ('Players with NULL session_id',
         'SELECT COUNT(*) FROM player_comprehensive_stats '
         'WHERE session_id IS NULL'),
        ('Players with NULL player_name',
         'SELECT COUNT(*) FROM player_comprehensive_stats '
         'WHERE player_name IS NULL'),
    ]
    
    issues_found = 0
    
    if orphan_sessions > 0:
        print(f"⚠️  Sessions without players: {orphan_sessions}")
        issues_found += 1
    else:
        print(f"✅ No orphan sessions (all sessions have players)")
    
    if orphan_players > 0:
        print(f"⚠️  Players without sessions: {orphan_players}")
        issues_found += 1
    else:
        print(f"✅ No orphan players (all players linked to sessions)")
    
    for check_name, query in null_checks:
        count = c.execute(query).fetchone()[0]
        if count > 0:
            print(f"⚠️  {check_name}: {count}")
            issues_found += 1
        else:
            print(f"✅ {check_name}: 0")
    
    print()
    if issues_found == 0:
        print("✅ DATABASE IS HEALTHY - No integrity issues found!")
    else:
        print(f"⚠️  Found {issues_found} potential issues (see above)")
    
    conn.close()
    print("\n" + "="*70)

if __name__ == "__main__":
    check_database()
