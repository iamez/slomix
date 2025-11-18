#!/usr/bin/env python3
"""
Analyze gaming sessions (ENTIRE DAYS) for Oct 28 and Oct 30

CRITICAL TERMINOLOGY FIX:
- GAMING SESSION = All games played on one date (user sits down and plays)
- ROUND = One map round (what database calls "session")
- MAP = Two rounds (R1 + R2)
"""

import sqlite3

def analyze_gaming_session(date):
    """Analyze one gaming session (full day of games)"""
    conn = sqlite3.connect('bot/etlegacy_production.db')
    c = conn.cursor()
    
    print(f"\n{'='*80}")
    print(f"🎮 GAMING SESSION: {date}")
    print(f"{'='*80}\n")
    
    # Get all rounds (database calls them "rounds") for this date
    c.execute("""
        SELECT id, map_name, round_number, time_limit, actual_time, winner_team
        FROM rounds
        WHERE substr(round_date, 1, 10) = ?
        ORDER BY id
    """, (date,))
    
    rounds = c.fetchall()
    
    print(f"Total rounds played: {len(rounds)}")
    print(f"\nRound-by-round breakdown:")
    print(f"{'#':<4} {'ID':<6} {'Map':<20} {'Round':<7} {'Winner':<10} {'Time'}")
    print("-" * 70)
    
    for i, (sess_id, map_name, rnd, limit, actual, winner) in enumerate(rounds, 1):
        print(f"{i:<4} {sess_id:<6} {map_name:<20} R{rnd:<6} Team {winner:<5} {actual}/{limit}")
    
    # Count round wins per team
    team1_wins = sum(1 for r in rounds if r[5] == 1)
    team2_wins = sum(1 for r in rounds if r[5] == 2)
    
    print(f"\n{'='*80}")
    print(f"Round Win Summary:")
    print(f"{'='*80}")
    print(f"Team 1: {team1_wins} rounds won ({team1_wins/len(rounds)*100:.1f}%)")
    print(f"Team 2: {team2_wins} rounds won ({team2_wins/len(rounds)*100:.1f}%)")
    
    # Try to identify complete maps (consecutive R1+R2 pairs)
    print(f"\n{'='*80}")
    print(f"Map Pairing Analysis:")
    print(f"{'='*80}\n")
    
    maps_completed = []
    i = 0
    while i < len(rounds):
        current = rounds[i]
        
        # Check if next round exists and is same map
        if i + 1 < len(rounds):
            next_round = rounds[i + 1]
            
            # Check if it's a proper R1->R2 pair
            if (current[1] == next_round[1] and  # same map
                current[2] == 1 and next_round[2] == 2):  # R1 then R2
                
                print(f"✅ Complete Map: {current[1]}")
                print(f"   R1 (ID {current[0]}): Team {current[5]} won - {current[4]}/{current[3]}")
                print(f"   R2 (ID {next_round[0]}): Team {next_round[5]} won - {next_round[4]}/{next_round[3]}")
                
                maps_completed.append({
                    'map': current[1],
                    'r1_winner': current[5],
                    'r2_winner': next_round[5]
                })
                i += 2
            else:
                print(f"⚠️  Orphaned Round: {current[1]} R{current[2]} (ID {current[0]})")
                i += 1
        else:
            print(f"⚠️  Orphaned Round: {current[1]} R{current[2]} (ID {current[0]})")
            i += 1
    
    print(f"\n{'='*80}")
    print(f"Map Score (only complete maps):")
    print(f"{'='*80}")
    
    team1_map_wins = 0
    team2_map_wins = 0
    
    for m in maps_completed:
        r1_win = m['r1_winner']
        r2_win = m['r2_winner']
        
        if r1_win == 1 and r2_win == 1:
            winner = "Team 1 (2-0)"
            team1_map_wins += 1
        elif r1_win == 2 and r2_win == 2:
            winner = "Team 2 (2-0)"
            team2_map_wins += 1
        elif r1_win == 1 and r2_win == 2:
            winner = "Split (1-1)"
        elif r1_win == 2 and r2_win == 1:
            winner = "Split (1-1)"
        else:
            winner = "Unknown"
        
        print(f"{m['map']:<20} → {winner}")
    
    print(f"\nMap Wins: Team 1: {team1_map_wins}, Team 2: {team2_map_wins}")
    
    conn.close()
    print(f"\n")


if __name__ == "__main__":
    analyze_gaming_session("2025-10-28")
    analyze_gaming_session("2025-10-30")
