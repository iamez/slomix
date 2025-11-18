#!/usr/bin/env python3
"""
Check if all rounds from last 14 days are already in the database
"""
import asyncio
import asyncpg
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from bot.config import load_config


async def check_missing_rounds():
    """Compare files in local_stats vs database"""
    config = load_config()
    stats_dir = Path("local_stats")
    
    # Calculate cutoff date (14 days ago)
    cutoff_date = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    
    print("=" * 70)
    print("🔍 Checking for Missing Rounds (Last 14 Days)")
    print("=" * 70)
    print(f"\nCutoff date: {cutoff_date}")
    
    # Get all files from last 14 days
    all_files = sorted(stats_dir.glob("*.txt"))
    files_in_range = [f for f in all_files if f.name[:10] >= cutoff_date]
    
    print(f"Files in last 14 days: {len(files_in_range):,}")
    
    # Connect to database
    pool = await asyncpg.create_pool(
        host=config.postgres_host.split(':')[0],
        port=int(config.postgres_host.split(':')[1]) if ':' in config.postgres_host else 5432,
        database=config.postgres_database,
        user=config.postgres_user,
        password=config.postgres_password,
        min_size=1,
        max_size=3
    )
    
    try:
        async with pool.acquire() as conn:
            # Get all processed files
            processed_files = await conn.fetch(
                "SELECT filename FROM processed_files WHERE success = true"
            )
            processed_set = {row['filename'] for row in processed_files}
            
            # Get all rounds in database for this period
            db_rounds = await conn.fetch(
                """
                SELECT match_id, round_number, round_date, map_name
                FROM rounds
                WHERE round_date >= $1
                ORDER BY round_date, round_time
                """,
                cutoff_date
            )
            
            print(f"Processed files in database: {len(processed_set):,}")
            print(f"Rounds in database (last 14 days): {len(db_rounds):,}")
            
            # Check which files are NOT processed
            missing_files = []
            processed_count = 0
            
            for file_path in files_in_range:
                filename = file_path.name
                if filename in processed_set:
                    processed_count += 1
                else:
                    missing_files.append(filename)
            
            print("\n" + "=" * 70)
            print("📊 RESULTS")
            print("=" * 70)
            print(f"\n✅ Files already processed: {processed_count:,} / {len(files_in_range):,}")
            print(f"❌ Files NOT processed: {len(missing_files):,}")
            
            if missing_files:
                print("\n🔍 Missing files (not in database):")
                for i, filename in enumerate(missing_files[:20], 1):
                    print(f"   {i:2d}. {filename}")
                if len(missing_files) > 20:
                    print(f"   ... and {len(missing_files) - 20} more")
                
                # Group by date
                from collections import defaultdict
                by_date = defaultdict(list)
                for f in missing_files:
                    date = f[:10]
                    by_date[date].append(f)
                
                print(f"\n📅 Missing files by date:")
                for date in sorted(by_date.keys()):
                    print(f"   {date}: {len(by_date[date])} files missing")
            else:
                print("\n✅ ALL FILES PROCESSED! Database is up to date.")
            
            # Check if there are rounds in DB but files are missing
            print("\n" + "=" * 70)
            print("🔄 Reverse Check: Rounds in DB vs Files on Disk")
            print("=" * 70)
            
            # Build expected filenames from database
            db_filenames = set()
            for row in db_rounds:
                # Try to reconstruct filename from match_id
                match_id = row['match_id']
                # match_id format: 2025-11-03-212845-supply-round-1
                if match_id.endswith('.txt'):
                    db_filenames.add(match_id)
                else:
                    db_filenames.add(f"{match_id}.txt")
            
            # Find files on disk
            disk_filenames = {f.name for f in files_in_range}
            
            # Check for orphaned rounds (in DB but file doesn't exist)
            orphaned_rounds = db_filenames - disk_filenames
            
            if orphaned_rounds:
                print(f"\n⚠️  Found {len(orphaned_rounds)} rounds in database but files are missing:")
                for i, filename in enumerate(sorted(orphaned_rounds)[:10], 1):
                    print(f"   {i:2d}. {filename}")
                if len(orphaned_rounds) > 10:
                    print(f"   ... and {len(orphaned_rounds) - 10} more")
            else:
                print("\n✅ All rounds in database have corresponding files on disk")
            
            # Summary
            print("\n" + "=" * 70)
            print("📈 SUMMARY")
            print("=" * 70)
            print(f"\n   Files on disk (last 14 days): {len(files_in_range):,}")
            print(f"   Files processed in DB: {processed_count:,}")
            print(f"   Files missing from DB: {len(missing_files):,}")
            print(f"   Rounds in DB (last 14 days): {len(db_rounds):,}")
            print(f"   DB rounds without files: {len(orphaned_rounds):,}")
            
            completion = (processed_count / len(files_in_range) * 100) if files_in_range else 0
            print(f"\n   Database completion: {completion:.1f}%")
            
            if completion == 100.0:
                print("\n   ✅ Database is COMPLETE - all files processed!")
                print("   💡 Nuclear wipe would just re-import the same data")
                print("   💡 Recommendation: No need to rebuild!")
            elif completion >= 95.0:
                print("\n   ⚠️  Database is nearly complete")
                print("   💡 Consider just importing the missing files")
                print("   💡 Use: postgresql_database_manager.py → Option 2")
            else:
                print("\n   ⚠️  Database is incomplete")
                print(f"   💡 {len(missing_files)} files need to be imported")
                print("   💡 Recommendation: Import missing files, don't do nuclear wipe")
            
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(check_missing_rounds())
