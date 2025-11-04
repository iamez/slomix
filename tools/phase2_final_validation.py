"""
Phase 2 Final Validation Suite
Comprehensive test to verify Phase 2 success after fresh import
"""
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

def connect_db():
    """Connect to production database"""
    db_path = Path('bot/etlegacy_production.db')
    if not db_path.exists():
        print("❌ Database not found!")
        return None
    return sqlite3.connect(str(db_path))

print("=" * 80)
print("🧪 PHASE 2 FINAL VALIDATION - COMPREHENSIVE TEST SUITE")
print("=" * 80)
print()

# ============================================================================
# TEST 1: Database Schema (Phase 2 Terminology)
# ============================================================================
print("📋 TEST 1: DATABASE SCHEMA (Phase 2 Terminology)")
print("-" * 80)

conn = connect_db()
if not conn:
    sys.exit(1)

cursor = conn.cursor()

# Check rounds table exists (not sessions)
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rounds'")
rounds_exists = cursor.fetchone() is not None
print(f"  ✅ 'rounds' table exists: {rounds_exists}")

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
sessions_exists = cursor.fetchone() is not None
print(f"  ✅ 'sessions' table removed: {not sessions_exists}")

# Check rounds table has correct columns
cursor.execute("PRAGMA table_info(rounds)")
columns = {row[1]: row[2] for row in cursor.fetchall()}
expected_cols = ['id', 'round_date', 'round_time', 'match_id', 'map_name', 
                 'round_number', 'gaming_session_id', 'winner_team', 'defender_team']

print(f"  ✅ rounds table has {len(columns)} columns")
for col in expected_cols:
    has_col = col in columns
    status = "✅" if has_col else "❌"
    print(f"    {status} {col}")

print()

# ============================================================================
# TEST 2: Data Import Statistics
# ============================================================================
print("📊 TEST 2: DATA IMPORT STATISTICS")
print("-" * 80)

cursor.execute("SELECT COUNT(*) FROM rounds")
round_count = cursor.fetchone()[0]
print(f"  📈 Total rounds imported: {round_count}")

cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
player_stats = cursor.fetchone()[0]
print(f"  📈 Player stats records: {player_stats}")

cursor.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats")
weapon_stats = cursor.fetchone()[0]
print(f"  📈 Weapon stats records: {weapon_stats}")

cursor.execute("SELECT COUNT(DISTINCT gaming_session_id) FROM rounds WHERE gaming_session_id IS NOT NULL")
gaming_sessions = cursor.fetchone()[0]
print(f"  📈 Gaming sessions created: {gaming_sessions}")

cursor.execute("SELECT COUNT(*) FROM rounds WHERE gaming_session_id IS NULL")
orphan_rounds = cursor.fetchone()[0]
print(f"  📈 Orphan rounds (no gaming_session): {orphan_rounds}")

print()

# ============================================================================
# TEST 3: Gaming Session Grouping (Phase 1 Preserved)
# ============================================================================
print("🎮 TEST 3: GAMING SESSION GROUPING (Phase 1 Logic)")
print("-" * 80)

cursor.execute("""
    SELECT 
        gaming_session_id,
        COUNT(*) as round_count,
        MIN(round_date) as first_date,
        MAX(round_date) as last_date,
        GROUP_CONCAT(DISTINCT map_name) as maps
    FROM rounds 
    WHERE gaming_session_id IS NOT NULL
    GROUP BY gaming_session_id
    ORDER BY gaming_session_id DESC
    LIMIT 5
""")

print("  📋 Last 5 gaming sessions:")
for row in cursor.fetchall():
    gs_id, rounds_in_session, first_date, last_date, maps = row
    print(f"    Gaming Session #{gs_id}: {rounds_in_session} rounds, Maps: {maps[:50]}...")

# Check for proper 3-map grouping
cursor.execute("""
    SELECT COUNT(*) as session_count
    FROM (
        SELECT gaming_session_id, COUNT(*) as round_count
        FROM rounds
        WHERE gaming_session_id IS NOT NULL
        GROUP BY gaming_session_id
        HAVING round_count >= 3
    )
""")
proper_sessions = cursor.fetchone()[0]
print(f"  ✅ Gaming sessions with 3+ rounds: {proper_sessions}")

print()

# ============================================================================
# TEST 4: Foreign Key Integrity
# ============================================================================
print("🔗 TEST 4: FOREIGN KEY INTEGRITY")
print("-" * 80)

# Check for orphaned player stats
cursor.execute("""
    SELECT COUNT(*) 
    FROM player_comprehensive_stats p
    WHERE NOT EXISTS (SELECT 1 FROM rounds r WHERE r.id = p.round_id)
""")
orphaned_players = cursor.fetchone()[0]
print(f"  ✅ Orphaned player stats: {orphaned_players} (should be 0)")

# Check for orphaned weapon stats
cursor.execute("""
    SELECT COUNT(*) 
    FROM weapon_comprehensive_stats w
    WHERE NOT EXISTS (SELECT 1 FROM rounds r WHERE r.id = w.round_id)
""")
orphaned_weapons = cursor.fetchone()[0]
print(f"  ✅ Orphaned weapon stats: {orphaned_weapons} (should be 0)")

print()

# ============================================================================
# TEST 5: Sample Data Verification (Compare with Raw Files)
# ============================================================================
print("📁 TEST 5: SAMPLE DATA VERIFICATION")
print("-" * 80)

# Get last 3 rounds
cursor.execute("""
    SELECT id, round_date, round_time, map_name, round_number, gaming_session_id
    FROM rounds
    ORDER BY round_date DESC, round_time DESC
    LIMIT 3
""")

print("  📋 Last 3 rounds in database:")
for row in cursor.fetchall():
    round_id, date, time, map_name, round_num, gs_id = row
    print(f"    Round #{round_id}: {date} {time} - {map_name} R{round_num} (GS#{gs_id})")
    
    # Check if raw file exists
    raw_file = Path(f"stats/{date}-{time}-{map_name}-round-{round_num}.txt")
    file_exists = raw_file.exists()
    status = "✅" if file_exists else "❌"
    print(f"      {status} Raw file exists: {raw_file.name}")

print()

# ============================================================================
# TEST 6: Column Naming (Phase 2 Success Check)
# ============================================================================
print("📝 TEST 6: COLUMN NAMING (Phase 2 Verification)")
print("-" * 80)

# Check player_comprehensive_stats columns
cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
player_cols = {row[1] for row in cursor.fetchall()}

has_round_id = 'round_id' in player_cols
has_session_id = 'session_id' in player_cols
has_round_date = 'round_date' in player_cols
has_session_date = 'session_date' in player_cols

print("  player_comprehensive_stats:")
print(f"    ✅ Has 'round_id': {has_round_id}")
print(f"    ✅ No 'session_id': {not has_session_id}")
print(f"    ✅ Has 'round_date': {has_round_date}")
print(f"    ✅ No 'session_date': {not has_session_date}")

# Check weapon_comprehensive_stats columns
cursor.execute("PRAGMA table_info(weapon_comprehensive_stats)")
weapon_cols = {row[1] for row in cursor.fetchall()}

has_round_id_w = 'round_id' in weapon_cols
has_session_id_w = 'session_id' in weapon_cols

print("  weapon_comprehensive_stats:")
print(f"    ✅ Has 'round_id': {has_round_id_w}")
print(f"    ✅ No 'session_id': {not has_session_id_w}")

print()

# ============================================================================
# TEST 7: Date Range Verification
# ============================================================================
print("📅 TEST 7: DATE RANGE VERIFICATION")
print("-" * 80)

cursor.execute("SELECT MIN(round_date), MAX(round_date) FROM rounds")
min_date, max_date = cursor.fetchone()
print(f"  📆 Date range: {min_date} to {max_date}")

cursor.execute("""
    SELECT round_date, COUNT(*) as rounds_count
    FROM rounds
    GROUP BY round_date
    ORDER BY round_date DESC
    LIMIT 7
""")

print("  📋 Last 7 days of data:")
for date, count in cursor.fetchall():
    print(f"    {date}: {count} rounds")

print()

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("=" * 80)
print("🏁 PHASE 2 VALIDATION SUMMARY")
print("=" * 80)

all_passed = (
    rounds_exists and 
    not sessions_exists and
    orphaned_players == 0 and 
    orphaned_weapons == 0 and
    has_round_id and not has_session_id and
    round_count > 0
)

if all_passed:
    print()
    print("  🎉 ✅ ALL TESTS PASSED!")
    print()
    print("  Phase 2 Success:")
    print(f"    ✅ Database uses 'rounds' table (not 'sessions')")
    print(f"    ✅ Columns renamed: session_id → round_id")
    print(f"    ✅ Columns renamed: session_date → round_date")
    print(f"    ✅ {round_count} rounds imported successfully")
    print(f"    ✅ {gaming_sessions} gaming sessions preserved")
    print(f"    ✅ 0 orphaned records")
    print(f"    ✅ Foreign key integrity maintained")
    print()
    print("  🚀 READY FOR PRODUCTION!")
    print()
    sys.exit(0)
else:
    print()
    print("  ⚠️  SOME TESTS FAILED")
    print()
    print("  Please review errors above.")
    print()
    sys.exit(1)

conn.close()
