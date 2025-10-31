#!/usr/bin/env python3
"""
Check comprehensive database structure and players for Discord linking
"""
import sqlite3
import os

def check_comprehensive_database():
    db_path = "dev/etlegacy_comprehensive.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=== COMPREHENSIVE DATABASE ANALYSIS ===")
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"\n📊 Tables found: {[t[0] for t in tables]}")
    
    # Check players
    if any("player_comprehensive_stats" in str(t) for t in tables):
        print("\n🎮 PLAYERS IN DATABASE:")
        cursor.execute('''
            SELECT DISTINCT player_guid, clean_name, COUNT(*) as rounds
            FROM player_comprehensive_stats 
            GROUP BY player_guid, clean_name
            ORDER BY rounds DESC
        ''')
        
        players = cursor.fetchall()
        for guid, name, rounds in players:
            print(f"  {name:<15} {guid:<12} ({rounds} rounds)")
        
        print(f"\n📈 Total unique players: {len(players)}")
    
    # Check current links
    if any("player_links" in str(t) for t in tables):
        print("\n🔗 CURRENT PLAYER LINKS:")
        cursor.execute("SELECT * FROM player_links")
        links = cursor.fetchall()
        
        if links:
            for link in links:
                print(f"  {link}")
        else:
            print("  No links found")
    
    # Check sessions
    if any("sessions" in str(t) for t in tables):
        print("\n📅 SESSIONS:")
        cursor.execute("SELECT COUNT(*) FROM sessions")
        session_count = cursor.fetchone()[0]
        print(f"  Total sessions: {session_count}")
    
    conn.close()

if __name__ == "__main__":
    check_comprehensive_database()