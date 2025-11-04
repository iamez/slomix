#!/usr/bin/env python3
"""
PROPER FIX: Use database_manager's rebuild_from_scratch()
This is THE correct way to fix the database issue.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from database_manager import DatabaseManager

print("=" * 80)
print("DATABASE REBUILD - Using database_manager.rebuild_from_scratch()")
print("=" * 80)

print("\n⚠️  This will:")
print("   1. Backup current bot/etlegacy_production.db")
print("   2. Delete the database")
print("   3. Create fresh schema")
print("   4. Import ALL 2025 files in proper order")
print("   5. Process Round 1 before Round 2 for each map")
print()

response = input("Type 'YES' to proceed: ")

if response != 'YES':
    print("❌ Aborted")
    sys.exit(0)

print("\n🚀 Starting rebuild...")
print("   This will take approximately 5-10 minutes")
print("   Files will be processed in chronological order")
print()

manager = DatabaseManager()
success = manager.rebuild_from_scratch(year=2025, confirm=True)

if success:
    print("\n✅ Rebuild completed!")
    print("\n📊 Final validation...")
    results = manager.validate_database()
    
    print(f"\n🎉 SUCCESS! Database is now properly populated:")
    print(f"   Sessions:        {results.get('rounds', 0):,}")
    print(f"   Player Stats:    {results.get('players', 0):,}")
    print(f"   Weapon Stats:    {results.get('weapons', 0):,}")
    print(f"   Processed Files: {results.get('processed_files', 0):,}")
    print(f"   Date Range:      {results.get('date_range', ('N/A', 'N/A'))[0]} to {results.get('date_range', ('N/A', 'N/A'))[1]}")
else:
    print("\n❌ Rebuild failed! Check database_manager.log for details")

print("\n" + "=" * 80)
