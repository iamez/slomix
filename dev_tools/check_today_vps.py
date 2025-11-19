#!/usr/bin/env python3
"""
Simple 3-Way Check for Today's Rounds
======================================
Checks today's files on:
1. VPS local_stats (files downloaded)
2. VPS PostgreSQL (files imported)
3. Comparison and recommendations

Run this ON THE VPS directly.
"""
import asyncio
import asyncpg
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, "/home/samba/share/slomix_discord")
from bot.config import load_config


async def check_today():
    """Check today's sync status"""
    config = load_config()
    today = datetime.now().strftime("%Y-%m-%d")
    
    print("=" * 70)
    print(f"🔍 Today's Sync Status Check - {today}")
    print("=" * 70)
    
    # Check local_stats directory
    stats_dir = Path("/home/samba/share/slomix_discord/local_stats")
    local_files = sorted([f.name for f in stats_dir.glob(f"{today}*.txt")])
    
    print(f"\n📁 VPS local_stats: {len(local_files)} files")
    for f in local_files:
        print(f"   ✓ {f}")
    
    # Check database
    pool = await asyncpg.create_pool(
        host=config.postgres_host.split(':')[0],
        port=int(config.postgres_host.split(':')[1]) if ':' in config.postgres_host else 5432,
        database=config.postgres_database,
        user=config.postgres_user,
        password=config.postgres_password,
        min_size=1,
        max_size=3
    )
    
    async with pool.acquire() as conn:
        # Check processed files
        processed = await conn.fetch(
            "SELECT filename, success FROM processed_files WHERE filename LIKE $1",
            f"{today}%"
        )
        
        # Check rounds
        rounds = await conn.fetch(
            """
            SELECT match_id, round_number, map_name, round_time
            FROM rounds
            WHERE round_date = $1
            ORDER BY round_time
            """,
            today
        )
    
    await pool.close()
    
    print(f"\n🗄️  PostgreSQL Database:")
    print(f"   Processed files: {len(processed)}")
    print(f"   Rounds created: {len(rounds)}")
    
    if rounds:
        print(f"\n   Latest rounds:")
        for r in rounds[-5:]:
            print(f"   ✓ Round {r['round_number']}: {r['map_name']} @ {r['round_time']}")
    
    # Comparison
    processed_names = {p['filename'] for p in processed if p['success']}
    local_set = set(local_files)
    
    missing_from_db = local_set - processed_names
    
    print("\n" + "=" * 70)
    print("📊 COMPARISON")
    print("=" * 70)
    print(f"\n   Files on disk: {len(local_files)}")
    print(f"   Files in DB:   {len(processed_names)}")
    print(f"   Missing:       {len(missing_from_db)}")
    
    if missing_from_db:
        print(f"\n   ⚠️  These files need to be imported:")
        for f in sorted(missing_from_db):
            print(f"      - {f}")
        print(f"\n   💡 Run: !sync_today in Discord")
    else:
        print(f"\n   ✅ All files are imported! Database is up to date.")
    
    # Calculate completion
    completion = (len(processed_names) / len(local_files) * 100) if local_files else 100
    print(f"\n   Sync status: {completion:.1f}%")
    
    if completion == 100:
        print("   Status: 🟢 PERFECT")
    elif completion >= 90:
        print("   Status: 🟡 GOOD")
    else:
        print("   Status: 🔴 NEEDS SYNC")


if __name__ == "__main__":
    asyncio.run(check_today())
