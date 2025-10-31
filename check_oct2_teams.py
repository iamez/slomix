#!/usr/bin/env python3
"""
Simple check of team assignments for October 2, 2025
"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

print("="*70)
print("October 2, 2025 - Team Distribution Check")
print("="*70)

# Get sessions from Oct 2
sessions = c.execute('''
    SELECT DISTINCT s.id, s.map_name, s.round_number
    FROM sessions s
    JOIN player_comprehensive_stats p ON s.id = p.session_id
    WHERE s.session_date = '2025-10-02'
    ORDER BY s.id
''').fetchall()

print(f"\nFound {len(sessions)} sessions with players on 2025-10-02\n")

team_names = {1: 'Axis', 2: 'Allies', 3: 'Spectator'}

for sess_id, map_name, round_num in sessions[:8]:  # Show first 8
    print(f"Session {sess_id}: {map_name} Round {round_num}")
    
    # Get team distribution
    teams = c.execute('''
        SELECT team, COUNT(*) as count
        FROM player_comprehensive_stats
        WHERE session_id = ?
        GROUP BY team
        ORDER BY team
    ''', (sess_id,)).fetchall()
    
    for team_num, count in teams:
        team_name = team_names.get(team_num, f'Unknown({team_num})')
        print(f"  {team_name}: {count} players")
    
    # Show sample players
    sample = c.execute('''
        SELECT player_name, team, kills, deaths
        FROM player_comprehensive_stats
        WHERE session_id = ?
        ORDER BY kills DESC
        LIMIT 3
    ''', (sess_id,)).fetchall()
    
    print("  Top players:")
    for name, team, kills, deaths in sample:
        team_name = team_names.get(team, f'?{team}')
        print(f"    {name[:20]:20} ({team_name:8}) K:{kills:2} D:{deaths:2}")
    print()

conn.close()
