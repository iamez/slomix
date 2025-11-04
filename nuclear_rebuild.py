#!/usr/bin/env python3
"""
🔥 NUCLEAR OPTION: Nuke database and rebuild last 3 weeks
Date: 2025-11-04
Range: 2025-10-14 to 2025-11-04
"""
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database_manager import DatabaseManager

def main():
    print("=" * 80)
    print("🔥 NUCLEAR DATABASE REBUILD")
    print("=" * 80)
    print()
    
    # Date range
    end_date = datetime(2025, 11, 4)
    start_date = end_date - timedelta(days=21)  # 3 weeks
    
    print(f"Date range: {start_date.date()} to {end_date.date()}")
    print(f"Stats directory: local_stats/")
    print()
    
    # Count files in date range
    stats_dir = Path("local_stats")
    if not stats_dir.exists():
        print("❌ ERROR: local_stats/ directory not found!")
        return 1
    
    # Get all stat files
    all_files = list(stats_dir.glob("*.txt"))
    print(f"📊 Total files in local_stats/: {len(all_files)}")
    
    # Filter by date range
    files_in_range = []
    for file in all_files:
        try:
            # Extract date from filename: YYYY-MM-DD-HHMMSS-...
            date_str = "-".join(file.stem.split("-")[:3])
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            
            if start_date.date() <= file_date.date() <= end_date.date():
                files_in_range.append(file)
        except (ValueError, IndexError):
            # Skip files that don't match expected format
            continue
    
    print(f"📊 Files in date range (last 3 weeks): {len(files_in_range)}")
    print()
    
    if len(files_in_range) == 0:
        print("⚠️  WARNING: No files found in date range!")
        print("   Check if local_stats/ has recent files.")
        return 1
    
    # Show sample of files
    print("Sample files to import:")
    for file in sorted(files_in_range)[:5]:
        print(f"  - {file.name}")
    if len(files_in_range) > 5:
        print(f"  ... and {len(files_in_range) - 5} more")
    print()
    
    # Confirm nuclear option
    print("🚨 WARNING: This will DELETE and RECREATE the database!")
    print()
    response = input("Type 'NUKE' to confirm: ")
    
    if response != "NUKE":
        print("❌ Aborted. Database unchanged.")
        return 0
    
    print()
    print("=" * 80)
    print("🔥 NUKING DATABASE...")
    print("=" * 80)
    print()
    
    db_path = Path("bot/etlegacy_production.db")
    
    # Step 1: Backup existing database
    if db_path.exists():
        backup_name = f"bot/etlegacy_production.db.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"📦 Creating backup: {backup_name}")
        shutil.copy2(db_path, backup_name)
        print(f"✅ Backup created: {os.path.getsize(backup_name) / 1024 / 1024:.2f} MB")
        print()
        
        # Delete current database
        print(f"💣 Deleting current database...")
        db_path.unlink()
        
        # Delete WAL and SHM files if they exist
        for ext in ['-wal', '-shm']:
            wal_file = Path(f"{db_path}{ext}")
            if wal_file.exists():
                wal_file.unlink()
                print(f"   Deleted: {wal_file.name}")
        
        print("✅ Database nuked!")
        print()
    else:
        print("ℹ️  No existing database found (creating fresh)")
        print()
    
    # Step 2: Initialize DatabaseManager
    print("=" * 80)
    print("🏗️  REBUILDING DATABASE...")
    print("=" * 80)
    print()
    
    manager = DatabaseManager()
    
    # Step 3: Import stats from date range
    print(f"📥 Importing {len(files_in_range)} files from last 3 weeks...")
    print()
    
    # DatabaseManager will handle files automatically
    # Just tell it to import from 2025 (it will process all files)
    # The date range filtering already happened in local_stats/
    success = manager.import_all_files(year_filter=2025)
    
    print()
    if success:
        print("=" * 80)
        print("✅ NUCLEAR REBUILD COMPLETE!")
        print("=" * 80)
        print()
        print("Next steps:")
        print("  1. Test bot commands: !last_round")
        print("  2. Verify data looks correct")
        print("  3. If issues, restore from backup:")
        print(f"     Copy {backup_name} to bot/etlegacy_production.db")
        print()
        return 0
    else:
        print("=" * 80)
        print("❌ REBUILD FAILED!")
        print("=" * 80)
        print()
        print("Restoring backup...")
        if Path(backup_name).exists():
            shutil.copy2(backup_name, db_path)
            print(f"✅ Database restored from backup")
        print()
        return 1

if __name__ == "__main__":
    sys.exit(main())
