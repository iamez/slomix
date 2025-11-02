"""
Investigate why certain fields have file values but DB shows 0
"""
import sqlite3
import os
from pathlib import Path

def check_session_data():
    """Check specific session mentioned by user"""
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    # Get the session (note: sessions table uses 'id' not 'session_id')
    cursor.execute("""
        SELECT id, session_date, map_name, round_number
        FROM sessions 
        WHERE session_date LIKE '%2025-10-28-212120%'
    """)
    
    sessions = cursor.fetchall()
    print(f"Found {len(sessions)} sessions matching 2025-10-28-212120")
    print()
    
    for session_id, session_date, map_name, round_num in sessions:
        print(f"Session ID: {session_id}")
        print(f"Session Date: {session_date}")
        print(f"Map: {map_name}, Round: {round_num}")
        print("-" * 80)
        
        # Check player data for problematic fields
        cursor.execute("""
            SELECT 
                player_name,
                team_damage_given,
                team_damage_received,
                headshot_kills,
                most_useful_kills,
                double_kills
            FROM player_comprehensive_stats
            WHERE session_id = ?
            ORDER BY player_name
        """, (session_id,))
        
        players = cursor.fetchall()
        print(f"\nDatabase values for {len(players)} players:")
        print(f"{'Player':<20} TDG  TDR  HS  Useful  2x")
        for player in players:
            print(f"{player[0]:<20} {player[1]:<4} {player[2]:<4} {player[3]:<3} {player[4]:<7} {player[5]}")
        
        # Now check the raw file
        print(f"\n{'='*80}")
        # Construct filename from session_date
        filename = f"{session_date}-{map_name}-round-{round_num}.txt"
        print(f"Checking raw file: {filename}")
        print(f"{'='*80}")
        
        file_path = Path('local_stats') / filename
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Find extended stats section
            in_extended = False
            print(f"\nRaw file extended stats (TAB-separated fields):")
            print(f"{'Player':<20} TDG  TDR  HS  Useful  2x")
            
            for line in lines:
                if line.startswith('EXTENDED STATS'):
                    in_extended = True
                    continue
                
                if in_extended and line.strip() and not line.startswith('END'):
                    parts = line.strip().split('\t')
                    if len(parts) >= 10:
                        player_name = parts[0]
                        # TAB fields: damage_given, damage_received, team_damage_given, team_damage_received, ...
                        # Position 2 = team_damage_given, 3 = team_damage_received
                        # Position 7 = headshot_kills, 8 = useful_kills, 9 = multikill_2x
                        tdg = parts[2] if len(parts) > 2 else '?'
                        tdr = parts[3] if len(parts) > 3 else '?'
                        hs = parts[7] if len(parts) > 7 else '?'
                        useful = parts[8] if len(parts) > 8 else '?'
                        mk2 = parts[9] if len(parts) > 9 else '?'
                        
                        print(f"{player_name:<20} {tdg:<4} {tdr:<4} {hs:<3} {useful:<7} {mk2}")
        else:
            print(f"FILE NOT FOUND: {file_path}")
        
        print("\n")
    
    conn.close()

if __name__ == '__main__':
    check_session_data()
