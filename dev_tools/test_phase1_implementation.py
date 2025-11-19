"""
Test script to verify Phase 1 implementation works correctly.

Tests:
1. Database has gaming_session_id column
2. All rounds have gaming_session_id assigned
3. Oct 19 has all 23 rounds in same gaming session
4. Gaming sessions are properly grouped
"""

import sqlite3
from datetime import datetime

DB_PATH = "bot/etlegacy_production.db"


def test_column_exists():
    """Test that gaming_session_id column exists"""
    print("\n" + "="*70)
    print("TEST 1: gaming_session_id column exists")
    print("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(sessions)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'gaming_session_id' in columns:
        print("✅ PASS: gaming_session_id column exists")
        return True
    else:
        print("❌ FAIL: gaming_session_id column not found")
        return False


def test_all_rounds_have_gaming_session_id():
    """Test that all rounds have gaming_session_id assigned"""
    print("\n" + "="*70)
    print("TEST 2: All rounds have gaming_session_id")
    print("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM rounds WHERE gaming_session_id IS NULL")
    null_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM rounds")
    total_count = cursor.fetchone()[0]
    
    print(f"   Total rounds: {total_count}")
    print(f"   Rounds with gaming_session_id: {total_count - null_count}")
    print(f"   Rounds without gaming_session_id: {null_count}")
    
    if null_count == 0:
        print("✅ PASS: All rounds have gaming_session_id")
        return True
    else:
        print(f"❌ FAIL: {null_count} rounds missing gaming_session_id")
        return False


def test_oct19_single_gaming_session():
    """Test that Oct 19 has all 23 rounds in ONE gaming session"""
    print("\n" + "="*70)
    print("TEST 3: October 19 has single gaming session")
    print("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COUNT(*), COUNT(DISTINCT gaming_session_id)
        FROM rounds
        WHERE round_date = '2025-10-19'
    """)
    round_count, gaming_session_count = cursor.fetchone()
    
    cursor.execute("""
        SELECT DISTINCT gaming_session_id
        FROM rounds
        WHERE round_date = '2025-10-19'
    """)
    gaming_session_ids = [row[0] for row in cursor.fetchall()]
    
    print(f"   Rounds on Oct 19: {round_count}")
    print(f"   Gaming sessions: {gaming_session_count}")
    print(f"   Gaming session IDs: {gaming_session_ids}")
    
    if gaming_session_count == 1 and round_count == 23:
        print("✅ PASS: All 23 rounds belong to same gaming session")
        return True
    else:
        print(f"❌ FAIL: Expected 1 gaming session with 23 rounds, got {gaming_session_count} sessions")
        return False


def test_gaming_session_grouping():
    """Test that gaming sessions are properly grouped"""
    print("\n" + "="*70)
    print("TEST 4: Gaming session grouping is correct")
    print("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            gaming_session_id,
            COUNT(*) as round_count,
            MIN(round_date || ' ' || round_time) as first_round,
            MAX(round_date || ' ' || round_time) as last_round
        FROM rounds
        WHERE gaming_session_id IS NOT NULL
        GROUP BY gaming_session_id
        ORDER BY gaming_session_id
    """)
    
    gaming_sessions = cursor.fetchall()
    
    print(f"   Total gaming sessions: {len(gaming_sessions)}")
    print()
    
    all_pass = True
    for gs_id, round_count, first_round, last_round in gaming_sessions:
        # Parse times
        first_dt = datetime.strptime(first_round, "%Y-%m-%d %H%M%S")
        last_dt = datetime.strptime(last_round, "%Y-%m-%d %H%M%S")
        duration_min = (last_dt - first_dt).total_seconds() / 60
        
        print(f"   Gaming Round #{gs_id}:")
        print(f"      Rounds: {round_count}")
        print(f"      Start:  {first_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"      End:    {last_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"      Duration: {duration_min:.0f} minutes ({duration_min/60:.1f} hours)")
        
        # Check if any gaps within this gaming session exceed 60 minutes
        cursor.execute("""
            SELECT round_date, round_time
            FROM rounds
            WHERE gaming_session_id = ?
            ORDER BY round_date, round_time
        """, (gs_id,))
        
        rounds = cursor.fetchall()
        max_gap = 0
        last_dt = None
        
        for date, time in rounds:
            current_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H%M%S")
            if last_dt:
                gap = (current_dt - last_dt).total_seconds() / 60
                if gap > max_gap:
                    max_gap = gap
            last_dt = current_dt
        
        print(f"      Max gap between rounds: {max_gap:.1f} minutes")
        
        if max_gap > 60:
            print(f"      ⚠️  WARNING: Gap exceeds 60 minutes!")
            all_pass = False
        else:
            print(f"      ✅ All gaps within 60 minutes")
        
        print()
    
    if all_pass:
        print("✅ PASS: All gaming sessions have proper grouping (gaps ≤ 60 min)")
        return True
    else:
        print("❌ FAIL: Some gaming sessions have gaps > 60 minutes")
        return False


def test_new_import_gets_gaming_session_id():
    """Test that new imports will get gaming_session_id (check schema)"""
    print("\n" + "="*70)
    print("TEST 5: New imports will get gaming_session_id")
    print("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if the column allows NULL or NOT NULL
    cursor.execute("PRAGMA table_info(sessions)")
    for row in cursor.fetchall():
        if row[1] == 'gaming_session_id':
            print(f"   Column: gaming_session_id")
            print(f"   Type: {row[2]}")
            print(f"   Allows NULL: {'NO' if row[3] else 'YES'}")
            print(f"   Default: {row[4] if row[4] else 'None'}")
    
    # Check if database_manager.py logic exists
    print("\n   Checking database_manager.py implementation...")
    with open('database_manager.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if '_get_or_create_gaming_session_id' in content:
            print("   ✅ _get_or_create_gaming_session_id() function exists")
        else:
            print("   ❌ _get_or_create_gaming_session_id() function NOT FOUND")
            return False
        
        if 'gaming_session_id = self._get_or_create_gaming_session_id' in content:
            print("   ✅ create_round() calls _get_or_create_gaming_session_id()")
        else:
            print("   ❌ create_round() does NOT call _get_or_create_gaming_session_id()")
            return False
    
    print("\n✅ PASS: New imports will get gaming_session_id assigned")
    return True


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("PHASE 1 IMPLEMENTATION TEST SUITE")
    print("="*70)
    print("Testing gaming_session_id implementation...")
    
    tests = [
        test_column_exists,
        test_all_rounds_have_gaming_session_id,
        test_oct19_single_gaming_session,
        test_gaming_session_grouping,
        test_new_import_gets_gaming_session_id,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ TEST FAILED WITH ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if all(results):
        print("\n✅ ALL TESTS PASSED! Phase 1 implementation is working correctly.")
    else:
        print("\n⚠️  SOME TESTS FAILED. Please review the results above.")
    
    print("="*70)


if __name__ == "__main__":
    main()
