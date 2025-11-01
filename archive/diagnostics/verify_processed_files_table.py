#!/usr/bin/env python3
"""Verify processed_files table structure"""

import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Get table schema
cursor.execute("""
    SELECT sql FROM sqlite_master 
    WHERE type='table' AND name='processed_files'
""")
result = cursor.fetchone()

if result:
    print("✅ processed_files table exists!\n")
    print("Schema:")
    print(result[0])
    print()
    
    # Get indexes
    cursor.execute("""
        SELECT sql FROM sqlite_master 
        WHERE type='index' AND tbl_name='processed_files'
    """)
    indexes = cursor.fetchall()
    
    if indexes:
        print("\nIndexes:")
        for idx in indexes:
            if idx[0]:  # Skip auto-created indexes
                print(f"  {idx[0]}")
    
    # Count rows
    cursor.execute("SELECT COUNT(*) FROM processed_files")
    count = cursor.fetchone()[0]
    print(f"\n📊 Current rows in table: {count}")
    
    if count > 0:
        print("\nSample rows:")
        cursor.execute("""
            SELECT filename, success, processed_at 
            FROM processed_files 
            LIMIT 5
        """)
        for row in cursor.fetchall():
            print(f"  - {row[0]} (success={row[1]}, processed={row[2]})")
else:
    print("❌ processed_files table does not exist!")

conn.close()
