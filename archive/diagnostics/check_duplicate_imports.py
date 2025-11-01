#!/usr/bin/env python3
"""
Check for duplicate imports in processed_files table
"""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print("="*70)
print("CHECKING PROCESSED FILES - October 2, 2025")
print("="*70)

# Check Oct 2 files
results = c.execute('''
    SELECT filename, processed_at, success
    FROM processed_files
    WHERE filename LIKE '%2025-10-02%'
    ORDER BY filename, processed_at
''').fetchall()

print(f"\nFound {len(results)} processed file records for Oct 2:\n")

# Group by filename
from collections import defaultdict
file_counts = defaultdict(list)
for filename, proc_at, success in results:
    file_counts[filename].append((proc_at, success))

# Show duplicates
duplicates = {f: times for f, times in file_counts.items() if len(times) > 1}

if duplicates:
    print(f"⚠️  Found {len(duplicates)} files processed MULTIPLE times:\n")
    for filename, times in list(duplicates.items())[:5]:  # Show first 5
        print(f"File: {filename}")
        for i, (proc_at, success) in enumerate(times, 1):
            print(f"  Import {i}: {proc_at} | Success={success}")
        print()
else:
    print("✅ No duplicate file imports found")

# Check first file specifically
print("="*70)
print("SPECIFIC CHECK: 2025-10-02-211808-etl_adlernest-round-1.txt")
print("="*70)

specific = c.execute('''
    SELECT processed_at, success
    FROM processed_files
    WHERE filename = '2025-10-02-211808-etl_adlernest-round-1.txt'
    ORDER BY processed_at
''').fetchall()

print(f"\nImport count: {len(specific)}\n")
for i, (proc_at, success) in enumerate(specific, 1):
    print(f"Import {i}: {proc_at} | Success={success}")

# Now check sessions table for this date/map
print(f"\n{'='*70}")
print("SESSIONS TABLE - etl_adlernest round 1 on Oct 2")
print("="*70)

sessions = c.execute('''
    SELECT id, session_date, map_name, round_number, created_at
    FROM sessions
    WHERE session_date = '2025-10-02'
      AND map_name = 'etl_adlernest'
      AND round_number = 1
    ORDER BY id
''').fetchall()

print(f"\nFound {len(sessions)} session records:\n")
for sess_id, date, map_name, round_num, created_at in sessions:
    # Count players
    player_count = c.execute('''
        SELECT COUNT(*)
        FROM player_comprehensive_stats
        WHERE session_id = ?
    ''', (sess_id,)).fetchone()[0]
    
    print(f"Session {sess_id}: {date} {map_name} R{round_num}")
    print(f"  Created: {created_at}")
    print(f"  Players: {player_count}")

conn.close()
