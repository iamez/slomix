#!/usr/bin/env python3
"""
PROPER REBUILD: Use database_manager.py's built-in disaster recovery
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from database_manager import DatabaseManager

print("=" * 80)
print("🔥 PROPER REBUILD: Using Database Manager's Disaster Recovery")
print("=" * 80)
print()
print("This will:")
print("  1. Backup existing database")
print("  2. Create fresh database with correct schema")
print("  3. Import ALL 2025 files")
print("  4. Validate results")
print()
print("This is the RIGHT way to do it - using the tool we built for this!")
print("=" * 80)

# Use the database manager's built-in disaster recovery
manager = DatabaseManager()

# This will:
# - Backup the current database
# - Delete it
# - Create fresh schema
# - Import all 2025 files with proper duplicate prevention
print("\n🚀 Starting rebuild...")
success = manager.rebuild_from_scratch(year=2025, confirm=True)

if success:
    print("\n✅ Rebuild complete!")
    print("\n📊 Final validation...")
    results = manager.validate_database()
    
    if results['rounds'] > 100:
        print("\n🎉 SUCCESS! Database has real data!")
    else:
        print("\n⚠️  Database might still have issues - check the counts above")
else:
    print("\n❌ Rebuild failed - check database_manager.log for details")
