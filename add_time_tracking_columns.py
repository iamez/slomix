#!/usr/bin/env python3
"""
Add proper time tracking columns to sessions table

Current problem:
- time_limit: ambiguous (original limit for R1, or time-to-beat for R2?)
- actual_time: just stores completion time

Solution:
- original_time_limit: Map's default time limit (always from R1)
- time_to_beat: R1's completion time (used as R2's target)
- actual_time: Rename to completion_time for clarity

Header format: \\map\\legacy3\\round\\team1\\team2\\TIME_FIELD_6\\TIME_FIELD_7
- R1: field 6 = original limit (e.g., 10:00), field 7 = actual completion (e.g., 5:12)
- R2: field 6 = time to beat from R1 (e.g., 5:12), field 7 = actual completion (e.g., 4:55)
"""

import sqlite3


def add_time_columns():
    """Add new time tracking columns to sessions table"""
    
    conn = sqlite3.connect('bot/etlegacy_production.db')
    c = conn.cursor()
    
    print("Adding new time columns to sessions table...")
    print()
    
    # Add original_time_limit column
    try:
        c.execute("ALTER TABLE sessions ADD COLUMN original_time_limit TEXT")
        print("✅ Added column: original_time_limit")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("⚠️  Column original_time_limit already exists")
        else:
            raise
    
    # Add time_to_beat column
    try:
        c.execute("ALTER TABLE sessions ADD COLUMN time_to_beat TEXT")
        print("✅ Added column: time_to_beat")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("⚠️  Column time_to_beat already exists")
        else:
            raise
    
    # Add completion_time column (will eventually replace actual_time)
    try:
        c.execute("ALTER TABLE sessions ADD COLUMN completion_time TEXT")
        print("✅ Added column: completion_time")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("⚠️  Column completion_time already exists")
        else:
            raise
    
    conn.commit()
    
    # Verify the new schema
    print()
    print("="*60)
    print("Current sessions table schema:")
    print("="*60)
    
    c.execute("PRAGMA table_info(sessions)")
    for row in c.fetchall():
        col_id, name, col_type, notnull, default, pk = row
        print(f"{col_id:2}. {name:25} {col_type:10} {'NOT NULL' if notnull else ''}")
    
    conn.close()
    
    print()
    print("="*60)
    print("✅ Database schema updated successfully!")
    print("="*60)
    print()
    print("Next steps:")
    print("1. Update parser to populate these new columns")
    print("2. Backfill data from existing stat files")
    print("3. Update all queries to use new column names")


if __name__ == "__main__":
    add_time_columns()
