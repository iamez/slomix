#!/usr/bin/env python3
"""
PROPER FIX: Clear processed_files table and re-import all data
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from database_manager import DatabaseManager

print("=" * 80)
print("PROPER FIX: Clear processed_files and Re-import")
print("=" * 80)

# Step 1: Clear processed_files table
print("\n1️⃣  Clearing processed_files table...")
db_path = "bot/etlegacy_production.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM processed_files")
before_count = cursor.fetchone()[0]
print(f"   Before: {before_count:,} entries")

cursor.execute("DELETE FROM processed_files")
conn.commit()

cursor.execute("SELECT COUNT(*) FROM processed_files")
after_count = cursor.fetchone()[0]
print(f"   After:  {after_count:,} entries")
print(f"   ✅ Cleared {before_count:,} entries")

conn.close()

# Step 2: Run full import
print("\n2️⃣  Starting full import of ALL 2025 files...")
print("   This will take 2-3 minutes...")
print("   (No files will be skipped now)\n")

manager = DatabaseManager()
success = manager.import_all_files(year_filter=2025)

if success:
    print("\n3️⃣  Final validation...")
    results = manager.validate_database()
    
    print(f"\n📊 Final Database State:")
    print(f"   Sessions:        {results.get('rounds', 0):,}")
    print(f"   Player Stats:    {results.get('players', 0):,}")
    print(f"   Weapon Stats:    {results.get('weapons', 0):,}")
    print(f"   Processed Files: {results.get('processed_files', 0):,}")
    print(f"   Date Range:      {results.get('date_range', ('N/A', 'N/A'))[0]} to {results.get('date_range', ('N/A', 'N/A'))[1]}")
    
    if results.get('rounds', 0) > 100:
        print("\n🎉 SUCCESS! Bot database now has REAL data!")
    else:
        print(f"\n⚠️  WARNING: Only {results.get('rounds', 0)} sessions imported")
        print("   Expected 150-200+ sessions for 2025 data")
else:
    print("\n❌ Import failed!")

print("\n" + "=" * 80)
