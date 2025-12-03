"""
Fix map_id for midnight-spanning sessions.

When a match spans midnight (R1 on Nov 1, R2 on Nov 2), they get different dates
but should share the same map_id since they're ONE session.

Strategy:
1. Find R2 sessions that started shortly after midnight (00:00-00:30)
2. Look for matching R1 from previous day (23:30-23:59)
3. Same map name and close timing = same session
4. Update R2's map_id to match R1's map_id
"""

import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Find potential midnight-spanning Round 2s (started 00:00-00:30)
cursor.execute("""
    SELECT id, round_date, map_name, round_number, map_id
    FROM rounds
    WHERE round_number = 2
    AND substr(round_date, 12, 2) = '00'  -- Hour is 00
    AND CAST(substr(round_date, 12, 6) AS INTEGER) <= 3000  -- Time <= 00:30:00
    ORDER BY round_date
""")

r2_midnight_sessions = cursor.fetchall()

print(f"Found {len(r2_midnight_sessions)} Round 2 sessions starting shortly after midnight")
print()

fixed_count = 0

for r2_id, r2_date, r2_map, r2_round, r2_map_id in r2_midnight_sessions:
    print(f"Checking R2: ID {r2_id} - {r2_date} - {r2_map} (map_id={r2_map_id})")
    
    # Extract date from round_date (format: YYYY-MM-DD-HHMMSS)
    r2_date_only = r2_date[:10]  # YYYY-MM-DD
    r2_datetime = datetime.strptime(r2_date[:17], '%Y-%m-%d-%H%M%S')
    
    # Look for R1 on previous day, same map, late timing (23:00-23:59)
    prev_date_obj = r2_datetime - timedelta(days=1)
    prev_date = prev_date_obj.strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT id, round_date, map_name, round_number, map_id
        FROM rounds
        WHERE round_number = 1
        AND map_name = ?
        AND round_date LIKE ?
        AND substr(round_date, 12, 2) = '23'  -- Hour is 23
        ORDER BY round_date DESC
        LIMIT 1
    """, (r2_map, f"{prev_date}%"))
    
    r1_match = cursor.fetchone()
    
    if r1_match:
        r1_id, r1_date, r1_map, r1_round, r1_map_id = r1_match
        
        # Check timing - R1 should be within ~30 minutes before R2
        r1_datetime = datetime.strptime(r1_date[:17], '%Y-%m-%d-%H%M%S')
        time_diff = (r2_datetime - r1_datetime).total_seconds() / 60  # minutes
        
        if 0 < time_diff <= 30:  # R2 should be 0-30 minutes after R1
            print(f"  ✓ Found matching R1: ID {r1_id} - {r1_date} (map_id={r1_map_id})")
            print(f"    Time difference: {time_diff:.1f} minutes")
            
            if r1_map_id != r2_map_id:
                print(f"    → Updating R2 map_id from {r2_map_id} to {r1_map_id}")
                cursor.execute("""
                    UPDATE rounds
                    SET map_id = ?
                    WHERE id = ?
                """, (r1_map_id, r2_id))
                fixed_count += 1
            else:
                print("    → map_ids already match, no update needed")
        else:
            print(f"  ✗ Time difference too large: {time_diff:.1f} minutes")
    else:
        print(f"  ✗ No matching R1 found on {prev_date}")
    
    print()

conn.commit()
conn.close()

print("="*70)
print(f"Fixed {fixed_count} midnight-spanning sessions")
