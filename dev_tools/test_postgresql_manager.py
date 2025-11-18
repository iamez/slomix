#!/usr/bin/env python3
"""
Test PostgreSQL Database Manager
Validates the tool works before you use it in production
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from postgresql_database_manager import PostgreSQLDatabaseManager


async def test_connection():
    """Test 1: Can we connect?"""
    print("TEST 1: Connection Test")
    print("-" * 50)
    
    try:
        manager = PostgreSQLDatabaseManager()
        await manager.connect()
        print("✅ Connected to PostgreSQL")
        
        # Test query
        async with manager.pool.acquire() as conn:
            result = await conn.fetchval("SELECT version()")
            print(f"✅ PostgreSQL version: {result.split(',')[0]}")
        
        await manager.disconnect()
        print("✅ Disconnected cleanly")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


async def test_validation():
    """Test 2: Can we validate?"""
    print("\nTEST 2: Validation Test")
    print("-" * 50)
    
    try:
        manager = PostgreSQLDatabaseManager()
        await manager.connect()
        
        results = await manager.validate_database()
        
        print(f"✅ Database has {results['rounds']:,} rounds")
        print(f"✅ Database has {results['player_comprehensive_stats']:,} player stats")
        
        await manager.disconnect()
        return True
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False


async def test_file_check():
    """Test 3: Can we see stat files?"""
    print("\nTEST 3: File Detection Test")
    print("-" * 50)
    
    try:
        manager = PostgreSQLDatabaseManager()
        
        files = list(manager.stats_dir.glob("*.txt"))
        if not files:
            print(f"⚠️  No stat files found in {manager.stats_dir}")
            print("   Make sure local_stats/ directory exists with .txt files")
            return False
        
        print(f"✅ Found {len(files):,} stat files")
        print(f"   First: {files[0].name}")
        print(f"   Last:  {files[-1].name}")
        return True
    except Exception as e:
        print(f"❌ File check failed: {e}")
        return False


async def test_parser():
    """Test 4: Can we parse files?"""
    print("\nTEST 4: Parser Test")
    print("-" * 50)
    
    try:
        manager = PostgreSQLDatabaseManager()
        
        files = list(manager.stats_dir.glob("*.txt"))
        if not files:
            print("⚠️  No files to test")
            return False
        
        # Try parsing first file
        test_file = files[0]
        print(f"   Parsing: {test_file.name}")
        
        parsed = manager.parser.parse_stats_file(str(test_file))
        
        if not parsed or parsed.get('error'):
            print(f"❌ Parse failed: {parsed.get('error') if parsed else 'No data'}")
            return False
        
        print(f"✅ Parsed successfully")
        print(f"   Map: {parsed.get('map_name')}")
        print(f"   Players: {len(parsed.get('players', []))}")
        return True
    except Exception as e:
        print(f"❌ Parser test failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("🧪 POSTGRESQL DATABASE MANAGER - TEST SUITE")
    print("=" * 70)
    print()
    
    tests = [
        ("Connection", test_connection),
        ("Validation", test_validation),
        ("File Detection", test_file_check),
        ("Parser", test_parser),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Test crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - Ready to use!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - Fix issues before proceeding")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n👋 Tests interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test suite crashed: {e}")
        sys.exit(1)
