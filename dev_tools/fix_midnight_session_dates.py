"""
Fix: Move midnight-spanning R2 session to same date as its R1 session.

When a match spans midnight (R1 on Nov 1 23:55, R2 on Nov 2 00:06),
the R2 should use the same date as R1 for proper grouping.
"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("Finding midnight-spanning sessions to fix:")
print("="*70)

# Find R2 sessions that started shortly after midnight
cursor.execute("""
    SELECT s2.id, s2.round_date, s2.map_name, s2.map_id,
           s1.id as r1_id, s1.round_date as r1_date
    FROM rounds s2
    JOIN rounds s1 ON s1.map_id = s2.map_id AND s1.round_number = 1
    WHERE s2.round_number = 2
    AND SUBSTR(s2.round_date, 12, 2) = '00'  -- R2 hour is 00
    AND CAST(SUBSTR(s2.round_date, 12, 6) AS INTEGER) <= 3000  -- R2 time <= 00:30:00
    AND SUBSTR(s1.round_date, 12, 2) = '23'  -- R1 hour is 23
    AND SUBSTR(s1.round_date, 1, 10) != SUBSTR(s2.round_date, 1, 10)  -- Different dates
""")

to_fix = cursor.fetchall()

print(f"Found {len(to_fix)} midnight-spanning R2 sessions:\n")

for r2_id, r2_date, map_name, map_id, r1_id, r1_date in to_fix:
    print(f"Session to fix:")
    print(f"  R1 (ID {r1_id}): {r1_date} - {map_name}")
    print(f"  R2 (ID {r2_id}): {r2_date} - {map_name}")
    
    # Extract the date part from R1 (first 10 chars: YYYY-MM-DD)
    r1_date_part = r1_date[:10]
    
    # Build new R2 round_date: R1's date + R2's time
    r2_time_part = r2_date[10:]  # Everything after the date
    new_r2_date = r1_date_part + r2_time_part
    
    print(f"  New R2 date: {new_r2_date}")
    print(f"  (Grouping R2 with R1's date for proper session grouping)")
    
    # Update the round_date
    cursor.execute("""
        UPDATE rounds
        SET round_date = ?
        WHERE id = ?
    """, (new_r2_date, r2_id))
    
    print(f"  ✅ Updated\n")

conn.commit()
conn.close()

print("="*70)
print(f"Fixed {len(to_fix)} midnight-spanning sessions")
print("\nNow !last_round will correctly show only the Nov 2 evening session")
print("(The midnight match will be grouped with Nov 1)")
