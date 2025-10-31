"""
Check if BOTH 8-2 AND 5-5 scores are correct depending on scoring system used.

Two possible scoring systems:
1. MAP WINS: Each map is worth 1 point (winner-takes-all)
2. POINT SYSTEM: Winner gets 2 points, loser gets 1 if they completed (0 if they didn't)
"""

import sqlite3

DB_PATH = 'etlegacy_production.db'

# Team rosters from session_teams table
TEAM_A_GUIDS = ['9BCDBB6D', '9E21C51D', 'D7EE4F38']  # SuperBoyy, qmr, SmetarskiProner
TEAM_B_GUIDS = ['5C3D0BC7', 'D8423F90', 'E16F9C0A']  # .olz, vid, endekk

def get_october_2_matches():
    """Get all October 2nd session data."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = """
    SELECT DISTINCT session_id, map_name
    FROM player_comprehensive_stats
    WHERE session_date = '2025-10-02'
    ORDER BY session_id
    """
    
    cursor.execute(query)
    sessions = cursor.fetchall()
    conn.close()
    
    # Group into matches (2 rounds each)
    matches = []
    for i in range(0, len(sessions), 2):
        if i + 1 < len(sessions):
            matches.append({
                'match_num': (i // 2) + 1,
                'map': sessions[i][1],
                'round1_id': sessions[i][0],
                'round2_id': sessions[i + 1][0]
            })
    
    return matches

def get_round_result(session_id):
    """Get result for a single round."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = """
    SELECT player_guid, player_name, team
    FROM player_comprehensive_stats
    WHERE session_id = ?
    ORDER BY player_guid
    """
    
    cursor.execute(query, (session_id,))
    players = cursor.fetchall()
    
    # Also get the objectives to see if round was completed
    query2 = """
    SELECT objectives_completed
    FROM player_comprehensive_stats
    WHERE session_id = ?
    ORDER BY objectives_completed DESC
    LIMIT 1
    """
    cursor.execute(query2, (session_id,))
    result = cursor.fetchone()
    max_objectives = result[0] if result else 0
    
    conn.close()
    
    # Determine which team is which
    # team: 0 = Axis (defenders), 1 = Allies (attackers), 2 = Spectator
    team_a_side = None
    team_b_side = None
    
    for guid, name, team in players:
        if guid in TEAM_A_GUIDS and team_a_side is None:
            if team == 0:
                team_a_side = 'Axis'
            elif team == 1:
                team_a_side = 'Allies'
        if guid in TEAM_B_GUIDS and team_b_side is None:
            if team == 0:
                team_b_side = 'Axis'
            elif team == 1:
                team_b_side = 'Allies'
    
    # Check if objectives were completed
    completed = max_objectives > 0
    completion_time = None  # We don't have this in the unified schema
    
    return {
        'team_a_side': team_a_side,
        'team_b_side': team_b_side,
        'completed': completed,
        'time': completion_time
    }

def time_to_seconds(time_str):
    """Convert MM:SS to seconds."""
    if not time_str or time_str == "0:00":
        return 999999
    parts = time_str.split(':')
    return int(parts[0]) * 60 + int(parts[1])

def main():
    print("="*80)
    print("OCTOBER 2ND SCORING VERIFICATION - BOTH SYSTEMS")
    print("="*80)
    print()
    
    matches = get_october_2_matches()
    
    # Scoring System 1: MAP WINS (winner-takes-all)
    map_wins_a = 0
    map_wins_b = 0
    
    # Scoring System 2: POINT SYSTEM (2 for win, 1 for completion, 0 for fail)
    points_a = 0
    points_b = 0
    
    print(f"{'#':<3} {'Map':<20} {'R1 Winner':<15} {'R2 Winner':<15} {'Map Winner':<12} {'Points A':<10} {'Points B':<10}")
    print("-" * 95)
    
    for match in matches:
        r1 = get_round_result(match['round1_id'])
        r2 = get_round_result(match['round2_id'])
        
        # Determine attacking team in each round (Allies = attackers)
        r1_attacker = 'Team A' if r1['team_a_side'] == 'Allies' else 'Team B'
        r2_attacker = 'Team A' if r2['team_a_side'] == 'Allies' else 'Team B'
        
        # Round 1 result
        r1_winner = None
        if r1['completed']:
            r1_winner = r1_attacker
        else:
            r1_winner = 'Team B' if r1_attacker == 'Team A' else 'Team A'
        
        # Round 2 result
        r2_winner = None
        if r2['completed']:
            r2_winner = r2_attacker
        else:
            r2_winner = 'Team B' if r2_attacker == 'Team A' else 'Team A'
        
        # Map winner (faster completion or successful defense)
        map_winner = None
        match_points_a = 0
        match_points_b = 0
        
        if r1['completed'] and r2['completed']:
            # Both completed - faster wins
            r1_time = time_to_seconds(r1['time'])
            r2_time = time_to_seconds(r2['time'])
            
            if r1_time < r2_time:
                map_winner = r1_attacker
            else:
                map_winner = r2_attacker
            
            # Points: Winner gets 2, loser gets 1
            if map_winner == 'Team A':
                match_points_a = 2
                match_points_b = 1
            else:
                match_points_a = 1
                match_points_b = 2
                
        elif r1['completed'] and not r2['completed']:
            # R1 completed, R2 failed - R1 attacker wins
            map_winner = r1_attacker
            
            # Points: Winner gets 2, loser gets 0 (didn't complete)
            if map_winner == 'Team A':
                match_points_a = 2
                match_points_b = 0
            else:
                match_points_a = 0
                match_points_b = 2
                
        elif not r1['completed'] and r2['completed']:
            # R1 failed, R2 completed - R2 attacker wins
            map_winner = r2_attacker
            
            # Points: Winner gets 2, loser gets 0
            if map_winner == 'Team A':
                match_points_a = 2
                match_points_b = 0
            else:
                match_points_a = 0
                match_points_b = 2
        else:
            # Both failed - this shouldn't happen in stopwatch
            map_winner = "TIE"
        
        # Update totals
        if map_winner == 'Team A':
            map_wins_a += 1
        elif map_winner == 'Team B':
            map_wins_b += 1
        
        points_a += match_points_a
        points_b += match_points_b
        
        print(f"{match['match_num']:<3} {match['map']:<20} {r1_winner:<15} {r2_winner:<15} {map_winner:<12} {match_points_a:<10} {match_points_b:<10}")
    
    print("="*95)
    print()
    print("📊 FINAL RESULTS:")
    print()
    print("SCORING SYSTEM #1: MAP WINS (Winner-Takes-All)")
    print(f"  Team A: {map_wins_a} maps won")
    print(f"  Team B: {map_wins_b} maps won")
    print(f"  Score: {map_wins_a}-{map_wins_b}")
    print()
    print("SCORING SYSTEM #2: POINT SYSTEM (2 pts win, 1 pt complete)")
    print(f"  Team A: {points_a} points")
    print(f"  Team B: {points_b} points")
    print(f"  Score: {points_a}-{points_b}")
    print()
    print("="*80)
    print()
    print("🤔 WHICH IS CORRECT?")
    print()
    print("If you're using MAP WINS: Score should be 5-5")
    print("If you're using POINT SYSTEM: Score should be 8-2 or similar")
    print()
    print("Check SuperBoyy's manual spreadsheet to see which system he uses!")
    print()

if __name__ == '__main__':
    main()
