#!/usr/bin/env python3
"""Add time_played_minutes column to database"""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print("🔧 Adding time_played_minutes column...")
print("=" * 80)

try:
    c.execute(
        'ALTER TABLE player_comprehensive_stats ADD COLUMN time_played_minutes REAL DEFAULT 0.0'
    )
    conn.commit()
    print("✅ Column added successfully!\n")

    # Verify column was added
    c.execute('PRAGMA table_info(player_comprehensive_stats)')
    cols = c.fetchall()

    print("📋 Updated table schema:")
    print("-" * 80)
    for i, col in enumerate(cols, 1):
        col_name = col[1]
        col_type = col[2]
        not_null = "NOT NULL" if col[3] else "NULL"
        default = col[4] if col[4] else "None"
        print(f"  {i:2}. {col_name:30} {col_type:10} {not_null:8} Default: {default}")

    print("\n" + "=" * 80)
    print("✅ Schema update complete!")

except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("⚠️  Column already exists (that's OK!)")
    else:
        print(f"❌ Error: {e}")

conn.close()
