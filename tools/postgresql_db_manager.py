#!/usr/bin/env python3
"""
🐘 PostgreSQL Database Manager - Quick DB Operations
====================================================

PostgreSQL-specific database management tool for:
  ✅ Quick database wipe and recreate
  ✅ Schema application
  ✅ Data migration with date filters
  ✅ Database verification

Usage:
    # Full reset with date range:
    echo "1`n2025-10-17`n2025-11-04" | python tools/postgresql_db_manager.py
    
    # Just wipe and recreate (no data):
    echo "2" | python tools/postgresql_db_manager.py
    
    # Verify database:
    echo "3" | python tools/postgresql_db_manager.py

Author: ET:Legacy Stats System
Date: November 5, 2025
Version: 1.0 - PostgreSQL Migration
"""

import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.config import load_config
from bot.core.database_adapter import create_adapter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('postgresql_manager.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('PostgreSQLManager')


class PostgreSQLDatabaseManager:
    """PostgreSQL Database Manager for quick operations"""
    
    def __init__(self):
        self.config = load_config()
        if self.config.database_type != 'postgresql':
            raise ValueError("This tool only works with PostgreSQL! Check bot_config.json")
        
        self.db_adapter = None
        
    async def connect(self):
        """Connect to PostgreSQL"""
        self.db_adapter = await create_adapter(self.config)
        await self.db_adapter.connect()
        logger.info("✅ Connected to PostgreSQL")
    
    async def disconnect(self):
        """Disconnect from PostgreSQL"""
        if self.db_adapter:
            await self.db_adapter.disconnect()
            logger.info("✅ Disconnected from PostgreSQL")
    
    async def wipe_all_data(self):
        """Wipe all data from tables (keeps schema)"""
        logger.warning("⚠️ WIPING ALL DATA FROM TABLES...")
        
        tables = [
            'weapon_comprehensive_stats',
            'player_comprehensive_stats',
            'processed_files',
            'session_teams',
            'player_links',
            'player_aliases',
            'rounds'
        ]
        
        for table in tables:
            try:
                await self.db_adapter.execute(f"DELETE FROM {table}")
                logger.info(f"✅ Wiped {table}")
            except Exception as e:
                logger.error(f"❌ Error wiping {table}: {e}")
        
        logger.info("✅ All data wiped!")
    
    async def verify_database(self):
        """Verify database contents"""
        logger.info("🔍 Verifying database...")
        
        tables = {
            'rounds': 'round_id',
            'player_comprehensive_stats': 'id',
            'weapon_comprehensive_stats': 'id',
            'player_aliases': 'id',
            'player_links': 'discord_id',
            'session_teams': 'id',
            'processed_files': 'id'
        }
        
        for table, id_col in tables.items():
            try:
                result = await self.db_adapter.fetch_one(
                    f"SELECT COUNT(*) as count FROM {table}"
                )
                count = result['count'] if result else 0
                logger.info(f"  📊 {table}: {count:,} rows")
            except Exception as e:
                logger.error(f"  ❌ {table}: Error - {e}")
        
        logger.info("✅ Verification complete!")
    
    async def migrate_with_date_filter(self, start_date: str, end_date: str):
        """
        Run migration with date filter
        
        Args:
            start_date: YYYY-MM-DD format
            end_date: YYYY-MM-DD format
        """
        logger.info(f"🔄 Starting migration from {start_date} to {end_date}...")
        
        # Import migration script
        from tools.migrate_to_postgresql import migrate_database
        
        # Run migration with date filter
        await migrate_database(
            start_date=start_date,
            end_date=end_date
        )
        
        logger.info("✅ Migration complete!")


def print_menu():
    """Display interactive menu"""
    print("\n" + "="*70)
    print("🐘 PostgreSQL Database Manager")
    print("="*70)
    print("\n1. 🔥 WIPE & MIGRATE (with date range)")
    print("2. 🧹 WIPE ALL DATA (keep schema)")
    print("3. 🔍 VERIFY DATABASE")
    print("4. ❌ EXIT")
    print("\n" + "="*70)


async def main():
    """Main interactive menu"""
    manager = PostgreSQLDatabaseManager()
    
    try:
        await manager.connect()
        
        while True:
            print_menu()
            choice = input("\n👉 Select option (1-4): ").strip()
            
            if choice == "1":
                # Wipe and migrate with date range
                print("\n🔥 WIPE & MIGRATE WITH DATE RANGE")
                print("="*70)
                
                start_date = input("Start date (YYYY-MM-DD): ").strip()
                end_date = input("End date (YYYY-MM-DD): ").strip()
                
                confirm = input(f"\n⚠️ This will DELETE ALL DATA and re-import {start_date} to {end_date}.\n   Type 'YES DELETE EVERYTHING' to confirm: ").strip()
                
                if confirm == "YES DELETE EVERYTHING":
                    await manager.wipe_all_data()
                    await manager.migrate_with_date_filter(start_date, end_date)
                    await manager.verify_database()
                else:
                    logger.info("❌ Operation cancelled")
            
            elif choice == "2":
                # Wipe all data
                print("\n🧹 WIPE ALL DATA")
                print("="*70)
                
                confirm = input("\n⚠️ This will DELETE ALL DATA from all tables.\n   Type 'YES DELETE EVERYTHING' to confirm: ").strip()
                
                if confirm == "YES DELETE EVERYTHING":
                    await manager.wipe_all_data()
                    await manager.verify_database()
                else:
                    logger.info("❌ Operation cancelled")
            
            elif choice == "3":
                # Verify database
                await manager.verify_database()
            
            elif choice == "4":
                # Exit
                print("\n👋 Goodbye!")
                break
            
            else:
                print("❌ Invalid choice. Please select 1-4.")
    
    finally:
        await manager.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
