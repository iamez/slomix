#!/usr/bin/env python3
"""
Add map_id column to sessions table (which actually stores ROUNDS)
This properly links R1 and R2 together as one MAP
"""

import sqlite3

def add_map_id_column():
    """Add map_id column and backfill for Oct 28 and Oct 30"""
    conn = sqlite3.connect('bot/etlegacy_production.db')
    c = conn.cursor()
    
    # Add column
    print("Adding map_id column...")
    try:
        c.execute("ALTER TABLE sessions ADD COLUMN map_id INTEGER")
        print("✅ Column added successfully")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("⚠️  Column already exists, proceeding to backfill...")
        else:
            raise
    
    # Backfill for Oct 28 and Oct 30 ONLY (clean data)
    dates = ['2025-10-28', '2025-10-30']
    
    for date in dates:
        print(f"\n{'='*60}")
        print(f"Processing {date}...")
        print(f"{'='*60}")
        
        # Get all rounds for this date
        c.execute("""
            SELECT id, map_name, round_number
            FROM rounds
            WHERE round_date LIKE ?
            ORDER BY id
        """, (f"{date}%",))
        
        rounds = c.fetchall()
        print(f"Found {len(rounds)} rounds")
        
        # Assign map_ids
        map_counter = 0
        current_map = None
        updates = []
        
        for round_id, map_name, round_num in rounds:
            # New map starts when:
            # 1. First round OR
            # 2. Map name changes OR
            # 3. We see R1 (new map started)
            if (current_map is None or 
                current_map['map_name'] != map_name or 
                round_num == 1):
                
                map_counter += 1
                current_map = {
                    'map_name': map_name,
                    'map_id': map_counter
                }
            
            # Assign this round to the current map_id
            updates.append((current_map['map_id'], round_id))
            
            status = "✅" if round_num == 1 else "  "
            print(f"{status} Round {round_id}: {map_name:<20} R{round_num} → map_id={current_map['map_id']}")
        
        # Execute updates
        print(f"\nUpdating {len(updates)} rounds...")
        c.executemany("UPDATE rounds SET map_id = ? WHERE id = ?", updates)
        
        print(f"✅ {date}: Assigned {map_counter} map_ids to {len(updates)} rounds")
    
    conn.commit()
    
    # Verify results
    print(f"\n{'='*60}")
    print("VERIFICATION:")
    print(f"{'='*60}\n")
    
    for date in dates:
        c.execute("""
            SELECT map_id, map_name, 
                   COUNT(*) as rounds,
                   GROUP_CONCAT(round_number) as round_nums
            FROM rounds
            WHERE round_date LIKE ?
            GROUP BY map_id, map_name
            ORDER BY map_id
        """, (f"{date}%",))
        
        results = c.fetchall()
        print(f"📅 {date}:")
        
        for map_id, map_name, rounds, round_nums in results:
            rounds_list = round_nums.split(',')
            status = "✅" if len(rounds_list) == 2 and '1' in rounds_list and '2' in rounds_list else "⚠️ "
            print(f"  {status} Map {map_id}: {map_name:<20} (rounds: {round_nums})")
        
        print()
    
    conn.close()
    print("\n✅ Done! map_id column added and backfilled for Oct 28 and Oct 30")


if __name__ == "__main__":
    add_map_id_column()
