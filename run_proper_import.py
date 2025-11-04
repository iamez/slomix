#!/usr/bin/env python3
"""
Run full import of all 2025 files into bot/etlegacy_production.db
"""
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database_manager import DatabaseManager

print("=" * 80)
print("PROPER FIX: Full Import of All 2025 Files")
print("=" * 80)

# Initialize database manager (will use bot/etlegacy_production.db)
print("\n1️⃣  Initializing database manager...")
manager = DatabaseManager()

# Validate current state
print("\n2️⃣  Checking current database state...")
results = manager.validate_database()

print(f"\nCurrent state:")
print(f"   Sessions: {results.get('rounds', 0):,}")
print(f"   Players:  {results.get('players', 0):,}")
print(f"   Weapons:  {results.get('weapons', 0):,}")

if results.get('rounds', 0) > 100:
    print("\n⚠️  Database already has significant data!")
    response = input("Continue with import anyway? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Aborted")
        sys.exit(0)

# Run full import
print("\n3️⃣  Starting full import of ALL 2025 files...")
print("   This will take a few minutes...")
print("   Files already processed will be skipped automatically.\n")

success = manager.import_all_files(year_filter=2025)

if success:
    print("\n✅ Import completed successfully!")
    
    # Final validation
    print("\n4️⃣  Final validation...")
    final_results = manager.validate_database()
    
    print(f"\n📊 Final Database State:")
    print(f"   Sessions:        {final_results.get('rounds', 0):,}")
    print(f"   Player Stats:    {final_results.get('players', 0):,}")
    print(f"   Weapon Stats:    {final_results.get('weapons', 0):,}")
    print(f"   Processed Files: {final_results.get('processed_files', 0):,}")
    print(f"   Date Range:      {final_results.get('date_range', ('N/A', 'N/A'))[0]} to {final_results.get('date_range', ('N/A', 'N/A'))[1]}")
    
    if final_results.get('rounds', 0) > 100:
        print("\n🎉 SUCCESS! Bot database is now properly populated!")
    else:
        print("\n⚠️  WARNING: Database still has low session count!")
else:
    print("\n❌ Import failed! Check database_manager.log for details")

print("\n" + "=" * 80)
