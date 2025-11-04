#!/usr/bin/env python3
"""
PROPER DATABASE REBUILD using database_manager.py
This is the correct way to fix the database!
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from database_manager import DatabaseManager

print("=" * 80)
print("PROPER DATABASE REBUILD - Using database_manager.py")
print("=" * 80)

print("\n⚠️  WARNING: This will DELETE ALL DATA and rebuild from scratch!")
print("   A backup will be created automatically before deletion.")
print()

# Initialize database manager
manager = DatabaseManager()

# Show current state
print("📊 Current database state:")
results = manager.validate_database()
print(f"   Sessions:        {results.get('rounds', 0):,}")
print(f"   Player Stats:    {results.get('players', 0):,}")
print(f"   Processed Files: {results.get('processed_files', 0):,}")

print("\n" + "=" * 80)
print("Starting rebuild...")
print("=" * 80)

# Use the built-in disaster recovery function
# This will:
#  1. Backup existing database
#  2. Delete old database
#  3. Create fresh schema
#  4. Import all 2025 files
success = manager.rebuild_from_scratch(year=2025, confirm=True)

if success:
    print("\n" + "=" * 80)
    print("✅ REBUILD COMPLETE!")
    print("=" * 80)
    
    # Final validation
    final = manager.validate_database()
    print(f"\n📊 Final State:")
    print(f"   Sessions:        {final.get('rounds', 0):,}")
    print(f"   Player Stats:    {final.get('players', 0):,}")
    print(f"   Weapon Stats:    {final.get('weapons', 0):,}")
    print(f"   Processed Files: {final.get('processed_files', 0):,}")
    print(f"   Date Range:      {final.get('date_range', ('N/A', 'N/A'))[0]} to {final.get('date_range', ('N/A', 'N/A'))[1]}")
    
    if final.get('rounds', 0) > 100:
        print("\n🎉 SUCCESS! Database fully populated!")
    else:
        print(f"\n⚠️  WARNING: Only {final.get('rounds', 0)} sessions - expected 150-200+")
else:
    print("\n❌ Rebuild failed! Check database_manager.log")

print("\n" + "=" * 80)
