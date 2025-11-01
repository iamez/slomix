#!/usr/bin/env python3
"""
Validate that all SQL column references in bot code match actual database schema
"""
import re
import sqlite3


def get_actual_columns():
    """Get actual columns from database"""
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()

    cursor.execute('PRAGMA table_info(player_comprehensive_stats)')
    columns = cursor.fetchall()
    conn.close()

    # Return set of column names
    return {col[1] for col in columns}


def find_column_references():
    """Find all p.columnname references in bot code"""
    with open('bot/ultimate_bot.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Find patterns like p.column_name or SUM(p.column_name) in SQL queries
    # Exclude .items() which is a Python dictionary method
    pattern = r'p\.([a-z_]+)'
    matches = re.findall(pattern, content)

    # Filter out Python methods
    python_methods = {'items', 'keys', 'values', 'get', 'pop', 'update'}
    matches = [m for m in matches if m not in python_methods]

    return set(matches)


def main():
    print("=" * 60)
    print("COLUMN VALIDATION CHECK")
    print("=" * 60)

    actual_cols = get_actual_columns()
    referenced_cols = find_column_references()

    print(f"\n✅ Actual columns in database: {len(actual_cols)}")
    print(f"🔍 Referenced columns in bot code: {len(referenced_cols)}")

    # Find invalid references
    invalid_refs = referenced_cols - actual_cols

    if invalid_refs:
        print(f"\n❌ INVALID COLUMN REFERENCES FOUND: {len(invalid_refs)}")
        for col in sorted(invalid_refs):
            print(f"   - p.{col} (DOES NOT EXIST)")
    else:
        print("\n✅ ALL COLUMN REFERENCES ARE VALID!")

    # Show all referenced columns
    print(f"\n📋 All referenced columns:")
    for col in sorted(referenced_cols):
        status = "✅" if col in actual_cols else "❌"
        print(f"   {status} p.{col}")

    return 0 if not invalid_refs else 1


if __name__ == "__main__":
    exit(main())
