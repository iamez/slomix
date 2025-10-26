#!/usr/bin/env python3
"""
Debug team detection issues in database
Check if players are being assigned to proper teams
"""
import sqlite3
from pathlib import Path

def check_team_detection():
    db_path = Path(__file__).parent / "bot" / "etlegacy_production.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    print("="*70)
    print("TEAM DETECTION DEBUG - October 2, 2025 Sessions")
    print("="*70)
    
    # Get a few October 2 sessions to analyze
    sessions = c.execute('''
        SELECT id, session_date, map_name, round_number
        FROM sessions
        WHERE session_date = '2025-10-02'
        ORDER BY id
        LIMIT 5
    ''').fetchall()
    
    for session_id, date, map_name, round_num in sessions:
        print(f"\n{'='*70}")
        print(f"Session {session_id}: {map_name} (Round {round_num})")
        print(f"{'='*70}")
        
        # Get all players for this session
        players = c.execute('''
            SELECT player_name, team, kills, deaths, damage_given, 
                   time_axis, time_allies
            FROM player_comprehensive_stats
            WHERE session_id = ?
            ORDER BY kills DESC
        ''', (session_id,)).fetchall()
        
        if not players:
            print("  ⚠️  NO PLAYERS FOUND for this session!")
            continue
        
        # Count players by team
        team_counts = {}
        for p in players:
            team = p[1] if p[1] else 'NULL'
            team_counts[team] = team_counts.get(team, 0) + 1
        
        print(f"\nTeam Distribution:")
        for team, count in team_counts.items():
            print(f"  {team}: {count} players")
        
        print(f"\nPlayer Details:")
        print(f"  {'Player':<20} {'Team':<12} {'K':<4} {'D':<4} {'Dmg':<6} "
              f"{'Axis%':<7} {'Allies%':<7}")
        print(f"  {'-'*20} {'-'*12} {'-'*4} {'-'*4} {'-'*6} "
              f"{'-'*7} {'-'*7}")
        
        for player in players:
            name = player[0][:20]
            team = player[1] if player[1] else 'NULL'
            kills = player[2]
            deaths = player[3]
            damage = player[4]
            time_axis = player[5] if player[5] else 0
            time_allies = player[6] if player[6] else 0
            
            print(f"  {name:<20} {team:<12} {kills:<4} {deaths:<4} "
                  f"{damage:<6} {time_axis:<7.1f} {time_allies:<7.1f}")
    
    # Now check the overall problem
    print(f"\n{'='*70}")
    print("OVERALL TEAM DETECTION ANALYSIS")
    print(f"{'='*70}")
    
    # Sessions with no players
    no_players = c.execute('''
        SELECT COUNT(*)
        FROM sessions s
        LEFT JOIN player_comprehensive_stats p ON s.id = p.session_id
        WHERE p.id IS NULL
    ''').fetchone()[0]
    
    # Sessions with players but NULL teams
    null_teams = c.execute('''
        SELECT s.id, s.session_date, s.map_name, COUNT(p.id) as player_count
        FROM sessions s
        JOIN player_comprehensive_stats p ON s.id = p.session_id
        WHERE p.team IS NULL OR p.team = ''
        GROUP BY s.id
        ORDER BY s.session_date DESC
        LIMIT 10
    ''').fetchall()
    
    # Get team distribution overall
    team_stats = c.execute('''
        SELECT team, COUNT(*) as count
        FROM player_comprehensive_stats
        GROUP BY team
        ORDER BY count DESC
    ''').fetchall()
    
    print(f"\nSessions without any players: {no_players}")
    
    print(f"\nOverall Team Distribution (all player records):")
    total_players = sum(stat[1] for stat in team_stats)
    for team, count in team_stats:
        team_name = team if team else 'NULL/Empty'
        pct = (count / total_players * 100) if total_players > 0 else 0
        print(f"  {team_name:<20} {count:>6} ({pct:>5.1f}%)")
    
    if null_teams:
        print(f"\nSessions with NULL/Empty team assignments (top 10):")
        for sess_id, date, map_name, player_count in null_teams:
            print(f"  Session {sess_id}: {date} - {map_name} "
                  f"({player_count} players with NULL team)")
    
    # Check a specific session's raw data to understand the issue
    print(f"\n{'='*70}")
    print("SAMPLE RAW DATA CHECK (Session 2415 - Latest Oct 2)")
    print(f"{'='*70}")
    
    raw_check = c.execute('''
        SELECT player_name, team, time_axis, time_allies, 
               time_played, xp_total
        FROM player_comprehensive_stats
        WHERE session_id = 2415
    ''').fetchall()
    
    print(f"\nFound {len(raw_check)} players in session 2415:")
    for row in raw_check:
        print(f"  Player: {row[0][:25]:<25}")
        print(f"    Team: '{row[1]}'")
        print(f"    Time Axis: {row[2]}, Time Allies: {row[3]}")
        print(f"    Time Played: {row[4]}, XP: {row[5]}")
        print()
    
    conn.close()

if __name__ == "__main__":
    check_team_detection()
