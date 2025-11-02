#!/usr/bin/env python3
"""
Calculate map-level scores (not rounds)

In stopwatch mode, typically rounds are paired into maps.
Team wins a map if they win both rounds or win by better time.
"""

import sqlite3
from collections import defaultdict

def calculate_map_scores(session_date):
    conn = sqlite3.connect('bot/etlegacy_production.db')
    c = conn.cursor()
    
    # Get rounds grouped by map
    c.execute("""
        SELECT id, map_name, round_number
        FROM sessions
        WHERE session_date LIKE ?
        ORDER BY id
    """, (f"{session_date}%",))
    
    rounds = c.fetchall()
    
    # Group into maps
    maps = defaultdict(list)
    for sess_id, map_name, round_num in rounds:
        maps[map_name].append((sess_id, round_num))
    
    print(f"\n{'='*80}")
    print(f"Map Analysis: {session_date}")
    print(f"{'='*80}\n")
    
    team1_map_wins = 0
    team2_map_wins = 0
    
    for map_name, map_rounds in maps.items():
        print(f"\n{map_name}:")
        map_rounds.sort(key=lambda x: x[1])  # Sort by round number
        
        team1_round_wins = 0
        team2_round_wins = 0
        
        for sess_id, round_num in map_rounds:
            # Get kills per team
            c.execute("""
                SELECT team, SUM(kills) as kills
                FROM player_comprehensive_stats
                WHERE session_id = ?
                GROUP BY team
                ORDER BY team
            """, (sess_id,))
            
            teams = c.fetchall()
            if len(teams) == 2:
                t1_kills = teams[0][1]
                t2_kills = teams[1][1]
                
                if t1_kills > t2_kills:
                    winner = "Team 1"
                    team1_round_wins += 1
                elif t2_kills > t1_kills:
                    winner = "Team 2"
                    team2_round_wins += 1
                else:
                    winner = "Tie"
                
                print(f"  Round {round_num}: T1 {t1_kills}K vs T2 {t2_kills}K → {winner}")
        
        # Determine map winner
        if team1_round_wins > team2_round_wins:
            print(f"  → MAP WIN: Team 1")
            team1_map_wins += 1
        elif team2_round_wins > team1_round_wins:
            print(f"  → MAP WIN: Team 2")
            team2_map_wins += 1
        else:
            print(f"  → MAP TIE")
    
    total_maps = len(maps)
    print(f"\n{'='*80}")
    print(f"Map Wins:")
    print(f"{'='*80}")
    print(f"Team 1: {team1_map_wins}/{total_maps} maps = {team1_map_wins/total_maps*100:.1f}%")
    print(f"Team 2: {team2_map_wins}/{total_maps} maps = {team2_map_wins/total_maps*100:.1f}%")
    print(f"{'='*80}\n")
    
    conn.close()

if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else "2025-10-30"
    calculate_map_scores(date)
