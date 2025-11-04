"""
Phase 2: Comprehensive Test Suite (Stage 4)
Validates database migration and code changes
"""
import sqlite3
import sys
from pathlib import Path

# Test results tracker
tests_passed = 0
tests_failed = 0
test_details = []

def test_result(name, passed, message=""):
    """Record a test result"""
    global tests_passed, tests_failed, test_details
    
    if passed:
        tests_passed += 1
        status = "✅ PASS"
    else:
        tests_failed += 1
        status = "❌ FAIL"
    
    test_details.append((name, status, message))
    print(f"{status}: {name}")
    if message:
        print(f"        {message}")

def connect_db():
    """Connect to the production database"""
    db_path = Path('bot/etlegacy_production.db')
    if not db_path.exists():
        return None
    return sqlite3.connect(str(db_path))

# ============================================================================
# DATABASE TESTS (10 tests)
# ============================================================================

print("=" * 70)
print("DATABASE TESTS")
print("=" * 70)

# Test 1: Database exists
conn = connect_db()
test_result(
    "DB-01: Database file exists",
    conn is not None,
    "bot/etlegacy_production.db"
)

if conn:
    cursor = conn.cursor()
    
    # Test 2: rounds table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rounds'")
    rounds_exists = cursor.fetchone() is not None
    test_result(
        "DB-02: 'rounds' table exists",
        rounds_exists
    )
    
    # Test 3: sessions table does NOT exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
    sessions_gone = cursor.fetchone() is None
    test_result(
        "DB-03: 'sessions' table removed",
        sessions_gone
    )
    
    # Test 4: rounds table has correct columns
    if rounds_exists:
        cursor.execute("PRAGMA table_info(rounds)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {'id', 'round_date', 'round_time', 'match_id', 'map_name', 
                   'round_number', 'time_limit', 'actual_time', 'winner_team', 
                   'defender_team', 'is_tied', 'round_outcome', 'created_at', 
                   'gaming_session_id'}
        has_correct_columns = expected.issubset(columns)
        test_result(
            "DB-04: rounds table has correct columns",
            has_correct_columns,
            f"Found {len(columns)} columns"
        )
    
    # Test 5: player_comprehensive_stats has round_id
    cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
    columns = {row[1] for row in cursor.fetchall()}
    has_round_id = 'round_id' in columns
    test_result(
        "DB-05: player_comprehensive_stats has round_id column",
        has_round_id
    )
    
    # Test 6: weapon_comprehensive_stats has round_id
    cursor.execute("PRAGMA table_info(weapon_comprehensive_stats)")
    columns = {row[1] for row in cursor.fetchall()}
    has_round_id = 'round_id' in columns
    test_result(
        "DB-06: weapon_comprehensive_stats has round_id column",
        has_round_id
    )
    
    # Test 7: Data integrity - count records
    cursor.execute("SELECT COUNT(*) FROM rounds")
    round_count = cursor.fetchone()[0]
    test_result(
        "DB-07: rounds table has data",
        round_count > 0,
        f"{round_count} rounds found"
    )
    
    # Test 8: Foreign key integrity - no orphaned player stats
    cursor.execute("""
        SELECT COUNT(*) FROM player_comprehensive_stats p
        WHERE NOT EXISTS (SELECT 1 FROM rounds r WHERE r.id = p.round_id)
    """)
    orphaned_players = cursor.fetchone()[0]
    test_result(
        "DB-08: No orphaned player stats",
        orphaned_players == 0,
        f"{orphaned_players} orphaned records"
    )
    
    # Test 9: Foreign key integrity - no orphaned weapon stats
    cursor.execute("""
        SELECT COUNT(*) FROM weapon_comprehensive_stats w
        WHERE NOT EXISTS (SELECT 1 FROM rounds r WHERE r.id = w.round_id)
    """)
    orphaned_weapons = cursor.fetchone()[0]
    test_result(
        "DB-09: No orphaned weapon stats",
        orphaned_weapons == 0,
        f"{orphaned_weapons} orphaned records"
    )
    
    # Test 10: Gaming session tracking intact
    cursor.execute("SELECT COUNT(DISTINCT gaming_session_id) FROM rounds WHERE gaming_session_id IS NOT NULL")
    gaming_session_count = cursor.fetchone()[0]
    test_result(
        "DB-10: Gaming session tracking intact",
        gaming_session_count > 0,
        f"{gaming_session_count} gaming sessions found"
    )
    
    conn.close()

print()

# ============================================================================
# CODE TESTS (5 tests)
# ============================================================================

print("=" * 70)
print("CODE TESTS")
print("=" * 70)

# Test 11: database_manager imports
try:
    # Add parent directory to path for import
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    import database_manager
    test_result(
        "CODE-01: database_manager imports successfully",
        True
    )
    
    # Test 12: DatabaseManager class has create_round method
    has_create_round = hasattr(database_manager.DatabaseManager, 'create_round')
    test_result(
        "CODE-02: DatabaseManager.create_round method exists",
        has_create_round
    )
except Exception as e:
    test_result(
        "CODE-01: database_manager imports successfully",
        False,
        str(e)
    )
    test_result(
        "CODE-02: DatabaseManager.create_round method exists",
        False
    )

# Test 13: Check for leftover 'sessions' references in database_manager
with open('database_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()
    # Count non-gaming_session references
    import re
    leftover_sessions = len(re.findall(r'\bsession\b(?!s\b)(?!_teams)', content.lower()))
    gaming_sessions = len(re.findall(r'gaming.?session', content.lower()))
    
    # Should be mostly gaming_session references
    test_result(
        "CODE-03: database_manager has minimal non-gaming session references",
        leftover_sessions < 20,
        f"{leftover_sessions} 'session' refs, {gaming_sessions} 'gaming_session' refs"
    )

# Test 14: Check bot/ultimate_bot.py syntax
try:
    with open('bot/ultimate_bot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    compile(content, 'bot/ultimate_bot.py', 'exec')
    test_result(
        "CODE-04: bot/ultimate_bot.py has valid syntax",
        True
    )
except SyntaxError as e:
    test_result(
        "CODE-04: bot/ultimate_bot.py has valid syntax",
        False,
        str(e)
    )

# Test 15: Check all cog files compile
cog_errors = []
cog_dir = Path('bot/cogs')
for cog_file in cog_dir.glob('*.py'):
    if cog_file.name == '__init__.py':
        continue
    try:
        with open(cog_file, 'r', encoding='utf-8') as f:
            content = f.read()
        compile(content, str(cog_file), 'exec')
    except SyntaxError as e:
        cog_errors.append(f"{cog_file.name}: {e}")

test_result(
    "CODE-05: All cog files have valid syntax",
    len(cog_errors) == 0,
    f"{len(cog_errors)} errors" if cog_errors else "All cogs valid"
)
if cog_errors:
    for error in cog_errors:
        print(f"        {error}")

print()

# ============================================================================
# SUMMARY
# ============================================================================

print("=" * 70)
print("TEST SUMMARY")
print("=" * 70)
print(f"✅ Tests passed: {tests_passed}")
print(f"❌ Tests failed: {tests_failed}")
print(f"📊 Total tests:  {tests_passed + tests_failed}")
print()

if tests_failed == 0:
    print("🎉 ALL TESTS PASSED! Phase 2 validation complete.")
    print()
    print("✅ Ready for Stage 5 (Deployment)")
    sys.exit(0)
else:
    print("⚠️  SOME TESTS FAILED! Review errors above.")
    print()
    print("❌ Not ready for deployment")
    sys.exit(1)
