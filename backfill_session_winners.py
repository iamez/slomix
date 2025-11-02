#!/usr/bin/env python3
"""
Backfill winner_team and defender_team in sessions table

Since ET:Legacy game stats don't include winner info in headers,
we need to calculate it from player_comprehensive_stats:
- Team with more kills wins the round
- Use damage as tiebreaker
"""

import sqlite3

def backfill_session_winners(db_path="bot/etlegacy_production.db"):
    """Calculate and update winner_team for all sessions"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all sessions
    cursor.execute("""
        SELECT id, session_date, map_name, round_number
        FROM sessions
        WHERE winner_team = 0
        ORDER BY id
    """)
    
    sessions = cursor.fetchall()
    
    print(f"Found {len(sessions)} sessions with winner_team=0")
    print("Calculating winners from player stats...\n")
    
    updated = 0
    skipped = 0
    
    for session_id, session_date, map_name, round_num in sessions:
        # Get team stats for this session
        cursor.execute("""
            SELECT team,
                   COUNT(*) as players,
                   SUM(kills) as kills,
                   SUM(deaths) as deaths,
                   SUM(damage_given) as damage
            FROM player_comprehensive_stats
            WHERE session_id = ?
            GROUP BY team
            ORDER BY team
        """, (session_id,))
        
        teams = cursor.fetchall()
        
        if len(teams) != 2:
            print(f"⚠️  Session {session_id}: Found {len(teams)} teams, skipping")
            skipped += 1
            continue
        
        team1_num, team1_players, team1_kills, team1_deaths, team1_damage = teams[0]
        team2_num, team2_players, team2_kills, team2_deaths, team2_damage = teams[1]
        
        # Determine winner
        if team1_kills > team2_kills:
            winner = team1_num
        elif team2_kills > team1_kills:
            winner = team2_num
        elif team1_damage > team2_damage:
            # Tie on kills, use damage
            winner = team1_num
        elif team2_damage > team1_damage:
            winner = team2_num
        else:
            # True tie
            winner = 0
        
        # Update session
        cursor.execute("""
            UPDATE sessions
            SET winner_team = ?
            WHERE id = ?
        """, (winner, session_id))
        
        updated += 1
        
        if updated % 100 == 0:
            print(f"  Processed {updated} sessions...")
            conn.commit()
    
    conn.commit()
    
    print(f"\n{'='*60}")
    print(f"✅ Backfill complete!")
    print(f"{'='*60}")
    print(f"  Updated: {updated}")
    print(f"  Skipped: {skipped}")
    print(f"  Total:   {len(sessions)}")
    
    # Show sample results
    print(f"\n{'='*60}")
    print(f"Sample results:")
    print(f"{'='*60}")
    
    cursor.execute("""
        SELECT map_name, round_number, winner_team
        FROM sessions
        WHERE session_date LIKE '2025-10-30%'
        ORDER BY id
        LIMIT 10
    """)
    
    for map_name, rnd, winner in cursor.fetchall():
        print(f"{map_name:<20} R{rnd} - Winner: Team {winner}")
    
    conn.close()


if __name__ == "__main__":
    backfill_session_winners()
