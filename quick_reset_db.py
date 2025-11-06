#!/usr/bin/env python3
"""
Quick PostgreSQL Database Reset Script
=======================================

Simple wrapper to mimic the old database_manager.py workflow:
    echo "3`nYES DELETE EVERYTHING`n3`n2025-10-17`n2025-11-04" | python quick_reset_db.py

Options:
    3 = Reset and rebuild with date range
    
After selecting option 3:
    - Confirmation: "YES DELETE EVERYTHING"
    - Another 3 (ignored, for compatibility)
    - Start date: 2025-10-17
    - End date: 2025-11-04
"""

import sys
import asyncio
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from postgresql_database_manager import PostgreSQLDatabaseManager


async def quick_reset():
    """Quick reset workflow"""
    manager = PostgreSQLDatabaseManager()
    
    try:
        await manager.connect()
        
        # Read inputs
        option = input().strip()  # Should be "3"
        confirm = input().strip()  # Should be "YES DELETE EVERYTHING"
        _ignored = input().strip()  # Old format had extra "3"
        start_date = input().strip()  # e.g., "2025-10-17"
        end_date = input().strip()  # e.g., "2025-11-04"
        
        if confirm == "YES DELETE EVERYTHING":
            print(f"\n🔥 Wiping database and rebuilding from {start_date} to {end_date}...")
            await manager.rebuild_from_scratch(
                year=int(start_date[:4]),
                start_date=start_date,
                end_date=end_date,
                confirm=True
            )
            await manager.validate_database()
            print("\n✅ Database reset complete!")
        else:
            print("❌ Confirmation not received. Aborted.")
    
    finally:
        await manager.disconnect()


if __name__ == "__main__":
    asyncio.run(quick_reset())
