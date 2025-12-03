"""
Investigate why 2 files weren't imported despite being available
"""
import sqlite3
import os
from datetime import datetime

# The missing files
missing_files = [
    '2025-11-04-225627-etl_frostbite-round-1.txt',
    '2025-11-04-224353-te_escape2-round-2.txt'
]

print("=" * 80)
print("IMPORT FAILURE INVESTIGATION")
print("=" * 80)

# 1. Check if files exist locally
print("\n[1] Checking if files exist in local_stats/...")
for filename in missing_files:
    filepath = os.path.join('local_stats', filename)
    exists = os.path.exists(filepath)
    if exists:
        size = os.path.getsize(filepath)
        mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
        print(f"  ✅ {filename}")
        print(f"     Size: {size} bytes, Modified: {mtime}")
    else:
        print(f"  ❌ {filename} - NOT FOUND")

# 2. Check processed_files table (tracks what's been imported)
print("\n[2] Checking processed_files table (import tracking)...")
conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Check if processed_files table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processed_files'")
if not cursor.fetchone():
    print("  ⚠️  processed_files table doesn't exist - no import tracking!")
else:
    for filename in missing_files:
        cursor.execute("SELECT * FROM processed_files WHERE filename = ?", (filename,))
        result = cursor.fetchone()
        
        if result:
            print(f"  ✅ {filename} - MARKED AS PROCESSED")
            print(f"     Import date: {result[2] if len(result) > 2 else 'unknown'}")
        else:
            print(f"  ❌ {filename} - NOT in processed_files (never imported)")

# 3. Check if there are ANY records for these specific rounds
print("\n[3] Checking if round data exists in player_comprehensive_stats...")

# etl_frostbite round 1
cursor.execute("""
    SELECT COUNT(*), MIN(created_at), MAX(created_at)
    FROM player_comprehensive_stats 
    WHERE round_date = '2025-11-04' 
    AND map_name = 'etl_frostbite' 
    AND round_number = 1
""")
frostbite_r1 = cursor.fetchone()
print("\n  etl_frostbite Round 1:")
print(f"    Records: {frostbite_r1[0]}")
if frostbite_r1[0] > 0:
    print(f"    First imported: {frostbite_r1[1]}")
    print(f"    Last imported: {frostbite_r1[2]}")

# etl_frostbite round 2 (for comparison - we know this one exists)
cursor.execute("""
    SELECT COUNT(*), MIN(created_at), MAX(created_at)
    FROM player_comprehensive_stats 
    WHERE round_date = '2025-11-04' 
    AND map_name = 'etl_frostbite' 
    AND round_number = 2
""")
frostbite_r2 = cursor.fetchone()
print("\n  etl_frostbite Round 2 (for comparison):")
print(f"    Records: {frostbite_r2[0]}")
if frostbite_r2[0] > 0:
    print(f"    First imported: {frostbite_r2[1]}")
    print(f"    Last imported: {frostbite_r2[2]}")

# te_escape2 round 2
cursor.execute("""
    SELECT COUNT(*), MIN(created_at), MAX(created_at)
    FROM player_comprehensive_stats 
    WHERE round_date = '2025-11-04' 
    AND map_name = 'te_escape2' 
    AND round_number = 2
""")
escape_r2 = cursor.fetchone()
print("\n  te_escape2 Round 2:")
print(f"    Records: {escape_r2[0]}")
if escape_r2[0] > 0:
    print(f"    First imported: {escape_r2[1]}")
    print(f"    Last imported: {escape_r2[2]}")

# te_escape2 round 1 (we know this exists)
cursor.execute("""
    SELECT COUNT(*), MIN(created_at), MAX(created_at)
    FROM player_comprehensive_stats 
    WHERE round_date = '2025-11-04' 
    AND map_name = 'te_escape2' 
    AND round_number = 1
""")
escape_r1 = cursor.fetchone()
print("\n  te_escape2 Round 1 (for comparison):")
print(f"    Records: {escape_r1[0]}")
if escape_r1[0] > 0:
    print(f"    First imported: {escape_r1[1]}")
    print(f"    Last imported: {escape_r1[2]}")

# 4. Check for duplicate te_escape2 round 2 entries (maybe there are multiple files?)
print("\n[4] Checking for duplicate files in local_stats...")
for prefix in ['2025-11-04', '2025-11-04']:
    # Look for all te_escape2 round 2 files
    import glob
    files = glob.glob('local_stats/*te_escape2-round-2.txt')
    if files:
        print(f"\n  te_escape2 Round 2 files found: {len(files)}")
        for f in files:
            print(f"    {os.path.basename(f)}")
    
    files = glob.glob('local_stats/*etl_frostbite-round-1.txt')
    if files:
        print(f"\n  etl_frostbite Round 1 files found: {len(files)}")
        for f in files:
            print(f"    {os.path.basename(f)}")

# 5. Check file contents to see if they're valid
print("\n[5] Checking file contents...")
for filename in missing_files:
    filepath = os.path.join('local_stats', filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.strip().split('\n')
            print(f"\n  {filename}:")
            print(f"    Lines: {len(lines)}")
            print(f"    Size: {len(content)} bytes")
            if len(lines) > 0:
                print(f"    First line: {lines[0][:80]}")
            if len(content) < 100:
                print("    ⚠️  File seems too small - might be empty/corrupt")

conn.close()

print("\n" + "=" * 80)
print("HYPOTHESIS")
print("=" * 80)
print("""
Possible reasons files weren't imported:

1. Import script skipped them (check processed_files table)
2. Files are empty or corrupted (check file size/content)
3. Parser failed on these specific files (check parser logs)
4. Duplicate detection flagged them incorrectly
5. Import was interrupted before reaching these files
6. Files were added to local_stats AFTER last import run
""")
