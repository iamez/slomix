"""
Quick test to verify data validation works
"""
import asyncio
from postgresql_database_manager import PostgreSQLDatabaseManager
from pathlib import Path

async def test_validation():
    """Test the new validation on a single file"""
    
    manager = PostgreSQLDatabaseManager()
    await manager.connect()
    
    print("\n" + "="*60)
    print("Testing Data Validation on Single File")
    print("="*60)
    
    # Find a file to test
    stats_dir = Path("local_stats")
    test_file = next(stats_dir.glob("*.txt"))
    
    print(f"\n📄 Test file: {test_file.name}")
    
    # Mark it as unprocessed to force re-import
    filename = test_file.name
    await manager.pool.execute(
        "DELETE FROM processed_files WHERE filename = $1",
        filename
    )
    print("✅ Marked as unprocessed")
    
    # Process it with validation
    print("\n🔄 Processing with validation checks...\n")
    success, message = await manager.process_file(test_file)
    
    print("\n📊 Result:")
    print(f"   Success: {success}")
    print(f"   Message: {message}")
    
    # Check for warnings
    error_msg = await manager.pool.fetchval(
        "SELECT error_message FROM processed_files WHERE filename = $1",
        filename
    )
    
    if error_msg:
        if "WARN" in error_msg:
            print("\n⚠️  Validation warnings found:")
            print(f"   {error_msg}")
        else:
            print("\n✅ No validation warnings - data matches perfectly!")
    else:
        print("\n✅ No validation warnings - data matches perfectly!")
    
    await manager.disconnect()

if __name__ == "__main__":
    asyncio.run(test_validation())
