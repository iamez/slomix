#!/usr/bin/env python3
"""
Backfill weapon stats for all existing sessions in the database.
Reads the original stat files and inserts weapon stats only.
"""

import sqlite3
import sys
from pathlib import Path

# Add bot directory to path for parser
sys.path.insert(0, str(Path(__file__).parent / 'bot'))
from community_stats_parser import C0RNP0RN3StatsParser

def backfill_weapon_stats():
    """Backfill weapon stats for all sessions"""
    
    db_path = 'etlegacy_production.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all sessions that don't have weapon stats yet
    cursor.execute('''
        SELECT s.id, s.session_date, s.map_name, s.round_number
        FROM sessions s
        LEFT JOIN weapon_comprehensive_stats w ON s.id = w.session_id
        WHERE w.id IS NULL
        GROUP BY s.id
        ORDER BY s.session_date, s.map_name, s.round_number
    ''')
    
    sessions_to_process = cursor.fetchall()
    print(f"Found {len(sessions_to_process)} sessions without weapon stats\n")
    
    parser = C0RNP0RN3StatsParser()
    stats_dir = Path('local_stats')
    
    processed = 0
    weapons_inserted = 0
    
    for session_id, session_date, map_name, round_number in sessions_to_process:
        # Find the corresponding file
        # Format: 2025-01-01-211921-etl_adlernest-round-1.txt
        pattern = f"{session_date}*-{map_name}-round-{round_number}.txt"
        files = list(stats_dir.glob(pattern))
        
        if not files:
            print(f"⚠️  Could not find file for session {session_id}: {session_date} {map_name} R{round_number}")
            continue
        
        file_path = files[0]
        
        # Parse the file
        try:
            parsed_data = parser.parse_stats_file(str(file_path))
            
            # Insert weapon stats for each player
            for player_guid, player_data in parsed_data['players'].items():
                weapon_stats = player_data.get('weapon_stats', {})
                
                for weapon_name, stats in weapon_stats.items():
                    if stats['shots'] > 0 or stats['kills'] > 0:
                        cursor.execute('''
                            INSERT INTO weapon_comprehensive_stats (
                                session_id, player_guid, weapon_name,
                                kills, deaths, hits, shots, headshots, accuracy
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            session_id, player_guid, weapon_name,
                            stats['kills'], stats['deaths'], stats['hits'],
                            stats['shots'], stats['headshots'], stats['accuracy']
                        ))
                        weapons_inserted += 1
            
            conn.commit()
            processed += 1
            
            if processed % 100 == 0:
                print(f"Progress: {processed}/{len(sessions_to_process)} sessions, {weapons_inserted} weapons")
                
        except Exception as e:
            print(f"❌ Error processing {file_path}: {e}")
            continue
    
    conn.close()
    
    print(f"\n✅ COMPLETE!")
    print(f"   Sessions processed: {processed}")
    print(f"   Weapon stats inserted: {weapons_inserted}")

if __name__ == '__main__':
    backfill_weapon_stats()
