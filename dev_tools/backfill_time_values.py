#!/usr/bin/env python3
"""
Backfill proper time values from stat file headers

Reads actual stat files from local_stats/ and extracts:
- R1: original_time_limit from header field 6
- R1: completion_time from header field 7
- R2: time_to_beat from header field 6 (R1's completion time)
- R2: completion_time from header field 7
"""

import sqlite3
import os
import glob


def parse_stat_file_header(filepath):
    """Parse header from stat file to get time values"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            header = f.readline().strip()
            
        # Split by backslash
        parts = header.split('\\')
        
        if len(parts) < 8:
            return None
        
        map_name = parts[1]
        round_num = int(parts[3]) if parts[3].isdigit() else 1
        time_field_6 = parts[6]  # Original limit (R1) or Time to beat (R2)
        time_field_7 = parts[7]  # Actual completion time
        
        return {
            'map_name': map_name,
            'round_number': round_num,
            'time_field_6': time_field_6,
            'time_field_7': time_field_7
        }
    except Exception as e:
        print(f"⚠️  Error parsing {filepath}: {e}")
        return None


def backfill_time_values(stats_dir='local_stats', db_path='bot/etlegacy_production.db'):
    """Backfill time values from stat files"""
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    print("🔍 Scanning for stat files...")
    print()
    
    # Get all stat files (format: YYYY-MM-DD-HHMMSS-mapname-round-X.txt)
    stat_files = glob.glob(os.path.join(stats_dir, '*.txt'))
    
    if not stat_files:
        print(f"❌ No stat files found in {stats_dir}/")
        return
    
    print(f"Found {len(stat_files)} stat files")
    print()
    
    # Group files by round_date and map_name to find R1+R2 pairs
    updates = []
    map_pairs = {}  # Key: (round_date, map_name), Value: {R1: data, R2: data}
    
    for stat_file in sorted(stat_files):
        filename = os.path.basename(stat_file)
        
        # Extract round_date from filename
        # Format: YYYY-MM-DD-HHMMSS-mapname-round-X.txt
        parts = filename.split('-')
        if len(parts) < 7:
            continue
        
        # round_date format: YYYY-MM-DD-HHMMSS
        round_date = f"{parts[0]}-{parts[1]}-{parts[2]}-{parts[3]}"
        
        # Parse the stat file header
        header_data = parse_stat_file_header(stat_file)
        if not header_data:
            continue
        
        map_name = header_data['map_name']
        round_num = header_data['round_number']
        
        key = (round_date, map_name)
        
        if key not in map_pairs:
            map_pairs[key] = {}
        
        map_pairs[key][round_num] = {
            'round_date': round_date,
            'map_name': map_name,
            'round_number': round_num,
            'time_field_6': header_data['time_field_6'],
            'time_field_7': header_data['time_field_7'],
            'filename': filename
        }
    
    print("="*80)
    print("Processing map pairs...")
    print("="*80)
    print()
    
    updates_count = 0
    
    for key, rounds in map_pairs.items():
        round_date, map_name = key
        
        # Process R1
        if 1 in rounds:
            r1 = rounds[1]
            
            # For R1: field 6 = original limit, field 7 = completion time
            original_limit = r1['time_field_6']
            completion = r1['time_field_7']
            
            c.execute("""
                UPDATE rounds
                SET original_time_limit = ?,
                    completion_time = ?,
                    time_to_beat = NULL
                WHERE round_date = ?
                AND map_name = ?
                AND round_number = 1
            """, (original_limit, completion, round_date, map_name))
            
            if c.rowcount > 0:
                updates_count += 1
                print(f"✅ R1: {round_date} {map_name:<20} "
                      f"Original: {original_limit} → Completed: {completion}")
        
        # Process R2
        if 2 in rounds:
            r2 = rounds[2]
            
            # For R2: field 6 = time to beat (R1's time), field 7 = completion
            time_to_beat = r2['time_field_6']
            completion = r2['time_field_7']
            
            # Get original limit from R1 if available
            original_limit = rounds[1]['time_field_6'] if 1 in rounds else None
            
            c.execute("""
                UPDATE rounds
                SET original_time_limit = ?,
                    time_to_beat = ?,
                    completion_time = ?
                WHERE round_date = ?
                AND map_name = ?
                AND round_number = 2
            """, (original_limit, time_to_beat, completion, round_date, map_name))
            
            if c.rowcount > 0:
                updates_count += 1
                print(f"✅ R2: {round_date} {map_name:<20} "
                      f"Beat: {time_to_beat} → Completed: {completion}")
    
    conn.commit()
    
    print()
    print("="*80)
    print(f"✅ Updated {updates_count} rounds with proper time values")
    print("="*80)
    
    # Show sample results
    print()
    print("Sample results:")
    print()
    
    c.execute("""
        SELECT round_date, map_name, round_number,
               original_time_limit, time_to_beat, completion_time
        FROM rounds
        WHERE round_date LIKE '2025-10-30%'
        AND completion_time IS NOT NULL
        ORDER BY id
        LIMIT 10
    """)
    
    print(f"{'Date':<20} {'Map':<20} {'R':<3} {'Original':<10} {'To Beat':<10} {'Completed':<10}")
    print("-"*80)
    
    for row in c.fetchall():
        date, map_name, rnd, orig, beat, comp = row
        orig_str = orig or "N/A"
        beat_str = beat or "N/A"
        comp_str = comp or "N/A"
        print(f"{date:<20} {map_name:<20} R{rnd:<2} {orig_str:<10} {beat_str:<10} {comp_str:<10}")
    
    conn.close()


if __name__ == "__main__":
    backfill_time_values()
