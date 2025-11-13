#!/usr/bin/env python3
"""
DAY 1: Fix Critical Bugs
========================

This script fixes the 3 critical bugs identified in the architecture review:
1. Time threshold mismatch (30 min → 60 min)
2. Missing rounds (skip R0 files)
3. Time format inconsistency (normalize to HHMMSS)

Run this script to automatically apply all fixes.
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.config import load_config


async def fix_bug_1_time_threshold():
    """
    BUG #1: Fix time threshold mismatch

    Change MAX_TIME_DIFF_MINUTES from 30 to 60 in community_stats_parser.py
    """
    print("\n" + "="*70)
    print("BUG #1: Fixing time threshold mismatch (30 min → 60 min)")
    print("="*70)

    parser_file = Path(__file__).parent.parent / "bot" / "community_stats_parser.py"

    if not parser_file.exists():
        print(f"❌ ERROR: File not found: {parser_file}")
        return False

    # Read file
    with open(parser_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if already fixed
    if 'MAX_TIME_DIFF_MINUTES = 60' in content:
        print("✅ Already fixed! Time threshold is 60 minutes.")
        return True

    # Replace 30 with 60
    if 'MAX_TIME_DIFF_MINUTES = 30' in content:
        new_content = content.replace(
            'MAX_TIME_DIFF_MINUTES = 30',
            'MAX_TIME_DIFF_MINUTES = 60  # Match gaming_session_id threshold'
        )

        # Write back
        with open(parser_file, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print("✅ FIXED: Changed MAX_TIME_DIFF_MINUTES from 30 to 60")
        print(f"   File: {parser_file}")
        print(f"   Line: ~385")
        return True
    else:
        print("⚠️  WARNING: Could not find 'MAX_TIME_DIFF_MINUTES = 30' in file")
        print("   Please manually check line 385 of community_stats_parser.py")
        return False


async def fix_bug_2_remove_r0_files():
    """
    BUG #2: Remove R0 (match summary) files from database

    These cause duplicate counting and missing rounds in !last_session
    """
    print("\n" + "="*70)
    print("BUG #2: Removing R0 (match summary) files from database")
    print("="*70)

    config = load_config()

    if config.database_type != 'postgresql':
        print("⚠️  WARNING: This script requires PostgreSQL")
        return False

    try:
        # Connect to database
        conn = await asyncpg.connect(
            host=config.postgres_host.split(':')[0],
            port=int(config.postgres_host.split(':')[1]) if ':' in config.postgres_host else 5432,
            database=config.postgres_database,
            user=config.postgres_user,
            password=config.postgres_password
        )

        # Count R0 files
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM rounds WHERE round_number = 0"
        )

        if count == 0:
            print("✅ No R0 files found in database. Already clean!")
            await conn.close()
            return True

        print(f"   Found {count} R0 (match summary) entries")

        # Get R0 round IDs
        r0_round_ids = await conn.fetch(
            "SELECT id FROM rounds WHERE round_number = 0"
        )

        if r0_round_ids:
            round_ids = [row['id'] for row in r0_round_ids]

            # Delete player stats for these rounds
            deleted_players = await conn.execute(
                f"DELETE FROM player_comprehensive_stats WHERE round_id = ANY($1)",
                round_ids
            )

            # Delete weapon stats for these rounds
            deleted_weapons = await conn.execute(
                f"DELETE FROM weapon_comprehensive_stats WHERE round_id = ANY($1)",
                round_ids
            )

            # Delete rounds
            deleted_rounds = await conn.execute(
                "DELETE FROM rounds WHERE round_number = 0"
            )

            print(f"✅ FIXED: Deleted {count} R0 entries")
            print(f"   - Deleted {deleted_players.split()[-1]} player stats")
            print(f"   - Deleted {deleted_weapons.split()[-1]} weapon stats")
            print(f"   - Deleted {deleted_rounds.split()[-1]} rounds")

        await conn.close()
        return True

    except Exception as e:
        print(f"❌ ERROR: Failed to remove R0 files: {e}")
        return False


async def fix_bug_3_normalize_time_format():
    """
    BUG #3: Normalize round_time to HHMMSS format

    Remove colons from time format for consistent sorting
    """
    print("\n" + "="*70)
    print("BUG #3: Normalizing time format (HH:MM:SS → HHMMSS)")
    print("="*70)

    config = load_config()

    if config.database_type != 'postgresql':
        print("⚠️  WARNING: This script requires PostgreSQL")
        return False

    try:
        # Connect to database
        conn = await asyncpg.connect(
            host=config.postgres_host.split(':')[0],
            port=int(config.postgres_host.split(':')[1]) if ':' in config.postgres_host else 5432,
            database=config.postgres_database,
            user=config.postgres_user,
            password=config.postgres_password
        )

        # Count rounds with colons in time
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM rounds WHERE round_time LIKE '%:%'"
        )

        if count == 0:
            print("✅ No times with colons found. Already normalized!")
            await conn.close()
            return True

        print(f"   Found {count} rounds with colon-formatted times")

        # Normalize times (remove colons)
        result = await conn.execute(
            "UPDATE rounds SET round_time = REPLACE(round_time, ':', '') WHERE round_time LIKE '%:%'"
        )

        updated = result.split()[-1] if result else '0'

        print(f"✅ FIXED: Normalized {updated} round_time values")
        print(f"   Format: HH:MM:SS → HHMMSS")

        # Verify
        remaining = await conn.fetchval(
            "SELECT COUNT(*) FROM rounds WHERE round_time LIKE '%:%'"
        )

        if remaining == 0:
            print(f"✅ VERIFIED: All times normalized successfully")
        else:
            print(f"⚠️  WARNING: {remaining} times still contain colons")

        await conn.close()
        return True

    except Exception as e:
        print(f"❌ ERROR: Failed to normalize times: {e}")
        return False


async def main():
    """Run all bug fixes"""
    print("\n" + "="*70)
    print("DAY 1: CRITICAL BUG FIXES")
    print("="*70)
    print("\nThis script will fix 3 critical bugs:")
    print("1. Time threshold mismatch (30 → 60 min)")
    print("2. Remove R0 match summary files")
    print("3. Normalize time format (HH:MM:SS → HHMMSS)")
    print("\n" + "="*70)

    # Confirm
    response = input("\nProceed with fixes? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("\n❌ Aborted by user")
        return

    # Run fixes
    results = []

    # Bug 1: Time threshold
    results.append(("Time Threshold", await fix_bug_1_time_threshold()))

    # Bug 2: R0 files
    results.append(("R0 Files", await fix_bug_2_remove_r0_files()))

    # Bug 3: Time format
    results.append(("Time Format", await fix_bug_3_normalize_time_format()))

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    for name, success in results:
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{status}: {name}")

    all_success = all(success for _, success in results)

    if all_success:
        print("\n🎉 All bugs fixed successfully!")
        print("\nNext steps:")
        print("1. Test R2 differential calculation:")
        print("   python bot/community_stats_parser.py local_stats/*-round-2.txt")
        print("\n2. Test !last_session command in Discord")
        print("\n3. Verify database sorting:")
        print("   psql -d etlegacy -c 'SELECT round_date, round_time FROM rounds ORDER BY round_date DESC, round_time DESC LIMIT 10'")
    else:
        print("\n⚠️  Some fixes failed. Please check errors above.")

    print("\n" + "="*70)


if __name__ == "__main__":
    asyncio.run(main())
