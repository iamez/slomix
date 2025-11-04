#!/usr/bin/env python3
"""
NUCLEAR OPTION - Complete Database Reset and Fresh Import
==========================================================

This script will:
1. Backup existing database (just in case)
2. Delete the database
3. Recreate fresh schema
4. Re-import ALL stat files with corrected parser
5. Validate the results

USE WITH CAUTION - This will DELETE all existing data!
"""

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, 'bot')

def backup_database():
    """Backup existing database before nuking"""
    db_path = 'bot/etlegacy_production.db'
    
    if not os.path.exists(db_path):
        print("❌ No database found at bot/etlegacy_production.db")
        return False
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f'bot/etlegacy_production_BACKUP_{timestamp}.db'
    
    print(f"📦 Backing up database to: {backup_path}")
    shutil.copy2(db_path, backup_path)
    print(f"✅ Backup created: {os.path.getsize(backup_path) / 1024 / 1024:.2f} MB")
    
    return True

def nuke_database():
    """Delete the database file"""
    db_path = 'bot/etlegacy_production.db'
    
    if os.path.exists(db_path):
        print(f"💣 Nuking database: {db_path}")
        os.remove(db_path)
        print("✅ Database deleted")
    else:
        print("ℹ️ No database to delete")
    
    return True

def get_schema_file():
    """Find the schema file"""
    schema_files = [
        'bot/schema.sql',
        'schema.sql',
        'database_schema.sql',
        'fresh_schema.sql'
    ]
    
    for schema_file in schema_files:
        if os.path.exists(schema_file):
            return schema_file
    
    return None

def create_fresh_database():
    """Create new database with fresh schema"""
    db_path = 'bot/etlegacy_production.db'
    schema_file = get_schema_file()
    
    if not schema_file:
        print("❌ Could not find schema file!")
        print("   Looking for: schema.sql, bot/schema.sql, database_schema.sql")
        return False
    
    print(f"📋 Using schema: {schema_file}")
    print(f"🏗️ Creating fresh database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    
    with open(schema_file, 'r') as f:
        schema_sql = f.read()
    
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()
    
    print("✅ Fresh database created")
    return True

def count_stat_files():
    """Count how many stat files we have"""
    stats_dir = Path('bot/local_stats')
    
    if not stats_dir.exists():
        print("❌ local_stats directory not found!")
        return 0
    
    txt_files = list(stats_dir.glob('*.txt'))
    r1_files = [f for f in txt_files if '-round-1.txt' in f.name]
    r2_files = [f for f in txt_files if '-round-2.txt' in f.name]
    
    print(f"\n📊 Stats Files Found:")
    print(f"   Total: {len(txt_files)} files")
    print(f"   Round 1: {len(r1_files)} files")
    print(f"   Round 2: {len(r2_files)} files")
    
    return len(txt_files)

def main():
    print("=" * 80)
    print("🚨 NUCLEAR OPTION - COMPLETE DATABASE RESET")
    print("=" * 80)
    print()
    print("⚠️  WARNING: This will DELETE your entire database and recreate from scratch!")
    print()
    
    # Show what will be done
    print("Steps:")
    print("  1. Backup existing database")
    print("  2. DELETE database file")
    print("  3. Create fresh database from schema")
    print("  4. Ready for fresh import")
    print()
    
    # Count files
    file_count = count_stat_files()
    if file_count == 0:
        print("❌ No stat files found! Cannot proceed.")
        return
    
    # Get confirmation
    print("=" * 80)
    response = input("Type 'NUKE' to proceed with database reset: ")
    
    if response != 'NUKE':
        print("❌ Aborted. No changes made.")
        return
    
    print()
    print("🚀 Starting nuclear reset...")
    print()
    
    # Step 1: Backup
    if not backup_database():
        print("⚠️ No backup created (database doesn't exist yet?)")
    
    # Step 2: Nuke
    if not nuke_database():
        print("❌ Failed to delete database")
        return
    
    # Step 3: Create fresh
    if not create_fresh_database():
        print("❌ Failed to create fresh database")
        return
    
    print()
    print("=" * 80)
    print("✅ DATABASE RESET COMPLETE!")
    print("=" * 80)
    print()
    print("📝 Next Steps:")
    print()
    print("  1. Import all stat files:")
    print("     python tools/fresh_bulk_import.py")
    print()
    print("  2. Or use your preferred import method")
    print()
    print("  3. After import, run validation:")
    print("     python tools/comprehensive_all_fields_validation.py --limit 50")
    print()
    print("  4. Generate technical report:")
    print("     python tools/detailed_technical_validator.py")
    print()
    print("  5. View results:")
    print("     - COMPREHENSIVE_VALIDATION_REPORT.html")
    print("     - TECHNICAL_MISMATCH_DETAILS.html")
    print()
    print(f"💾 Backup saved in case you need to restore")
    print()

if __name__ == '__main__':
    main()
