#!/usr/bin/env python3
"""
Test Complete Data Flow: Parser → Database → Bot
Verifies the entire pipeline works correctly
"""

import sqlite3
import sys
from pathlib import Path

from community_stats_parser import C0RNP0RN3StatsParser

# Add bot directory to path
sys.path.insert(0, 'bot')


def test_parser():
    """Test 1: Parser extracts data correctly"""
    print("=" * 80)
    print("TEST 1: Parser Extraction")
    print("=" * 80)

    parser = C0RNP0RN3StatsParser()
    test_file = "local_stats/2025-10-02-211808-etl_adlernest-round-1.txt"

    if not Path(test_file).exists():
        print(f"❌ Test file not found: {test_file}")
        return None

    result = parser.parse_stats_file(test_file)

    print(f"✅ Parse successful: {result['success']}")
    print(f"📍 Map: {result['map_name']}")
    print(f"🔢 Round: {result['round_num']}")
    print(f"👥 Players: {len(result['players'])}")
    print(f"⏱️  Session time: {result.get('actual_time', 'N/A')}")

    if result['players']:
        player = result['players'][0]
        print(f"\n👤 Sample Player: {player['name']}")
        print(f"   • Kills/Deaths: {player['kills']}/{player['deaths']}")
        print(f"   • Damage: {player['damage_given']}")
        print(f"   • Time (seconds): {player.get('time_played_seconds', 'MISSING')}")
        print(f"   • Time (display): {player.get('time_display', 'MISSING')}")
        print(f"   • DPM: {player.get('dpm', 0):.2f}")

        # Check objective_stats
        obj = player.get('objective_stats', {})
        print(f"   • Objective stats fields: {len(obj)}")

    return result


def test_database_schema():
    """Test 2: Database schema matches parser output"""
    print("\n" + "=" * 80)
    print("TEST 2: Database Schema Check")
    print("=" * 80)

    db_path = "etlegacy_production.db"
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get player_comprehensive_stats columns
    cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
    columns = cursor.fetchall()

    print(f"✅ Database found: {db_path}")
    print(f"📊 player_comprehensive_stats has {len(columns)} columns")

    # Check critical fields
    col_names = [col[1] for col in columns]
    critical_fields = [
        'time_played_seconds',
        'time_played_minutes',
        'time_display',
        'dpm',
        'damage_given',
        'kills',
        'deaths',
    ]

    print("\n🔍 Critical Fields Check:")
    for field in critical_fields:
        status = "✅" if field in col_names else "❌ MISSING"
        print(f"   {status} {field}")

    conn.close()
    return all(field in col_names for field in critical_fields)


def test_import_script():
    """Test 3: Import script can write to database"""
    print("\n" + "=" * 80)
    print("TEST 3: Import Script Test")
    print("=" * 80)

    import_script = Path("tools/simple_bulk_import.py")

    if not import_script.exists():
        print(f"❌ Import script not found: {import_script}")
        return False

    print(f"✅ Import script exists: {import_script}")

    # Check if it imports the parser
    with open(import_script, 'r', encoding='utf-8') as f:
        content = f.read()

    checks = {
        'Parser import': 'from community_stats_parser import' in content,
        'Database INSERT': 'INSERT INTO player_comprehensive_stats' in content,
        'Time seconds field': 'time_played_seconds' in content,
        'Time display field': 'time_display' in content,
        'DPM field': 'dpm' in content,
    }

    print("\n🔍 Import Script Checks:")
    for check, result in checks.items():
        status = "✅" if result else "❌ MISSING"
        print(f"   {status} {check}")

    return all(checks.values())


def test_bot_queries():
    """Test 4: Bot can query the data"""
    print("\n" + "=" * 80)
    print("TEST 4: Bot Query Test")
    print("=" * 80)

    db_path = "etlegacy_production.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Count records
    cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
    total_records = cursor.fetchone()[0]
    print(f"📊 Total player records: {total_records}")

    if total_records == 0:
        print("⚠️  Database is empty - no data imported yet")
        conn.close()
        return False

    # Check for records with time data
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM player_comprehensive_stats
        WHERE time_played_seconds > 0
    """
    )
    records_with_time = cursor.fetchone()[0]

    print(
        f"⏱️  Records with time data: {records_with_time} ({
            records_with_time /
            total_records *
            100:.1f}%)"
    )

    # Sample a record
    cursor.execute(
        """
        SELECT player_name, time_played_seconds, time_display,
               damage_given, dpm, kills, deaths
        FROM player_comprehensive_stats
        WHERE time_played_seconds > 0
        LIMIT 1
    """
    )

    sample = cursor.fetchone()
    if sample:
        print(f"\n👤 Sample Record:")
        print(f"   • Player: {sample[0]}")
        print(f"   • Time (seconds): {sample[1]}s")
        print(f"   • Time (display): {sample[2]}")
        print(f"   • Damage: {sample[3]}")
        print(f"   • DPM: {sample[4]:.2f}")
        print(f"   • K/D: {sample[5]}/{sample[6]}")

    # Check if bot query would work
    cursor.execute(
        """
        SELECT
            player_name,
            SUM(damage_given) as total_damage,
            SUM(time_played_seconds) as total_seconds,
            (SUM(damage_given) * 60.0) / NULLIF(SUM(time_played_seconds), 0) as weighted_dpm
        FROM player_comprehensive_stats
        WHERE session_date = '2025-10-02'
        GROUP BY player_name
        LIMIT 3
    """
    )

    players = cursor.fetchall()
    if players:
        print(f"\n🏆 Top Players (October 2nd):")
        for p in players:
            print(f"   • {p[0]}: {p[1]} damage, {p[2]}s played, {p[3]:.2f} DPM")

    conn.close()
    return True


def test_bot_endstats_monitor():
    """Test 5: Check bot's auto-import functionality"""
    print("\n" + "=" * 80)
    print("TEST 5: Bot Auto-Import Check")
    print("=" * 80)

    bot_file = Path("bot/ultimate_bot.py")

    if not bot_file.exists():
        print(f"❌ Bot file not found: {bot_file}")
        return False

    with open(bot_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if endstats_monitor actually does anything
    if 'async def endstats_monitor' in content:
        print("✅ endstats_monitor function exists")

        # Check if it's empty
        monitor_start = content.find('async def endstats_monitor')
        monitor_section = content[monitor_start: monitor_start + 500]

        if 'pass' in monitor_section and 'parse_stats_file' not in monitor_section:
            print("❌ CRITICAL: endstats_monitor is EMPTY!")
            print("   The bot does NOT automatically import new stats files!")
            print("   You must manually run: python tools/simple_bulk_import.py")
            return False
        else:
            print("✅ endstats_monitor has implementation")
            return True
    else:
        print("❌ endstats_monitor function not found")
        return False


def main():
    """Run all tests"""
    print("\n" + "🔬" * 40)
    print("COMPLETE DATA FLOW TEST")
    print("🔬" * 40 + "\n")

    results = {}

    # Test 1: Parser
    parser_result = test_parser()
    results['Parser'] = parser_result is not None

    # Test 2: Database Schema
    results['Database Schema'] = test_database_schema()

    # Test 3: Import Script
    results['Import Script'] = test_import_script()

    # Test 4: Bot Queries
    results['Bot Queries'] = test_bot_queries()

    # Test 5: Bot Auto-Import
    results['Bot Auto-Import'] = test_bot_endstats_monitor()

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test}")

    all_passed = all(results.values())

    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Complete data flow is working correctly")
    else:
        print("⚠️  SOME TESTS FAILED")
        print("🔧 Issues need to be fixed before bot will work correctly")
    print("=" * 80 + "\n")

    # Recommendations
    print("\n📋 RECOMMENDATIONS:")
    if not results['Bot Auto-Import']:
        print("   1. ❌ Bot does NOT auto-import files")
        print("      → Must manually run: python tools/simple_bulk_import.py")
        print("      → OR implement endstats_monitor function in bot")

    if not results['Bot Queries']:
        print("   2. ❌ Database is empty or has issues")
        print("      → Run: python tools/simple_bulk_import.py local_stats\\2025-10-02-*.txt")

    if results['Parser'] and results['Import Script'] and not results['Bot Queries']:
        print("   3. ✅ Parser works, import script ready")
        print("      → Just need to run import to populate database!")


if __name__ == "__main__":
    main()
