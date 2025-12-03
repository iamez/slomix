import asyncio
import sys
sys.path.insert(0, '.')
from bot.core.database_adapter import create_adapter
from bot.config import load_config

async def main():
    config = load_config()
    db = create_adapter(**config.get_database_adapter_kwargs())
    await db.connect()

    print("🔍 Checking for duplicate rounds...\n")

    # Find all duplicate match_ids
    duplicates = await db.fetch_all("""
        SELECT match_id, COUNT(*) as count
        FROM rounds
        WHERE round_date LIKE '2025-11-11%'
        GROUP BY match_id
        HAVING COUNT(*) > 1
        ORDER BY count DESC, match_id
    """)

    if not duplicates:
        print("✅ No duplicates found!")
        await db.close()
        return

    print(f"❌ Found {len(duplicates)} duplicate match_ids:\n")
    total_to_delete = 0
    for match_id, count in duplicates:
        print(f"  {match_id}: {count} copies")
        total_to_delete += (count - 1)

    print("\n📊 Summary:")
    print(f"  Duplicate match_ids: {len(duplicates)}")
    print(f"  Total duplicate entries to delete: {total_to_delete}")

    # Ask for confirmation
    print("\n⚠️  WARNING: This will DELETE duplicate entries from the database!")
    print("   Only the FIRST entry (lowest ID) for each match_id will be kept.")
    response = input("\nProceed with deletion? (yes/no): ")

    if response.lower() != 'yes':
        print("❌ Deletion cancelled.")
        await db.close()
        return

    print("\n🗑️  Deleting duplicates...\n")

    deleted_count = 0
    for match_id, count in duplicates:
        # For each duplicate match_id, delete all but the first entry (lowest id)
        result = await db.execute("""
            DELETE FROM rounds
            WHERE match_id = ?
              AND id NOT IN (
                  SELECT MIN(id)
                  FROM rounds
                  WHERE match_id = ?
              )
        """, (match_id, match_id))

        # The result should tell us how many rows were affected
        rows_deleted = count - 1  # We keep one, delete the rest
        deleted_count += rows_deleted
        print(f"  ✅ Deleted {rows_deleted} duplicate(s) for {match_id}")

    print("\n✅ Deletion complete!")
    print(f"   Total entries deleted: {deleted_count}")

    # Verify cleanup
    print("\n🔍 Verifying cleanup...\n")

    remaining_duplicates = await db.fetch_all("""
        SELECT match_id, COUNT(*) as count
        FROM rounds
        WHERE round_date LIKE '2025-11-11%'
        GROUP BY match_id
        HAVING COUNT(*) > 1
    """)

    if remaining_duplicates:
        print(f"⚠️  WARNING: Still found {len(remaining_duplicates)} duplicates:")
        for match_id, count in remaining_duplicates:
            print(f"  {match_id}: {count} copies")
    else:
        print("✅ No duplicates remaining!")

    # Show final round count
    final_count = await db.fetch_one("""
        SELECT COUNT(*)
        FROM rounds
        WHERE round_date LIKE '2025-11-11%'
          AND round_number IN (1, 2)
    """)

    print(f"\n📊 Final round count (R1 & R2): {final_count[0]}")

    await db.close()

asyncio.run(main())
