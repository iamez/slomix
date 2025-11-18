"""
Backfill round outcomes (winner_team, round_outcome, defender_team, is_tied)
for existing rounds from raw stats files.
"""
import sys
import sqlite3
import os

sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

db_path = 'bot/etlegacy_production.db'
parser = C0RNP0RN3StatsParser()

def find_raw_file(round_date, round_time, map_name, round_number):
    """Find the raw stats file for a round"""
    time_formatted = round_time.replace(':', '')
    pattern = f"{round_date}-{time_formatted}-{map_name}-round-{round_number}.txt"
    
    search_dirs = ['local_stats', 'bot/local_stats']
    for search_dir in search_dirs:
        if os.path.exists(search_dir):
            filepath = os.path.join(search_dir, pattern)
            if os.path.exists(filepath):
                return filepath
    return None

def main():
    print("=" * 80)
    print("BACKFILLING ROUND OUTCOMES")
    print("=" * 80)
    print()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all rounds that don't have outcome data
    cursor.execute('''
        SELECT id, round_date, round_time, map_name, round_number
        FROM rounds
        WHERE round_outcome IS NULL OR winner_team = 0
        ORDER BY id
    ''')
    
    rounds = cursor.fetchall()
    
    print(f"📊 Found {len(rounds)} rounds needing outcome data\n")
    
    updated = 0
    skipped = 0
    
    for round_id, round_date, round_time, map_name, round_num in rounds:
        # Find raw file
        raw_file = find_raw_file(round_date, round_time, map_name, round_num)
        
        if not raw_file:
            print(f"⚠️  Round {round_id}: No raw file found")
            skipped += 1
            continue
        
        # Parse it
        parsed = parser.parse_stats_file(raw_file)
        
        if not parsed:
            print(f"❌ Round {round_id}: Failed to parse {os.path.basename(raw_file)}")
            skipped += 1
            continue
        
        winner_team = parsed.get('winner_team', 0)
        
        # Determine outcome
        if winner_team == 0:
            round_outcome = "Tie"
            is_tied = 1
        elif winner_team == 1:
            round_outcome = "Axis Victory"
            is_tied = 0
        elif winner_team == 2:
            round_outcome = "Allies Victory"
            is_tied = 0
        else:
            round_outcome = None
            is_tied = 0
        
        # Defender team (R1 = Axis, R2 = Allies)
        defender_team = 1 if round_num == 1 else 2
        
        # Update database
        cursor.execute('''
            UPDATE rounds
            SET winner_team = ?, defender_team = ?, is_tied = ?, round_outcome = ?
            WHERE id = ?
        ''', (winner_team, defender_team, is_tied, round_outcome, round_id))
        
        print(f"✅ Round {round_id}: {map_name} R{round_num} - {round_outcome}")
        updated += 1
    
    conn.commit()
    conn.close()
    
    print()
    print("=" * 80)
    print(f"✅ Updated: {updated} rounds")
    print(f"⚠️  Skipped: {skipped} rounds")
    print("=" * 80)

if __name__ == '__main__':
    main()
