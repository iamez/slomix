#!/usr/bin/env python3
"""Check fresh database status"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

print("="*70)
print("FRESH DATABASE STATUS")
print("="*70)

sessions = c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
players = c.execute('SELECT COUNT(*) FROM player_comprehensive_stats').fetchone()[0]
weapons = c.execute('SELECT COUNT(*) FROM weapon_comprehensive_stats').fetchone()[0]
processed = c.execute('SELECT COUNT(*) FROM processed_files').fetchone()[0]

print(f"\nTotals:")
print(f"  Sessions: {sessions}")
print(f"  Player records: {players}")
print(f"  Weapon records: {weapons}")
print(f"  Processed files: {processed}")

if sessions > 0:
    print(f"\nFirst session details:")
    s1 = c.execute('''
        SELECT id, session_date, map_name, round_number
        FROM sessions
        ORDER BY id
        LIMIT 1
    ''').fetchone()
    
    if s1:
        sess_id, date, map_name, round_num = s1
        print(f"  Session {sess_id}: {date} {map_name} R{round_num}")
        
        # Get players
        players_s1 = c.execute('''
            SELECT id, player_name, team, kills, deaths
            FROM player_comprehensive_stats
            WHERE session_id = ?
            ORDER BY id
        ''', (sess_id,)).fetchall()
        
        print(f"  Players ({len(players_s1)}):")
        for pid, pname, team, kills, deaths in players_s1:
            team_name = "Axis" if team == 1 else "Allies" if team == 2 else "Spec"
            print(f"    ID {pid}: {pname} | {team_name} | K={kills} D={deaths}")
        
        # Check for unique players
        unique = set(p[1] for p in players_s1)
        print(f"\n  Unique players: {len(unique)}")
        if len(unique) < len(players_s1):
            print(f"  ⚠️  WARNING: Duplicates detected!")

conn.close()
