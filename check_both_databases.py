#!/usr/bin/env python3
"""Check both databases"""
import sqlite3
import os

dbs = ['etlegacy_production.db', 'bot/etlegacy_production.db']

for db_path in dbs:
    print(f"\n{'='*70}")
    print(f"DATABASE: {db_path}")
    print('='*70)
    
    if not os.path.exists(db_path):
        print("  ❌ Does not exist")
        continue
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    sessions = c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
    players = c.execute('SELECT COUNT(*) FROM player_comprehensive_stats').fetchone()[0]
    unique_players = c.execute('SELECT COUNT(DISTINCT player_name) FROM player_comprehensive_stats').fetchone()[0]
    
    print(f"  Sessions: {sessions}")
    print(f"  Player records: {players}")
    print(f"  Unique players: {unique_players}")
    
    # Check Session 1
    print("\n  Session 1 details:")
    s1 = c.execute('SELECT session_date, map_name, round_number FROM sessions WHERE id = 1').fetchone()
    if s1:
        print(f"    {s1[0]} {s1[1]} R{s1[2]}")
        s1_players = c.execute('SELECT COUNT(DISTINCT player_name) FROM player_comprehensive_stats WHERE session_id = 1').fetchone()[0]
        print(f"    Unique players: {s1_players}")
    else:
        print("    No Session 1")
    
    # Check Session 72
    print("\n  Session 72 details:")
    s72 = c.execute('SELECT session_date, map_name, round_number FROM sessions WHERE id = 72').fetchone()
    if s72:
        print(f"    {s72[0]} {s72[1]} R{s72[2]}")
        s72_players = c.execute('SELECT COUNT(DISTINCT player_name) FROM player_comprehensive_stats WHERE session_id = 72').fetchone()[0]
        print(f"    Unique players: {s72_players}")
    else:
        print("    No Session 72")
    
    conn.close()
