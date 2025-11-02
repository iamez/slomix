#!/usr/bin/env python3
"""
Calculate actual round winners from player stats

Since winner_team field in sessions is empty (all 0s), we need to 
determine round winners from player_comprehensive_stats by:
1. Comparing team kills
2. Comparing K/D ratios
3. Comparing damage dealt
"""

import sqlite3
import json

def calculate_round_winner(session_id, round_number, conn):
    """
    Determine which team won a specific round
    
    Returns: (winner_team_number, team1_stats, team2_stats)
    """
    c = conn.cursor()
    
    c.execute("""
        SELECT team,
               COUNT(*) as players,
               SUM(kills) as kills,
               SUM(deaths) as deaths,
               SUM(damage_given) as damage
        FROM player_comprehensive_stats
        WHERE session_id = ? AND round_number = ?
        GROUP BY team
        ORDER BY team
    """, (session_id, round_number))
    
    teams = c.fetchall()
    
    if len(teams) != 2:
        return (0, None, None)  # Can't determine winner
    
    team1 = {'team': teams[0][0], 'players': teams[0][1], 'kills': teams[0][2], 
             'deaths': teams[0][3], 'damage': teams[0][4]}
    team2 = {'team': teams[1][0], 'players': teams[1][1], 'kills': teams[1][2], 
             'deaths': teams[1][3], 'damage': teams[1][4]}
    
    # Determine winner by kills first
    if team1['kills'] > team2['kills']:
        return (team1['team'], team1, team2)
    elif team2['kills'] > team1['kills']:
        return (team2['team'], team1, team2)
    else:
        # Tie on kills - use damage
        if team1['damage'] > team2['damage']:
            return (team1['team'], team1, team2)
        elif team2['damage'] > team1['damage']:
            return (team2['team'], team1, team2)
        else:
            return (0, team1, team2)  # True tie


def calculate_session_scores(session_date):
    """Calculate round-based scoring for a session"""
    conn = sqlite3.connect('bot/etlegacy_production.db')
    c = conn.cursor()
    
    # Get all rounds
    c.execute("""
        SELECT id, map_name, round_number
        FROM sessions
        WHERE session_date LIKE ?
        ORDER BY id
    """, (f"{session_date}%",))
    
    rounds = c.fetchall()
    
    team1_wins = 0
    team2_wins = 0
    ties = 0
    
    print(f"\n{'='*80}")
    print(f"Round-by-Round Analysis: {session_date}")
    print(f"{'='*80}\n")
    
    for sess_id, map_name, round_num in rounds:
        winner, team1, team2 = calculate_round_winner(sess_id, round_num, conn)
        
        if winner == 0:
            result = "TIE"
            ties += 1
        elif winner == 1:
            result = "TEAM 1 WIN"
            team1_wins += 1
        else:
            result = "TEAM 2 WIN"
            team2_wins += 1
        
        if team1 and team2:
            print(f"{map_name:<20} R{round_num} - T1: {team1['kills']:3d}K  T2: {team2['kills']:3d}K  → {result}")
    
    total_rounds = len(rounds)
    team1_pct = (team1_wins / total_rounds * 100) if total_rounds > 0 else 0
    team2_pct = (team2_wins / total_rounds * 100) if total_rounds > 0 else 0
    
    print(f"\n{'='*80}")
    print(f"Final Round Win Percentages:")
    print(f"{'='*80}")
    print(f"Team 1: {team1_wins}/{total_rounds} rounds = {team1_pct:.1f}%")
    print(f"Team 2: {team2_wins}/{total_rounds} rounds = {team2_pct:.1f}%")
    print(f"Ties:   {ties}/{total_rounds} rounds")
    print(f"{'='*80}\n")
    
    # Get team names from session_teams
    c.execute("""
        SELECT team_name, player_guids
        FROM session_teams
        WHERE session_start_date = ? AND map_name = 'ALL'
        ORDER BY team_name
    """, (session_date,))
    
    teams_data = c.fetchall()
    if teams_data:
        print("Team Names:")
        for team_name, guids_json in teams_data:
            guids = json.loads(guids_json)
            print(f"  {team_name}: {len(guids)} players")
    
    conn.close()
    
    return team1_wins, team2_wins, ties, total_rounds


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        date = sys.argv[1]
    else:
        date = "2025-10-30"
    
    calculate_session_scores(date)
