#!/usr/bin/env python3
"""Check bot database processed_files for October 2"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

print("="*70)
print("BOT DATABASE - PROCESSED FILES CHECK")
print("="*70)

# Check if processed_files table exists
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"\nTables in bot database: {[t[0] for t in tables]}\n")

if 'processed_files' in [t[0] for t in tables]:
    # Check October 2 adlernest file
    target_file = '2025-10-02-211808-etl_adlernest-round-1.txt'
    
    records = c.execute('''
        SELECT filename, processed_at, success, error_message
        FROM processed_files
        WHERE filename = ?
        ORDER BY processed_at
    ''', (target_file,)).fetchall()
    
    print(f"Records for {target_file}:")
    print(f"  Import count: {len(records)}\n")
    
    for i, (filename, proc_at, success, error_msg) in enumerate(records, 1):
        print(f"  Import {i}:")
        print(f"    Time: {proc_at}")
        print(f"    Success: {success}")
        if error_msg:
            print(f"    Error: {error_msg}")
    
    # Check all Oct 2 files
    print(f"\n{'='*70}")
    print("ALL OCTOBER 2 FILES")
    print("="*70)
    
    oct2_files = c.execute('''
        SELECT filename, COUNT(*) as import_count
        FROM processed_files
        WHERE filename LIKE '%2025-10-02%'
        GROUP BY filename
        HAVING COUNT(*) > 1
        ORDER BY import_count DESC
    ''').fetchall()
    
    if oct2_files:
        print(f"\nFound {len(oct2_files)} Oct 2 files imported MULTIPLE times:")
        for filename, count in oct2_files[:10]:  # Show first 10
            print(f"  {filename}: {count} times")
    else:
        print("\n✅ No Oct 2 files imported multiple times")
        
        # Show all Oct 2 files
        all_oct2 = c.execute('''
            SELECT filename, processed_at
            FROM processed_files
            WHERE filename LIKE '%2025-10-02%'
            ORDER BY filename
        ''').fetchall()
        print(f"\nAll Oct 2 files (imported once each): {len(all_oct2)} files")
else:
    print("❌ processed_files table does NOT exist in bot database!")
    print("This explains the duplication - no tracking of imports!")

conn.close()
