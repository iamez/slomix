#!/usr/bin/env python3
"""
Verify stopwatch scoring logic for ties.
When R2 completion_time = time_to_beat, R1 attackers defended their time.
"""

import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

print("\n" + "="*80)
print("STOPWATCH SCORING VERIFICATION - TIES")
print("="*80 + "\n")

# Get Oct 30 maps with proper pairing
c.execute("""
    SELECT 
        r1.map_id,
        r1.map_name,
        r1.session_date as r1_date,
        r1.winner_team as r1_winner,
        r1.original_time_limit,
        r1.completion_time as r1_completion,
        r2.session_date as r2_date,
        r2.winner_team as r2_winner,
        r2.time_to_beat,
        r2.completion_time as r2_completion
    FROM sessions r1
    JOIN sessions r2 ON r1.map_id = r2.map_id AND r2.round_number = 2
    WHERE r1.round_number = 1
    AND r1.session_date LIKE '2025-10-30%'
    ORDER BY r1.session_date
""")

maps = c.fetchall()

for map_data in maps:
    (map_id, map_name, r1_date, r1_winner, orig, r1_time, 
     r2_date, r2_winner, beat, r2_time) = map_data
    
    print(f"\nMap ID {map_id}: {map_name}")
    print(f"  R1: Team {r1_winner} attacked, completed in {r1_time} (orig: {orig})")
    print(f"  R2: Team {r2_winner} attacked, completed in {r2_time} (beat: {beat})")
    
    # Determine map winner based on stopwatch rules
    if r2_time < beat:
        expected_winner = r2_winner  # R2 attackers beat the time
        status = "R2 ATTACKERS WIN"
    elif r2_time == beat:
        expected_winner = r1_winner  # TIE - R1 attackers defended
        status = "TIE - R1 ATTACKERS DEFENDED"
    else:
        expected_winner = r1_winner  # R2 failed to beat time
        status = "R1 ATTACKERS WIN"
    
    print(f"  >>> {status}")
    print(f"  >>> Map winner should be: Team {expected_winner}")
    
    if r2_time == beat:
        print(f"  ⚠️  TRUE TIE DETECTED: Both teams took {beat}")

conn.close()
