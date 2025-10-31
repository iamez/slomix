#!/usr/bin/env python3
"""
ET:Legacy Stats Parser - Bug Test Suite
Tests for critical parsing and ingestion bugs
"""

import os
import sys
from community_stats_parser import C0RNP0RN3StatsParser

def test_extended_stats_float_parsing():
    """
    BUG #1 [HIGH]: Float values in extended stats cause int() parsing errors
    
    Issue: Fields like XP (0.0, 2.4) and time_played (82.5) are floats but parser
    tries to parse them as ints, causing ValueError and defaulting damage to 0.
    
    Impact: ALL damage_given, damage_received, and objective stats are lost!
    """
    print("\n" + "="*80)
    print("TEST #1: Extended Stats Float Parsing")
    print("="*80)
    
    parser = C0RNP0RN3StatsParser()
    result = parser.parse_stats_file("2025-10-23-221845-te_escape2-round-1.txt")
    
    if result['success']:
        player = result['players'][0]
        damage_given = player.get('damage_given', 0)
        
        print(f"Player: {player['name']}")
        print(f"Damage Given: {damage_given}")
        
        if damage_given == 0:
            print("❌ FAIL: damage_given is 0 (should be 639 based on file)")
            print("   Root cause: int() called on float fields in extended stats")
            return False
        else:
            print(f"✅ PASS: damage_given = {damage_given}")
            return True
    else:
        print("❌ FAIL: Could not parse file")
        return False


def test_round_2_file_matching():
    """
    BUG #2 [HIGH]: Round 2 files cannot find corresponding Round 1 files
    
    Issue: find_corresponding_round_1_file() searches in wrong directory.
    When file_path is "/full/path/to/file.txt", dirname is "/full/path/to/",
    but the search pattern looks in that directory which doesn't exist in test env.
    
    Impact: Round 2 files are processed with CUMULATIVE stats instead of differential!
    This means Round 2 stats include Round 1 data, making them useless.
    """
    print("\n" + "="*80)
    print("TEST #2: Round 2 File Matching")
    print("="*80)
    
    parser = C0RNP0RN3StatsParser()
    
    # Test Round 2 file
    r2_file = "2025-10-23-222205-te_escape2-round-2.txt"
    result = parser.parse_stats_file(r2_file)
    
    if result['success']:
        has_differential = result.get('differential_calculation', False)
        
        if not has_differential:
            print(f"❌ FAIL: Round 2 file processed without differential calculation")
            print(f"   Expected Round 1 file: 2025-10-23-221845-te_escape2-round-1.txt")
            print(f"   Stats will be cumulative (Round 1 + Round 2) instead of Round 2 only!")
            return False
        else:
            print(f"✅ PASS: Round 2 differential calculation performed")
            return True
    else:
        print("❌ FAIL: Could not parse file")
        return False


def test_round_2_differential_accuracy():
    """
    BUG #3 [MEDIUM]: Round 2 differential calculation may have race conditions
    
    Issue: If Round 1 and Round 2 files arrive at same time, or Round 2 arrives
    before Round 1 is processed, the differential will be wrong or missing.
    
    Impact: Stats may be double-counted or missing entirely.
    """
    print("\n" + "="*80)
    print("TEST #3: Round 2 Differential Accuracy")
    print("="*80)
    
    # This test requires the files to actually be present and parseable
    # For now, we'll document the potential race condition
    
    print("⚠️  POTENTIAL RACE CONDITION:")
    print("   1. Round 2 file arrives/detected first")
    print("   2. Round 1 file not in processed_files DB yet")
    print("   3. Round 2 processed without differential")
    print("   4. Later Round 1 arrives and gets processed")
    print("   5. Result: Both rounds processed without differential!")
    print("\n   Recommendation: Add detection_timestamp to processed_files")
    print("   and retry Round 2 processing if Round 1 not found initially")
    
    return None  # Not a pass/fail test, just documentation


def test_player_guid_consistency():
    """
    BUG #4 [MEDIUM]: Player GUID changes between rounds cause differential to fail
    
    Issue: If a player's GUID changes (reconnect, etc.), the differential
    calculation won't find them in Round 1 and will treat them as new player.
    
    Impact: Player stats for Round 2 will be cumulative instead of differential.
    """
    print("\n" + "="*80)
    print("TEST #4: Player GUID Consistency")
    print("="*80)
    
    parser = C0RNP0RN3StatsParser()
    
    r1_result = parser.parse_stats_file("2025-10-23-221845-te_escape2-round-1.txt")
    r2_result = parser.parse_stats_file("2025-10-23-222205-te_escape2-round-2.txt")
    
    if r1_result['success'] and r2_result['success']:
        r1_guids = {p['guid'] for p in r1_result['players']}
        r2_guids = {p['guid'] for p in r2_result['players']}
        
        missing_in_r2 = r1_guids - r2_guids
        new_in_r2 = r2_guids - r1_guids
        
        print(f"Round 1 players: {len(r1_guids)}")
        print(f"Round 2 players: {len(r2_guids)}")
        print(f"Players only in R1: {len(missing_in_r2)}")
        print(f"Players only in R2: {len(new_in_r2)}")
        
        if missing_in_r2 or new_in_r2:
            print("⚠️  WARNING: Player roster changed between rounds")
            print("   This is normal, but differential calc will treat new R2 players as fresh")
            return None
        else:
            print("✅ PASS: Same players in both rounds")
            return True
    else:
        print("❌ FAIL: Could not parse files")
        return False


def test_time_played_seconds_vs_minutes():
    """
    BUG #5 [LOW]: Inconsistent time storage (seconds vs minutes)
    
    Issue: Parser stores time_played_seconds but some code may use time_played_minutes.
    Both are stored but may get out of sync.
    
    Impact: DPM calculations or time displays may be incorrect.
    """
    print("\n" + "="*80)
    print("TEST #5: Time Storage Consistency")
    print("="*80)
    
    parser = C0RNP0RN3StatsParser()
    result = parser.parse_stats_file("2025-10-23-221845-te_escape2-round-1.txt")
    
    if result['success']:
        player = result['players'][0]
        seconds = player.get('time_played_seconds', 0)
        minutes = player.get('time_played_minutes', 0)
        
        expected_minutes = seconds / 60.0
        
        print(f"Player: {player['name']}")
        print(f"Time (seconds): {seconds}")
        print(f"Time (minutes): {minutes:.2f}")
        print(f"Expected (s/60): {expected_minutes:.2f}")
        
        if abs(minutes - expected_minutes) > 0.1:
            print("❌ FAIL: Time values inconsistent")
            return False
        else:
            print("✅ PASS: Time values consistent")
            return True
    else:
        print("❌ FAIL: Could not parse file")
        return False


def test_new_file_detection():
    """
    BUG #6 [MEDIUM]: New files may not be detected immediately
    
    Issue: SSH monitoring loop polls every 30 seconds. If a file appears,
    is processed, and a new one arrives within that window, may be missed.
    
    Impact: Stats files could be skipped entirely.
    """
    print("\n" + "="*80)
    print("TEST #6: New File Detection")
    print("="*80)
    
    print("⚠️  POTENTIAL ISSUE:")
    print("   SSH monitoring polls remote server every 30 seconds")
    print("   If multiple files appear between polls, ORDER matters!")
    print("")
    print("   Example:")
    print("   - 22:18:45 Round 1 file created")
    print("   - 22:22:05 Round 2 file created")
    print("   - 22:22:20 SSH poll detects BOTH files")
    print("   - Files processed in ALPHABETICAL order")
    print("   - Round 1 processed first ✓")
    print("   - Round 2 processed second ✓")
    print("")
    print("   BUT if files come in reverse alphabetical order:")
    print("   - Round 2 processed first (no Round 1 yet!) ✗")
    print("   - Round 1 processed second ✓")
    print("")
    print("   Recommendation: Sort files by timestamp before processing")
    
    return None


def test_db_write_guarantee():
    """
    BUG #7 [HIGH]: Database writes may not be guaranteed
    
    Issue: No transaction handling or error recovery in DB import.
    If DB write fails partway through, data is lost and file marked as processed.
    
    Impact: Stats data permanently lost!
    """
    print("\n" + "="*80)
    print("TEST #7: Database Write Guarantee")
    print("="*80)
    
    print("⚠️  CRITICAL ISSUE:")
    print("   No evidence of transaction wrapping in DB import code")
    print("   If import fails partway through:")
    print("   1. Session row written")
    print("   2. Player 1 written")
    print("   3. Player 2 fails (DB error)")
    print("   4. File marked as processed")
    print("   5. Players 3-6 never written!")
    print("")
    print("   Recommendation:")
    print("   - Wrap all DB writes in a transaction")
    print("   - Only mark file as processed after COMMIT succeeds")
    print("   - Add retry logic for transient errors")
    
    return None


def test_double_processing():
    """
    BUG #8 [MEDIUM]: Files may be double-processed if processed_files check fails
    
    Issue: 4-layer check in should_process_file(), but if cache is stale
    or DB check fails, file could be processed twice.
    
    Impact: Duplicate stats in database, inflated player scores.
    """
    print("\n" + "="*80)
    print("TEST #8: Double Processing Prevention")
    print("="*80)
    
    print("⚠️  POTENTIAL ISSUE:")
    print("   should_process_file() has 4-layer check:")
    print("   1. In-memory cache")
    print("   2. DB filename check")
    print("   3. DB file_hash check (if available)")
    print("   4. DB file_timestamp check (if available)")
    print("")
    print("   BUT if bot restarts between processing and cache refresh:")
    print("   - Cache is empty")
    print("   - DB check runs")
    print("   - If DB returns no rows (query error?), file re-processed!")
    print("")
    print("   Recommendation:")
    print("   - Load processed_files cache on bot startup")
    print("   - Add UNIQUE constraint on filename in DB")
    print("   - Log all processing attempts with timestamps")
    
    return None


def run_all_tests():
    """Run all bug tests and generate report"""
    print("\n" + "#"*80)
    print("# ET:LEGACY STATS PARSER - BUG AUDIT REPORT")
    print("#"*80)
    
    tests = [
        ("Extended Stats Float Parsing", test_extended_stats_float_parsing),
        ("Round 2 File Matching", test_round_2_file_matching),
        ("Round 2 Differential Accuracy", test_round_2_differential_accuracy),
        ("Player GUID Consistency", test_player_guid_consistency),
        ("Time Storage Consistency", test_time_played_seconds_vs_minutes),
        ("New File Detection", test_new_file_detection),
        ("Database Write Guarantee", test_db_write_guarantee),
        ("Double Processing Prevention", test_double_processing),
    ]
    
    results = {}
    for name, test_func in tests:
        result = test_func()
        results[name] = result
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    high_priority = []
    medium_priority = []
    low_priority = []
    
    if results["Extended Stats Float Parsing"] == False:
        high_priority.append("BUG #1: Float parsing in extended stats [CRITICAL - ALL DAMAGE DATA LOST]")
    
    if results["Round 2 File Matching"] == False:
        high_priority.append("BUG #2: Round 2 file matching [CRITICAL - CUMULATIVE STATS INSTEAD OF DIFFERENTIAL]")
    
    medium_priority.append("BUG #3: Round 2 race condition [File arrival ordering]")
    medium_priority.append("BUG #4: Player GUID changes [Reconnects between rounds]")
    medium_priority.append("BUG #6: New file detection [Polling interval issues]")
    medium_priority.append("BUG #8: Double processing [Cache/DB sync issues]")
    
    low_priority.append("BUG #5: Time storage inconsistency [Seconds vs minutes]")
    
    high_priority.append("BUG #7: Database write guarantee [No transactions]")
    
    print("\n🔴 HIGH PRIORITY BUGS:")
    for bug in high_priority:
        print(f"   {bug}")
    
    print("\n🟡 MEDIUM PRIORITY BUGS:")
    for bug in medium_priority:
        print(f"   {bug}")
    
    print("\n🟢 LOW PRIORITY BUGS:")
    for bug in low_priority:
        print(f"   {bug}")
    
    print("\n" + "="*80)
    print("RECOMMENDATIONS:")
    print("="*80)
    print("1. FIX BUG #1 IMMEDIATELY - Use float() instead of int() for float fields")
    print("2. FIX BUG #2 IMMEDIATELY - Fix directory search in find_corresponding_round_1_file()")
    print("3. ADD TRANSACTIONS - Wrap all DB writes in transactions")
    print("4. ADD FILE SORTING - Sort files by timestamp before processing")
    print("5. ADD STARTUP CACHE - Load processed_files into cache on bot startup")
    print("6. ADD UNIQUE CONSTRAINT - Filename should be unique in processed_files table")


if __name__ == "__main__":
    run_all_tests()
