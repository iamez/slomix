"""
Backfill script to re-import sessions with missing/zero stats

This will:
1. Find sessions with zero accuracy/time_dead (affected by the parser bug)
2. Re-parse the raw files with the fixed parser
3. Update the database with correct values
"""
import sqlite3
import sys
import os
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

db_path = "bot/etlegacy_production.db"

print("=" * 100)
print("BACKFILL SCRIPT - Fix missing accuracy and time_dead stats")
print("=" * 100)

# Find affected sessions
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""
    SELECT 
        s.id, s.round_date, s.map_name, s.round_number,
        COUNT(*) as player_count,
        SUM(CASE WHEN p.accuracy = 0 THEN 1 ELSE 0 END) as zero_acc
    FROM rounds s
    JOIN player_comprehensive_stats p ON s.id = p.round_id AND s.round_number = p.round_number
    WHERE s.id >= (SELECT MAX(id) - 100 FROM rounds)
    GROUP BY s.id
    HAVING zero_acc > player_count * 0.5
    ORDER BY s.id
""")

affected_sessions = cursor.fetchall()

print(f"\nFound {len(affected_sessions)} affected sessions")
print("Will attempt to re-import from raw files\n")

parser = C0RNP0RN3StatsParser()
success_count = 0
skip_count = 0
error_count = 0

for sid, sdate, map_name, rnum, pcount, zacc in affected_sessions:
    print(f"Session {sid} R{rnum} {map_name[:20]:20s} ", end="")
    
    # Find raw file
    date_prefix = sdate[:10]
    try:
        all_files = os.listdir('bot/local_stats')
        raw_files = [f for f in all_files 
                     if map_name in f and f'round-{rnum}.txt' in f and date_prefix in f]
        
        if not raw_files:
            print("[SKIP] No raw file")
            skip_count += 1
            continue
        
        raw_file = f"bot/local_stats/{raw_files[0]}"
        
        # Parse with fixed parser
        result = parser.parse_stats_file(raw_file)
        parsed_players = result.get('players', [])
        
        if not parsed_players:
            print("[SKIP] No players in parsed result")
            skip_count += 1
            continue
        
        # Update database for each player
        updates = 0
        for player in parsed_players:
            guid = player.get('guid')
            if not guid:
                continue
            
            # Get values from parser
            accuracy = player.get('accuracy', 0.0)
            obj_stats = player.get('objective_stats', {})
            time_dead_mins = obj_stats.get('time_dead_minutes', 0)
            time_dead_ratio = obj_stats.get('time_dead_ratio', 0)
            
            # Update database
            cursor.execute("""
                UPDATE player_comprehensive_stats
                SET accuracy = ?, time_dead_minutes = ?, time_dead_ratio = ?
                WHERE round_id = ? AND round_number = ? AND player_guid = ?
            """, (accuracy, time_dead_mins, time_dead_ratio, sid, rnum, guid))
            
            if cursor.rowcount > 0:
                updates += 1
        
        conn.commit()
        print(f"[OK] Updated {updates} players")
        success_count += 1
        
    except Exception as e:
        print(f"[ERROR] {e}")
        error_count += 1

conn.close()

print(f"\n{'=' * 100}")
print("BACKFILL COMPLETE")
print(f"  Success: {success_count}")
print(f"  Skipped: {skip_count}")
print(f"  Errors: {error_count}")
print("=" * 100)
