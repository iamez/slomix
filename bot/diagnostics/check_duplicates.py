import asyncio
import sys
sys.path.insert(0, '.')
from bot.core.database_adapter import create_adapter
from bot.config import load_config

async def main():
    config = load_config()
    db = create_adapter(**config.get_database_adapter_kwargs())
    await db.connect()
    
    # Check for duplicate rounds (same match_id)
    print("Checking for duplicate rounds...\n")
    
    duplicates = await db.fetch_all("""
        SELECT match_id, COUNT(*) as count
        FROM rounds
        WHERE round_date LIKE '2025-11-11%'
        GROUP BY match_id
        HAVING COUNT(*) > 1
        ORDER BY count DESC, match_id
    """)
    
    if duplicates:
        print(f"❌ Found {len(duplicates)} duplicate match_ids:\n")
        for match_id, count in duplicates:
            print(f"  {match_id}: {count} copies")
    else:
        print("✅ No duplicates found!")
    
    # Show total round count breakdown
    print("\n" + "="*80)
    print("Round count breakdown:\n")
    
    counts = await db.fetch_all("""
        SELECT round_number, COUNT(*) as count
        FROM rounds
        WHERE round_date LIKE '2025-11-11%'
        GROUP BY round_number
        ORDER BY round_number
    """)
    
    total = 0
    for rnd, count in counts:
        print(f"  Round {rnd}: {count} rounds")
        total += count
    print(f"\n  TOTAL: {total} rounds")
    
    await db.close()

asyncio.run(main())
