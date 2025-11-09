#!/usr/bin/env python3
"""
Quick migration script to add gaming_sessions table to existing PostgreSQL database
Run this once on VPS to fix the missing table error
"""

import asyncio
import sys
from postgresql_database_manager import PostgreSQLDatabaseManager

async def run_migration():
    """Run the gaming_sessions table migration"""
    print("🔄 Starting gaming_sessions table migration...")
    
    try:
        # Initialize database manager
        db = PostgreSQLDatabaseManager()
        await db.initialize()
        
        print("✅ Connected to database")
        
        # Run the migration
        await db._migrate_schema_if_needed()
        
        print("✅ Migration complete!")
        print("\nYou can now restart the bot.")
        
        await db.close()
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(run_migration())
