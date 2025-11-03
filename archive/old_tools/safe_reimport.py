#!/usr/bin/env python3
"""
Safe Database Re-import Tool
Handles re-importing stats files without creating duplicates

This script provides TWO safe re-import options:
1. Clean slate (delete old data, fresh start)
2. Incremental (only import new files)
"""

import sqlite3
import logging
from pathlib import Path
from dev.bulk_import_stats import BulkStatsImporter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SafeReimporter:
    """Safe re-import with duplicate prevention"""
    
    def __init__(self, db_path: str = "bot/etlegacy_production.db"):
        self.db_path = db_path
        
    def check_existing_data(self):
        """Check what data exists in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check sessions
            cursor.execute("SELECT COUNT(*) FROM sessions")
            session_count = cursor.fetchone()[0]
            
            # Check players
            cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
            player_count = cursor.fetchone()[0]
            
            # Check processed files
            cursor.execute("SELECT COUNT(*) FROM processed_files WHERE success = 1")
            processed_count = cursor.fetchone()[0]
            
            # Date range
            cursor.execute("SELECT MIN(session_date), MAX(session_date) FROM sessions")
            date_range = cursor.fetchone()
            
            conn.close()
            
            return {
                'sessions': session_count,
                'players': player_count,
                'processed_files': processed_count,
                'date_range': date_range
            }
        except sqlite3.Error as e:
            logger.error(f"Error checking database: {e}")
            return None
    
    def option_1_clean_slate(self, stats_dir: str, year: int = 2025):
        """
        Option 1: Clean Slate Re-import
        
        DELETES all existing data and re-imports from scratch.
        Use this when you want to fix corrupted data.
        
        ⚠️ WARNING: This DELETES all stats data!
        """
        logger.info("=" * 60)
        logger.info("OPTION 1: CLEAN SLATE RE-IMPORT")
        logger.info("=" * 60)
        
        # Check existing data
        existing = self.check_existing_data()
        if existing:
            logger.info(f"\n📊 Current Database Stats:")
            logger.info(f"   Sessions: {existing['sessions']:,}")
            logger.info(f"   Players: {existing['players']:,}")
            logger.info(f"   Processed Files: {existing['processed_files']:,}")
            logger.info(f"   Date Range: {existing['date_range'][0]} to {existing['date_range'][1]}")
        
        # Confirm deletion
        logger.warning(f"\n⚠️  WARNING: This will DELETE all existing data!")
        response = input("\nType 'DELETE ALL DATA' to confirm: ")
        
        if response != "DELETE ALL DATA":
            logger.info("❌ Aborted - data preserved")
            return False
        
        logger.info("\n🗑️  Deleting existing data...")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delete in correct order (respect foreign keys)
            cursor.execute("DELETE FROM weapon_comprehensive_stats")
            weapons_deleted = cursor.rowcount
            logger.info(f"   Deleted {weapons_deleted:,} weapon rows")
            
            cursor.execute("DELETE FROM player_comprehensive_stats")
            players_deleted = cursor.rowcount
            logger.info(f"   Deleted {players_deleted:,} player rows")
            
            cursor.execute("DELETE FROM sessions")
            sessions_deleted = cursor.rowcount
            logger.info(f"   Deleted {sessions_deleted:,} session rows")
            
            cursor.execute("DELETE FROM processed_files")
            files_deleted = cursor.rowcount
            logger.info(f"   Deleted {files_deleted:,} processed file records")
            
            conn.commit()
            conn.close()
            
            logger.info("✅ Database cleaned!")
            
        except sqlite3.Error as e:
            logger.error(f"❌ Failed to clean database: {e}")
            return False
        
        # Now do fresh import
        logger.info(f"\n🔄 Starting fresh import from {stats_dir}...")
        logger.info(f"   Year filter: {year}")
        
        importer = BulkStatsImporter(self.db_path, stats_dir=stats_dir)
        success = importer.import_all_files(year_filter=year, limit=None)
        
        if success:
            logger.info("\n🎉 Clean slate re-import complete!")
            
            # Show new stats
            new_data = self.check_existing_data()
            if new_data:
                logger.info(f"\n📊 New Database Stats:")
                logger.info(f"   Sessions: {new_data['sessions']:,}")
                logger.info(f"   Players: {new_data['players']:,}")
                logger.info(f"   Processed Files: {new_data['processed_files']:,}")
                logger.info(f"   Date Range: {new_data['date_range'][0]} to {new_data['date_range'][1]}")
        
        return success
    
    def option_2_incremental(self, stats_dir: str, year: int = 2025):
        """
        Option 2: Incremental Import
        
        Only imports NEW files that haven't been processed yet.
        Safe to run multiple times - won't create duplicates.
        
        ✅ SAFE: Uses processed_files table to skip already imported data
        """
        logger.info("=" * 60)
        logger.info("OPTION 2: INCREMENTAL IMPORT (Safe)")
        logger.info("=" * 60)
        
        # Check existing data
        existing = self.check_existing_data()
        if existing:
            logger.info(f"\n📊 Current Database Stats:")
            logger.info(f"   Sessions: {existing['sessions']:,}")
            logger.info(f"   Players: {existing['players']:,}")
            logger.info(f"   Processed Files: {existing['processed_files']:,}")
            logger.info(f"   Date Range: {existing['date_range'][0]} to {existing['date_range'][1]}")
        
        logger.info(f"\n✅ This is SAFE - will only import new files")
        logger.info(f"   Already processed files will be skipped")
        logger.info(f"   No duplicates will be created")
        
        response = input("\nProceed with incremental import? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            logger.info("❌ Aborted")
            return False
        
        logger.info(f"\n🔄 Starting incremental import from {stats_dir}...")
        logger.info(f"   Year filter: {year}")
        
        importer = BulkStatsImporter(self.db_path, stats_dir=stats_dir)
        success = importer.import_all_files(year_filter=year, limit=None)
        
        if success:
            logger.info("\n🎉 Incremental import complete!")
            
            # Show updated stats
            new_data = self.check_existing_data()
            if new_data and existing:
                logger.info(f"\n📊 Updated Database Stats:")
                logger.info(f"   Sessions: {existing['sessions']:,} → {new_data['sessions']:,} (+{new_data['sessions'] - existing['sessions']:,})")
                logger.info(f"   Players: {existing['players']:,} → {new_data['players']:,} (+{new_data['players'] - existing['players']:,})")
                logger.info(f"   Processed Files: {existing['processed_files']:,} → {new_data['processed_files']:,} (+{new_data['processed_files'] - existing['processed_files']:,})")
        
        return success
    
    def option_3_fix_specific_date_range(self, stats_dir: str, start_date: str, end_date: str):
        """
        Option 3: Fix Specific Date Range
        
        Deletes data for specific dates and re-imports only those files.
        Useful when you know specific dates have bad data.
        
        Example: Re-import Oct 28 & 30, 2025 to fix field mismatches
        """
        logger.info("=" * 60)
        logger.info("OPTION 3: FIX SPECIFIC DATE RANGE")
        logger.info("=" * 60)
        
        logger.info(f"\n📅 Target Date Range: {start_date} to {end_date}")
        
        # Check data in that range
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) FROM sessions 
                WHERE session_date BETWEEN ? AND ?
            """, (start_date, end_date))
            sessions_in_range = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM player_comprehensive_stats 
                WHERE session_date BETWEEN ? AND ?
            """, (start_date, end_date))
            players_in_range = cursor.fetchone()[0]
            
            conn.close()
            
            logger.info(f"\n📊 Data in this range:")
            logger.info(f"   Sessions: {sessions_in_range:,}")
            logger.info(f"   Players: {players_in_range:,}")
            
        except sqlite3.Error as e:
            logger.error(f"Error checking date range: {e}")
            return False
        
        logger.warning(f"\n⚠️  This will DELETE data from {start_date} to {end_date}")
        response = input(f"\nType 'FIX {start_date} to {end_date}' to confirm: ")
        
        expected = f"FIX {start_date} to {end_date}"
        if response != expected:
            logger.info("❌ Aborted")
            return False
        
        # Delete data in range
        logger.info(f"\n🗑️  Deleting data for {start_date} to {end_date}...")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delete in correct order
            cursor.execute("""
                DELETE FROM weapon_comprehensive_stats 
                WHERE session_date BETWEEN ? AND ?
            """, (start_date, end_date))
            weapons_deleted = cursor.rowcount
            
            cursor.execute("""
                DELETE FROM player_comprehensive_stats 
                WHERE session_date BETWEEN ? AND ?
            """, (start_date, end_date))
            players_deleted = cursor.rowcount
            
            cursor.execute("""
                DELETE FROM sessions 
                WHERE session_date BETWEEN ? AND ?
            """, (start_date, end_date))
            sessions_deleted = cursor.rowcount
            
            # Clear processed files for this date range
            cursor.execute("""
                DELETE FROM processed_files 
                WHERE filename LIKE ? OR filename LIKE ?
            """, (f"{start_date}-%", f"{end_date}-%"))
            files_cleared = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"   Deleted {sessions_deleted:,} sessions")
            logger.info(f"   Deleted {players_deleted:,} player rows")
            logger.info(f"   Deleted {weapons_deleted:,} weapon rows")
            logger.info(f"   Cleared {files_cleared:,} processed file records")
            logger.info("✅ Date range cleaned!")
            
        except sqlite3.Error as e:
            logger.error(f"❌ Failed to clean date range: {e}")
            return False
        
        # Re-import only files in that range
        logger.info(f"\n🔄 Re-importing files from {start_date} to {end_date}...")
        
        importer = BulkStatsImporter(self.db_path)
        
        # Get list of files in date range
        stats_path = Path(stats_dir)
        files_to_import = []
        
        for file_path in sorted(stats_path.glob("*.txt")):
            filename = file_path.name
            file_date = '-'.join(filename.split('-')[:3])  # YYYY-MM-DD
            
            if start_date <= file_date <= end_date:
                files_to_import.append(file_path)
        
        logger.info(f"   Found {len(files_to_import)} files in date range")
        
        if not files_to_import:
            logger.warning("⚠️  No files found in date range!")
            return False
        
        # Import each file
        for file_path in files_to_import:
            success, msg = importer.process_single_file(file_path)
            if not success:
                logger.warning(f"   Failed: {file_path.name} - {msg}")
        
        logger.info("\n🎉 Date range re-import complete!")
        
        # Show updated stats for that range
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) FROM sessions 
                WHERE session_date BETWEEN ? AND ?
            """, (start_date, end_date))
            new_sessions = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM player_comprehensive_stats 
                WHERE session_date BETWEEN ? AND ?
            """, (start_date, end_date))
            new_players = cursor.fetchone()[0]
            
            conn.close()
            
            logger.info(f"\n📊 New Data in Range:")
            logger.info(f"   Sessions: {new_sessions:,}")
            logger.info(f"   Players: {new_players:,}")
            
        except sqlite3.Error as e:
            logger.error(f"Error checking results: {e}")
        
        return True


def main():
    """Interactive re-import tool"""
    print("=" * 60)
    print("🔄 SAFE DATABASE RE-IMPORT TOOL")
    print("=" * 60)
    print()
    print("This tool prevents duplicate data (no 6000 damage when it should be 3000!)")
    print()
    print("Choose your re-import strategy:")
    print()
    print("1️⃣  CLEAN SLATE - Delete ALL data, re-import everything")
    print("    ⚠️  Destructive but thorough fix")
    print("    Use when: Field mappings were wrong, need fresh start")
    print()
    print("2️⃣  INCREMENTAL - Only import NEW files (SAFE)")
    print("    ✅ Safe to run anytime, won't create duplicates")
    print("    Use when: Adding new stats files, regular updates")
    print()
    print("3️⃣  FIX DATE RANGE - Re-import specific dates only")
    print("    🎯 Surgical fix for known bad data")
    print("    Use when: Oct 28 & 30 had issues, fix just those dates")
    print()
    
    choice = input("Select option (1/2/3): ").strip()
    
    reimporter = SafeReimporter()
    
    if choice == "1":
        stats_dir = input("Stats directory [local_stats]: ").strip() or "local_stats"
        year = input("Year to import [2025]: ").strip() or "2025"
        reimporter.option_1_clean_slate(stats_dir, int(year))
        
    elif choice == "2":
        stats_dir = input("Stats directory [local_stats]: ").strip() or "local_stats"
        year = input("Year to import [2025]: ").strip() or "2025"
        reimporter.option_2_incremental(stats_dir, int(year))
        
    elif choice == "3":
        stats_dir = input("Stats directory [local_stats]: ").strip() or "local_stats"
        start_date = input("Start date (YYYY-MM-DD) [2025-10-28]: ").strip() or "2025-10-28"
        end_date = input("End date (YYYY-MM-DD) [2025-10-30]: ").strip() or "2025-10-30"
        reimporter.option_3_fix_specific_date_range(stats_dir, start_date, end_date)
        
    else:
        print("❌ Invalid choice")


if __name__ == "__main__":
    main()
