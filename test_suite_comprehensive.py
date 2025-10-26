#!/usr/bin/env python3
"""
Comprehensive Bot Testing Suite - Run Overnight
Tests all bot functionality and logs results
"""

import sqlite3
import sys
import time
import traceback
from datetime import datetime

from community_stats_parser import C0RNP0RN3StatsParser

# Add bot directory to path
sys.path.append('bot')


print('\n' + '=' * 80)
print('🧪 COMPREHENSIVE BOT TESTING SUITE')
print('=' * 80)
print(f'Started: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 80 + '\n')

# Test results tracking
tests_passed = 0
tests_failed = 0
test_results = []


def test_result(test_name, passed, message=""):
    """Record test result"""
    global tests_passed, tests_failed, test_results
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"{status} | {test_name}"
    if message:
        result += f" | {message}"
    test_results.append(result)
    if passed:
        tests_passed += 1
    else:
        tests_failed += 1
    print(result)


print('\n' + '-' * 80)
print('TEST SUITE 1: DATABASE INTEGRITY')
print('-' * 80)

try:
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()

    # Test 1: Database exists and connects
    test_result("Database Connection", True, "Connected successfully")

    # Test 2: Check all required tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    required_tables = [
        'sessions',
        'player_comprehensive_stats',
        'weapon_comprehensive_stats',
        'player_links',
    ]
    missing = [t for t in required_tables if t not in tables]
    test_result(
        "Required Tables",
        len(missing) == 0,
        f"Found {len(tables)} tables" if not missing else f"Missing: {missing}",
    )

    # Test 3: Check session count for 2025-10-02
    cursor.execute("SELECT COUNT(*) FROM sessions WHERE session_date = '2025-10-02'")
    session_count = cursor.fetchone()[0]
    test_result(
        "Oct 2 Sessions Count", session_count == 20, f"Found {session_count} sessions (expected 20)"
    )

    # Test 4: Check escape map count
    cursor.execute(
        """
        SELECT COUNT(*) FROM sessions
        WHERE session_date = '2025-10-02' AND map_name = 'te_escape2'
    """
    )
    escape_count = cursor.fetchone()[0]
    test_result(
        "Escape Map Count", escape_count == 4, f"Found {escape_count} escape rounds (expected 4)"
    )

    # Test 5: Check for NULL values in critical fields
    cursor.execute(
        """
        SELECT COUNT(*) FROM player_comprehensive_stats
        WHERE player_name IS NULL OR kills IS NULL OR deaths IS NULL
    """
    )
    null_count = cursor.fetchone()[0]
    test_result(
        "No NULL Critical Fields", null_count == 0, f"Found {null_count} records with NULL values"
    )

    # Test 6: Check time_played_seconds are positive
    cursor.execute(
        """
        SELECT COUNT(*) FROM player_comprehensive_stats
        WHERE time_played_seconds <= 0
    """
    )
    zero_time = cursor.fetchone()[0]
    test_result("Valid Time Played", zero_time == 0, f"Found {zero_time} records with <= 0 time")

    # Test 7: Check DPM calculations
    cursor.execute(
        """
        SELECT COUNT(*) FROM player_comprehensive_stats
        WHERE dpm < 0 OR dpm > 2000
    """
    )
    bad_dpm = cursor.fetchone()[0]
    test_result("Valid DPM Range", bad_dpm == 0, f"Found {bad_dpm} records with invalid DPM")

    # Test 8: Check player count on Oct 2
    cursor.execute(
        """
        SELECT COUNT(*) FROM player_comprehensive_stats
        WHERE session_date = '2025-10-02'
    """
    )
    player_records = cursor.fetchone()[0]
    test_result(
        "Player Records Oct 2", player_records > 0, f"Found {player_records} player records"
    )

    # Test 9: Check for duplicate sessions (same date/map/round/time)
    cursor.execute(
        """
        SELECT map_name, round_number, COUNT(*) as cnt
        FROM sessions
        WHERE session_date = '2025-10-02'
        GROUP BY map_name, round_number
        HAVING cnt > 2
    """
    )
    duplicates = cursor.fetchall()
    test_result(
        "No Excessive Duplicates",
        len(duplicates) == 0,
        "No suspicious duplicates" if not duplicates else f"Found: {duplicates}",
    )

    # Test 10: Verify new stats columns exist and have data
    cursor.execute(
        """
        SELECT
            SUM(team_kills) as tk,
            SUM(self_kills) as sk,
            SUM(kill_steals) as ks,
            SUM(useless_kills) as uk,
            SUM(bullets_fired) as bf
        FROM player_comprehensive_stats
        WHERE session_date = '2025-10-02'
    """
    )
    row = cursor.fetchone()
    has_chaos_data = all(x > 0 for x in row if x is not None)
    test_result(
        "Chaos Stats Data",
        has_chaos_data,
        f"TK:{row[0]} SK:{row[1]} KS:{row[2]} UK:{row[3]} BF:{row[4]}",
    )

    conn.close()

except Exception as e:
    test_result("Database Tests", False, f"ERROR: {str(e)}")
    traceback.print_exc()

print('\n' + '-' * 80)
print('TEST SUITE 2: PARSER FUNCTIONALITY')
print('-' * 80)

try:
    parser = C0RNP0RN3StatsParser()

    # Test 11: Parse Round 1 file
    try:
        result = parser.parse_stats_file('local_stats/2025-10-02-211808-etl_adlernest-round-1.txt')
        test_result("Parse Round 1 File", True, f"Parsed {len(result.get('players', []))} players")
    except Exception as e:
        test_result("Parse Round 1 File", False, f"ERROR: {str(e)}")

    # Test 12: Parse Round 2 file with differential
    try:
        result = parser.parse_stats_file('local_stats/2025-10-02-212249-etl_adlernest-round-2.txt')
        test_result("Parse Round 2 File", True, f"Parsed {len(result.get('players', []))} players")
    except Exception as e:
        test_result("Parse Round 2 File", False, f"ERROR: {str(e)}")

    # Test 13: Verify parsed data structure
    if result:
        has_required = all(k in result for k in ['map_name', 'round_num', 'players'])
        test_result("Parser Output Structure", has_required, "All required fields present")

    # Test 14: Check player data completeness
    if result and result.get('players'):
        player = result['players'][0]
        has_fields = all(k in player for k in ['guid', 'name', 'kills', 'deaths'])
        test_result("Player Data Complete", has_fields, "All required player fields present")

except Exception as e:
    test_result("Parser Tests", False, f"ERROR: {str(e)}")
    traceback.print_exc()

print('\n' + '-' * 80)
print('TEST SUITE 3: QUERY PERFORMANCE')
print('-' * 80)

try:
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()

    # Test 15: Query last session (bot main query)
    start = time.time()
    cursor.execute(
        """
        SELECT DISTINCT session_date
        FROM sessions
        ORDER BY session_date DESC
        LIMIT 1
    """
    )
    latest_date = cursor.fetchone()[0]
    elapsed = (time.time() - start) * 1000
    test_result("Latest Date Query", elapsed < 100, f"Took {elapsed:.2f}ms")

    # Test 16: Get all sessions for date
    start = time.time()
    cursor.execute(
        """
        SELECT id, map_name, round_number FROM sessions
        WHERE session_date = ?
        ORDER BY id ASC
    """,
        (latest_date,),
    )
    sessions = cursor.fetchall()
    elapsed = (time.time() - start) * 1000
    test_result(
        "Session List Query", elapsed < 100, f"Found {len(sessions)} sessions in {elapsed:.2f}ms"
    )

    # Test 17: Aggregate player stats
    session_ids = [s[0] for s in sessions]
    start = time.time()
    cursor.execute(
        f"""
        SELECT player_name, SUM(kills), SUM(deaths), SUM(damage_given)
        FROM player_comprehensive_stats
        WHERE session_id IN ({','.join('?' * len(session_ids))})
        GROUP BY player_name
    """,
        session_ids,
    )
    players = cursor.fetchall()
    elapsed = (time.time() - start) * 1000
    test_result(
        "Player Aggregation Query",
        elapsed < 500,
        f"Aggregated {len(players)} players in {elapsed:.2f}ms",
    )

    # Test 18: Chaos stats query (new)
    start = time.time()
    cursor.execute(
        f"""
        SELECT
            SUM(team_kills), SUM(self_kills), SUM(kill_steals),
            SUM(useless_kills), SUM(bullets_fired)
        FROM player_comprehensive_stats
        WHERE session_id IN ({','.join('?' * len(session_ids))})
    """,
        session_ids,
    )
    chaos = cursor.fetchone()
    elapsed = (time.time() - start) * 1000
    test_result("Chaos Stats Query", elapsed < 100, f"Took {elapsed:.2f}ms")

    conn.close()

except Exception as e:
    test_result("Query Performance Tests", False, f"ERROR: {str(e)}")
    traceback.print_exc()

print('\n' + '-' * 80)
print('TEST SUITE 4: DATA VALIDATION')
print('-' * 80)

try:
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()

    # Test 19: Check K/D ratios are calculated correctly
    cursor.execute(
        """
        SELECT player_name, kills, deaths, kd_ratio
        FROM player_comprehensive_stats
        WHERE session_date = '2025-10-02' AND deaths > 0
        LIMIT 5
    """
    )
    for row in cursor.fetchall():
        expected_kd = round(row[1] / row[2], 2)
        actual_kd = row[3]
        diff = abs(expected_kd - actual_kd)
        test_result(
            f"K/D Ratio ({row[0][:10]})", diff < 0.02, f"Expected {expected_kd}, got {actual_kd}"
        )

    # Test 20: Check DPM calculations
    cursor.execute(
        """
        SELECT player_name, damage_given, time_played_seconds, dpm
        FROM player_comprehensive_stats
        WHERE session_date = '2025-10-02' AND time_played_seconds > 0
        LIMIT 5
    """
    )
    for row in cursor.fetchall():
        expected_dpm = round((row[1] * 60) / row[2], 2)
        actual_dpm = row[3]
        diff = abs(expected_dpm - actual_dpm)
        test_result(
            f"DPM Calculation ({row[0][:10]})",
            diff < 1.0,
            f"Expected {expected_dpm}, got {actual_dpm}",
        )

    conn.close()

except Exception as e:
    test_result("Data Validation Tests", False, f"ERROR: {str(e)}")
    traceback.print_exc()

print('\n' + '=' * 80)
print('TEST SUMMARY')
print('=' * 80)
print(f'\n✅ Tests Passed: {tests_passed}')
print(f'❌ Tests Failed: {tests_failed}')
print(f'📊 Success Rate: {(tests_passed / (tests_passed + tests_failed) * 100):.1f}%')

print('\n' + '-' * 80)
print('DETAILED RESULTS:')
print('-' * 80)
for result in test_results:
    print(result)

print('\n' + '=' * 80)
print(f'Completed: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 80 + '\n')

# Exit with error code if any tests failed
sys.exit(0 if tests_failed == 0 else 1)
