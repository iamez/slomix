#!/usr/bin/env python3
"""
Check R2 rounds where completion_time equals time_to_beat (ties).
These are critical for scoring - when R2 matches R1's time exactly.
"""

import sqlite3

def check_r2_ties():
    conn = sqlite3.connect('bot/etlegacy_production.db')
    c = conn.cursor()
    
    # Find R2 rounds where they matched the time exactly
    c.execute("""
        SELECT 
            round_date,
            map_name,
            round_number,
            original_time_limit,
            time_to_beat,
            completion_time,
            winner_team,
            map_id
        FROM rounds
        WHERE round_number = 2 
        AND time_to_beat = completion_time
        AND time_to_beat IS NOT NULL
        ORDER BY round_date
    """)
    
    ties = c.fetchall()
    
    print(f"\n{'='*100}")
    print("R2 ROUNDS WHERE TEAMS TIED (completion_time = time_to_beat)")
    print(f"{'='*100}\n")
    print(f"Found {len(ties)} R2 ties where defending team matched R1's time exactly\n")
    
    if ties:
        print(f"{'Date':<20} {'Map':<25} {'To Beat':<12} {'Completed':<12} {'Winner':<8} {'MapID'}")
        print('-'*100)
        
        for row in ties:
            date, map_name, rnd, orig, to_beat, completed, winner, map_id = row
            print(f"{date:<20} {map_name:<25} {to_beat:<12} {completed:<12} Team {winner:<5} {map_id}")
    
    # Now let's get the paired R1 data for context
    print(f"\n{'='*100}")
    print("FULL MAP CONTEXT (R1 + R2 pairs for ties)")
    print(f"{'='*100}\n")
    
    for row in ties:
        date, map_name, rnd, orig, to_beat, completed, winner, map_id = row
        
        # Get both rounds for this map
        c.execute("""
            SELECT 
                round_date,
                map_name,
                round_number,
                original_time_limit,
                time_to_beat,
                completion_time,
                winner_team
            FROM rounds
            WHERE map_id = ?
            ORDER BY round_number
        """, (map_id,))
        
        rounds = c.fetchall()
        
        print(f"\nMap ID {map_id}: {map_name}")
        print(f"  R1: Original limit {rounds[0][3]} → Completed in {rounds[0][5]} (Winner: Team {rounds[0][6]})")
        print(f"  R2: Had to beat {rounds[1][4]} → Completed in {rounds[1][5]} (Winner: Team {rounds[1][6]})")
        print(f"  >>> TIE! Both teams took exactly {to_beat}")
    
    conn.close()
    
    return len(ties)

if __name__ == '__main__':
    check_r2_ties()
