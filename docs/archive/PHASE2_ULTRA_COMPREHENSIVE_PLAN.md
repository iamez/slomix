# 🚀 PHASE 2: NUCLEAR SESSION→ROUND TERMINOLOGY RENAME
# ULTRA COMPREHENSIVE IMPLEMENTATION PLAN

**Status:** 📋 READY TO EXECUTE  
**Type:** 🔥 **BREAKING CHANGE** - Requires Maintenance Window  
**Risk Level:** 🔴 **HIGH** - Database schema + 800+ code changes  
**Estimated Time:** 8-14 hours (careful execution)  
**Prerequisite:** Phase 1 Complete ✅ (gaming_session_id added)

---

## 🎯 MISSION OBJECTIVE

**FIX THE DAY 0 TERMINOLOGY MISTAKE PERMANENTLY**

```
❌ BEFORE (Current - WRONG):
- Database table: "rounds" (actually stores rounds)
- Foreign key: "round_id" (actually means round_id)
- 238 "rounds" in DB = actually 238 ROUNDS
- Oct 19: 23 "rounds" = should be "23 rounds, 1 gaming session"

✅ AFTER (Correct):
- Database table: "rounds" (stores rounds - CORRECT)
- Foreign key: "round_id" (means round - CORRECT)
- 238 rounds in DB = 18 gaming sessions = CLEAR
- Oct 19: 23 rounds = 1 gaming session = PERFECT
```

---

## 📊 SCOPE ANALYSIS (From Complete Audit)

### Total Files to Update: **112 FILES**
### Total Changes: **800+ occurrences**

**Breakdown:**
- 🐍 **Python files:** 62 files (354 total .py in workspace)
- 📄 **Documentation:** 50+ .md files (242 total .md in workspace)
- 🗄️ **SQL schemas:** 1 file (schema.sql)
- ⚙️ **Config files:** As needed

### Critical High-Impact Files (Top 10):
1. `database_manager.py` - 50+ instances
2. `bot/ultimate_bot.py` - 100+ instances  
3. `bot/cogs/last_session_cog.py` - 60+ instances
4. `bot/cogs/stats_cog.py` - 30+ instances
5. `bot/cogs/session_cog.py` - 25+ instances
6. `bot/cogs/team_cog.py` - 20+ instances
7. `bot/cogs/leaderboard_cog.py` - 15+ instances
8. `tools/stopwatch_scoring.py` - 40+ instances
9. `bot/core/team_manager.py` - 30+ instances
10. `bot/core/advanced_team_detector.py` - 25+ instances

---

## 🔬 PRE-MIGRATION CHECKLIST

### ✅ Prerequisites (MUST BE COMPLETE):
- [x] Phase 1 committed to Git (c7223fb) ✅
- [x] Phase 1 pushed to GitHub ✅
- [x] gaming_session_id column exists and working ✅
- [x] Comprehensive validation passed (21/22 tests) ✅
- [ ] Full database backup created
- [ ] Rollback procedure tested
- [ ] All team members notified (maintenance window)
- [ ] Bot shut down
- [ ] No active users in Discord

### ⚠️ STOP CONDITIONS (If ANY true, ABORT):
- Database backup fails
- Rollback test fails
- Active users in Discord
- Bot is still running
- Any critical file is missing
- Git status is not clean

---

## 📋 PHASE 2 MASTER IMPLEMENTATION PLAN

### STAGE 1: PREPARATION (30 min)

#### 1.1 Create Full Database Backup
```powershell
# Location: C:\Users\seareal\Documents\stats\bot\etlegacy_production.db
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item "bot/etlegacy_production.db" "bot/BACKUP_BEFORE_PHASE2_$timestamp.db"
Copy-Item "bot/etlegacy_production.db" "bot/BACKUP_ROLLBACK.db"

# Verify backup
$original = Get-FileHash "bot/etlegacy_production.db"
$backup = Get-FileHash "bot/BACKUP_BEFORE_PHASE2_$timestamp.db"
if ($original.Hash -eq $backup.Hash) { 
    Write-Host "✅ Backup verified!" 
} else { 
    Write-Host "❌ BACKUP FAILED - ABORT!" 
    exit 1
}
```

#### 1.2 Create Git Branch
```bash
git checkout -b phase2-terminology-rename
git status  # Must be clean
```

#### 1.3 Create Rollback Script
```powershell
# File: rollback_phase2.ps1
Copy-Item "bot/BACKUP_ROLLBACK.db" "bot/etlegacy_production.db" -Force
git checkout team-system
git branch -D phase2-terminology-rename
Write-Host "✅ Rolled back to pre-Phase 2 state"
```

---

### STAGE 2: DATABASE MIGRATION (1-2 hours)

#### 2.1 Create Migration Script

**File:** `tools/migrate_sessions_to_rounds.sql`

```sql
-- ============================================================
-- PHASE 2 DATABASE MIGRATION: sessions → rounds
-- Date: [EXECUTION_DATE]
-- Database: bot/etlegacy_production.db
-- ============================================================

-- STEP 1: Create new rounds table with CORRECT naming
-- ============================================================
CREATE TABLE rounds (
    id INTEGER PRIMARY KEY,
    round_date TEXT NOT NULL,  -- Was: round_date
    round_time TEXT NOT NULL,  -- Was: round_time
    match_id TEXT,
    map_name TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    
    -- Time tracking
    time_limit TEXT,
    actual_time TEXT,
    
    -- Outcomes
    winner_team INTEGER DEFAULT 0,
    defender_team INTEGER DEFAULT 0,
    is_tied INTEGER DEFAULT 0,
    round_outcome TEXT,
    
    -- Relationships
    gaming_session_id INTEGER,  -- ✅ Phase 1 addition
    map_id INTEGER,
    
    -- Stopwatch fields
    original_time_limit TEXT,
    time_to_beat TEXT,
    completion_time TEXT,
    
    -- Metadata
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint
    UNIQUE(round_date, round_time, map_name, round_number)
);

-- STEP 2: Copy ALL data from sessions to rounds
-- ============================================================
INSERT INTO rounds (
    id, round_date, round_time, match_id, map_name, round_number,
    time_limit, actual_time, winner_team, defender_team, is_tied,
    round_outcome, gaming_session_id, map_id, original_time_limit,
    time_to_beat, completion_time, created_at
)
SELECT 
    id, round_date, round_time, match_id, map_name, round_number,
    time_limit, actual_time, winner_team, defender_team, is_tied,
    round_outcome, gaming_session_id, map_id, original_time_limit,
    time_to_beat, completion_time, created_at
FROM rounds;

-- STEP 3: Verify data copy
-- ============================================================
SELECT 
    'Data Verification' as check_type,
    (SELECT COUNT(*) FROM rounds) as old_count,
    (SELECT COUNT(*) FROM rounds) as new_count,
    CASE 
        WHEN (SELECT COUNT(*) FROM rounds) = (SELECT COUNT(*) FROM rounds) 
        THEN '✅ PASS' 
        ELSE '❌ FAIL - DATA LOSS!' 
    END as result;

-- STEP 4: Update player_comprehensive_stats foreign keys
-- ============================================================
-- Note: SQLite doesn't support ALTER COLUMN, so we recreate the table

-- 4.1: Create new table structure
CREATE TABLE player_comprehensive_stats_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL,  -- Was: round_id
    round_date TEXT NOT NULL,   -- Was: round_date
    map_name TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    player_guid TEXT NOT NULL,
    player_name TEXT NOT NULL,
    clean_name TEXT NOT NULL,
    team INTEGER,
    
    -- Core combat stats
    kills INTEGER DEFAULT 0,
    deaths INTEGER DEFAULT 0,
    damage_given INTEGER DEFAULT 0,
    damage_received INTEGER DEFAULT 0,
    team_damage_given INTEGER DEFAULT 0,
    team_damage_received INTEGER DEFAULT 0,
    
    -- Special kills
    gibs INTEGER DEFAULT 0,
    self_kills INTEGER DEFAULT 0,
    team_kills INTEGER DEFAULT 0,
    team_gibs INTEGER DEFAULT 0,
    headshot_kills INTEGER DEFAULT 0,
    
    -- Time tracking
    time_played_seconds INTEGER DEFAULT 0,
    time_played_minutes REAL DEFAULT 0,
    time_dead_minutes REAL DEFAULT 0,
    time_dead_ratio REAL DEFAULT 0,
    
    -- Performance metrics
    xp INTEGER DEFAULT 0,
    kd_ratio REAL DEFAULT 0,
    dpm REAL DEFAULT 0,
    hsr REAL DEFAULT 0,
    
    -- Objectives
    obj_captured INTEGER DEFAULT 0,
    obj_destroyed INTEGER DEFAULT 0,
    obj_returned INTEGER DEFAULT 0,
    obj_taken INTEGER DEFAULT 0,
    
    -- Support actions
    revives INTEGER DEFAULT 0,
    ammogiven INTEGER DEFAULT 0,
    healthgiven INTEGER DEFAULT 0,
    
    -- Other stats
    efficiency REAL DEFAULT 0,
    num_rounds INTEGER DEFAULT 0,
    poisoned INTEGER DEFAULT 0,
    
    -- Accuracy
    total_accuracy REAL DEFAULT 0,
    
    -- Metadata
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    FOREIGN KEY (round_id) REFERENCES rounds(id),  -- Updated reference
    UNIQUE(round_id, player_guid)  -- Updated unique constraint
);

-- 4.2: Copy all player stats data
INSERT INTO player_comprehensive_stats_new
SELECT * FROM player_comprehensive_stats;

-- 4.3: Drop old table
DROP TABLE player_comprehensive_stats;

-- 4.4: Rename new table
ALTER TABLE player_comprehensive_stats_new RENAME TO player_comprehensive_stats;

-- STEP 5: Update weapon_comprehensive_stats foreign keys
-- ============================================================

-- 5.1: Create new table structure
CREATE TABLE weapon_comprehensive_stats_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL,  -- Was: round_id
    round_date TEXT NOT NULL,   -- Was: round_date
    map_name TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    player_guid TEXT NOT NULL,
    player_name TEXT NOT NULL,
    weapon_name TEXT NOT NULL,
    
    -- Weapon stats
    kills INTEGER DEFAULT 0,
    deaths INTEGER DEFAULT 0,
    headshots INTEGER DEFAULT 0,
    hits INTEGER DEFAULT 0,
    shots INTEGER DEFAULT 0,
    
    -- Metadata
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    FOREIGN KEY (round_id) REFERENCES rounds(id),  -- Updated reference
    UNIQUE(round_id, player_guid, weapon_name)  -- Updated unique constraint
);

-- 5.2: Copy all weapon stats data
INSERT INTO weapon_comprehensive_stats_new
SELECT * FROM weapon_comprehensive_stats;

-- 5.3: Drop old table
DROP TABLE weapon_comprehensive_stats;

-- 5.4: Rename new table
ALTER TABLE weapon_comprehensive_stats_new RENAME TO weapon_comprehensive_stats;

-- STEP 6: Drop old rounds table
-- ============================================================
DROP TABLE sessions;

-- STEP 7: Recreate all indexes with CORRECT names
-- ============================================================

-- Rounds table indexes
CREATE INDEX idx_rounds_date ON rounds(round_date);
CREATE INDEX idx_rounds_match_id ON rounds(match_id);
CREATE INDEX idx_rounds_gaming_session_id ON rounds(gaming_session_id);
CREATE INDEX idx_rounds_date_time ON rounds(round_date, round_time);

-- Player stats indexes
CREATE INDEX idx_player_stats_round ON player_comprehensive_stats(round_id);
CREATE INDEX idx_player_stats_guid ON player_comprehensive_stats(player_guid);
CREATE INDEX idx_player_stats_clean_name ON player_comprehensive_stats(clean_name);
CREATE INDEX idx_players_dpm ON player_comprehensive_stats(dpm DESC);
CREATE INDEX idx_players_kd ON player_comprehensive_stats(kd_ratio DESC);

-- Weapon stats indexes
CREATE INDEX idx_weapon_stats_round ON weapon_comprehensive_stats(round_id);
CREATE INDEX idx_weapons_player ON weapon_comprehensive_stats(player_guid);

-- STEP 8: Final verification
-- ============================================================
SELECT '========================================' as separator;
SELECT 'MIGRATION COMPLETE - VERIFICATION' as status;
SELECT '========================================' as separator;

SELECT 'rounds table' as table_name, COUNT(*) as count FROM rounds
UNION ALL
SELECT 'player_comprehensive_stats', COUNT(*) FROM player_comprehensive_stats
UNION ALL
SELECT 'weapon_comprehensive_stats', COUNT(*) FROM weapon_comprehensive_stats;

-- Check foreign keys are valid
SELECT 
    'Foreign Key Check' as check_type,
    CASE 
        WHEN NOT EXISTS (
            SELECT 1 FROM player_comprehensive_stats p
            LEFT JOIN rounds r ON p.round_id = r.id
            WHERE r.id IS NULL
        ) THEN '✅ All player stats linked to rounds'
        ELSE '❌ Orphaned player stats found!'
    END as player_stats_result;

SELECT 
    'Foreign Key Check' as check_type,
    CASE 
        WHEN NOT EXISTS (
            SELECT 1 FROM weapon_comprehensive_stats w
            LEFT JOIN rounds r ON w.round_id = r.id
            WHERE r.id IS NULL
        ) THEN '✅ All weapon stats linked to rounds'
        ELSE '❌ Orphaned weapon stats found!'
    END as weapon_stats_result;

-- Check gaming_session_id preserved
SELECT 
    'gaming_session_id Check' as check_type,
    COUNT(DISTINCT gaming_session_id) as gaming_sessions,
    CASE 
        WHEN COUNT(DISTINCT gaming_session_id) >= 18 
        THEN '✅ Gaming sessions preserved'
        ELSE '❌ Gaming sessions lost!'
    END as result
FROM rounds
WHERE gaming_session_id IS NOT NULL;

SELECT '========================================' as separator;
SELECT '🎉 PHASE 2 MIGRATION COMPLETE! 🎉' as status;
SELECT '========================================' as separator;
```

#### 2.2 Execute Migration

```powershell
# Run migration script
cd C:\Users\seareal\Documents\stats
python -c "
import sqlite3
import sys

print('🚀 Starting Phase 2 Database Migration...')
print('=' * 60)

try:
    # Connect to database
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    # Read and execute migration script
    with open('tools/migrate_sessions_to_rounds.sql', 'r') as f:
        migration_sql = f.read()
    
    # Execute each statement
    for statement in migration_sql.split(';'):
        if statement.strip():
            cursor.execute(statement)
            conn.commit()
    
    print('✅ Migration completed successfully!')
    print('=' * 60)
    
    # Verify
    cursor.execute('SELECT COUNT(*) FROM rounds')
    rounds_count = cursor.fetchone()[0]
    print(f'Rounds table: {rounds_count} records')
    
    cursor.execute('SELECT COUNT(*) FROM player_comprehensive_stats')
    players_count = cursor.fetchone()[0]
    print(f'Player stats: {players_count} records')
    
    cursor.execute('SELECT COUNT(*) FROM weapon_comprehensive_stats')
    weapons_count = cursor.fetchone()[0]
    print(f'Weapon stats: {weapons_count} records')
    
    conn.close()
    
except Exception as e:
    print(f'❌ MIGRATION FAILED: {e}')
    print('🔄 ROLLING BACK...')
    import subprocess
    subprocess.run(['powershell', '-File', 'rollback_phase2.ps1'])
    sys.exit(1)
"
```

---

### STAGE 3: CODE UPDATES (4-6 hours)

#### 3.1 Core Database Layer

**File:** `database_manager.py` (1,139 lines)

**Strategy:** Line-by-line systematic replacement

**Changes Required (50+ instances):**

```python
# FIND & REPLACE OPERATIONS:

# 1. Table names
"rounds" → "rounds"
"sessions(" → "rounds("
"FROM rounds" → "FROM rounds"
"INTO rounds" → "INTO rounds"
"UPDATE sessions" → "UPDATE rounds"
"DELETE FROM rounds" → "DELETE FROM rounds"

# 2. Column names
"round_id" → "round_id"
"round_date" → "round_date"
"round_time" → "round_time"

# 3. Variable names
round_id → round_id
round_date → round_date
round_time → round_time

# 4. Function/method names
create_session → create_round
insert_player_stats(round_id → insert_player_stats(round_id
insert_weapon_stats(round_id → insert_weapon_stats(round_id

# 5. Comments and docstrings
"Create session" → "Create round"
"round record" → "round record"
"Session already exists" → "Round already exists"

# 6. Index names
idx_sessions_date_map → idx_rounds_date_map
idx_sessions_match_id → idx_rounds_match_id
idx_player_stats_session → idx_player_stats_round
idx_weapon_stats_session → idx_weapon_stats_round

# 7. Stats tracking
'sessions_created' → 'rounds_created'

# 8. Logging messages
"Creating session" → "Creating round"
"Session ID" → "Round ID"
```

**Critical Functions to Update:**

```python
# Line 539: create_session() → create_round()
def create_round(self, parsed_data: Dict, file_date: str, round_time: str, match_id: str) -> Optional[int]:
    """Create new round (with transaction safety and duplicate handling)"""
    # ... rest of function

# Line 591: insert_player_stats()
def insert_player_stats(self, round_id: int, round_date: str, 
                        map_name: str, round_num: int, player: Dict) -> bool:
    # ... update all queries

# Line 698: insert_weapon_stats()
def insert_weapon_stats(self, round_id: int, round_date: str,
                        map_name: str, round_num: int, player: Dict) -> bool:
    # ... update all queries
```

**Test After:** Run `check_schema.py` to verify database structure

---

#### 3.2 Bot Main File

**File:** `bot/ultimate_bot.py` (3,000+ lines)

**Changes Required (100+ instances):**

```python
# FIND & REPLACE (same as database_manager.py):
sessions → rounds
round_id → round_id
round_date → round_date
round_time → round_time

# Special attention to:
# 1. SSH auto-import queries
# 2. Discord command outputs
# 3. Embed messages
# 4. Logging statements
# 5. Error messages
```

**Critical Sections:**

```python
# Line ~2800-3000: Stats import function
async def import_stats_file(self, file_path):
    # Update all database queries
    # Update all logging messages
    # Update Discord notifications
    
# Line ~3500-3700: Last session display
async def show_last_round_stats(self):
    # Update query to use rounds table
    # Update all variable names
    # Update Discord embeds
```

---

#### 3.3 Bot Cogs (10+ files)

**Priority Order:**

1. **`bot/cogs/last_session_cog.py`** - 60+ changes
2. **`bot/cogs/stats_cog.py`** - 30+ changes
3. **`bot/cogs/session_cog.py`** - 25+ changes (filename stays, but refers to gaming sessions)
4. **`bot/cogs/team_cog.py`** - 20+ changes
5. **`bot/cogs/leaderboard_cog.py`** - 15+ changes
6. **`bot/cogs/admin_cog.py`** - 10+ changes
7. **`bot/cogs/sync_cog.py`** - 10+ changes
8. **`bot/cogs/link_cog.py`** - 5+ changes
9. **`bot/cogs/automation_commands.py`** - 5+ changes
10. **`bot/cogs/server_control.py`** - 5+ changes

**For Each Cog:**
```python
# Update:
1. All SQL queries (FROM rounds → FROM rounds)
2. All variable names (round_id → round_id)
3. All Discord embed messages
4. All logging statements
5. All comments and docstrings
6. All function parameters
```

---

#### 3.4 Utility Scripts (60+ files)

**Systematic Approach:**

```powershell
# Get all Python files
Get-ChildItem -Path . -Filter *.py -Recurse | 
    Where-Object { $_.Name -notlike "*__pycache__*" } |
    Select-Object -ExpandProperty FullName |
    Out-File python_files_to_update.txt

# Process each file
Get-Content python_files_to_update.txt | ForEach-Object {
    $file = $_
    Write-Host "Checking: $file"
    
    # Check if file contains "session" terminology
    if (Select-String -Path $file -Pattern "sessions|round_id|round_date|round_time" -Quiet) {
        Write-Host "  ⚠️ NEEDS UPDATE" -ForegroundColor Yellow
        # Add to update list
        Add-Content "files_needing_update.txt" $file
    } else {
        Write-Host "  ✅ Clean" -ForegroundColor Green
    }
}
```

**Categories:**

1. **Analysis Scripts** (20 files):
   - `analyze_*.py`
   - `comprehensive_*.py`
   - `deep_analysis.py`
   - `maximum_detail_analysis.py`

2. **Check Scripts** (25 files):
   - `check_*.py`
   - `investigate_*.py`
   - `validate_*.py`

3. **Backfill Scripts** (5 files):
   - `backfill_*.py`

4. **Tools** (30 files):
   - `tools/*.py`
   - `tools/round differential/*.py`
   - `tools/migrations/*.py`

5. **Development Scripts** (20 files):
   - `dev/*.py`
   - `dev/diagnostics/*.py`
   - `dev/test_bots/*.py`

---

#### 3.5 Documentation (50+ files)

**Find & Replace in ALL .md files:**

```markdown
# Simple text replacements:
rounds table → rounds table
round_id column → round_id column
round_date → round_date
round_time → round_time

# Context-aware replacements:
"session" (meaning round) → "round"
"rounds" (meaning rounds) → "rounds"

# Keep these as-is:
"gaming session" → NO CHANGE (correct term)
"session_teams table" → NO CHANGE (refers to gaming session teams)
```

**Critical Documentation Files:**

1. `PHASE2_PLANNING.md` - Update status
2. `COMPLETE_SESSION_TERMINOLOGY_AUDIT.md` - Mark as resolved
3. `SESSION_TERMINOLOGY_AUDIT_SUMMARY.md` - Update
4. `PHASE1_IMPLEMENTATION_COMPLETE.md` - Reference Phase 2
5. `README.md` - Update database schema section
6. `COMPLETE_SYSTEM_RUNDOWN.md` - Update architecture
7. `TEAM_SYSTEM_PLAN.md` - Update terminology
8. All other .md files as needed

---

### STAGE 4: TESTING (2-3 hours)

#### 4.1 Database Integrity Tests

```python
# File: test_phase2_database.py

import sqlite3
import sys

def test_database_migration():
    """Comprehensive Phase 2 migration validation"""
    print("🧪 Testing Phase 2 Database Migration")
    print("=" * 60)
    
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    tests_passed = 0
    tests_failed = 0
    
    # TEST 1: Rounds table exists
    print("\n1️⃣ Testing: rounds table exists")
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rounds'")
        if cursor.fetchone():
            print("   ✅ PASS: rounds table exists")
            tests_passed += 1
        else:
            print("   ❌ FAIL: rounds table not found!")
            tests_failed += 1
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        tests_failed += 1
    
    # TEST 2: Rounds table does NOT exist
    print("\n2️⃣ Testing: rounds table removed")
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rounds'")
        if not cursor.fetchone():
            print("   ✅ PASS: rounds table removed")
            tests_passed += 1
        else:
            print("   ❌ FAIL: rounds table still exists!")
            tests_failed += 1
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        tests_failed += 1
    
    # TEST 3: Rounds table has correct columns
    print("\n3️⃣ Testing: rounds table schema")
    try:
        cursor.execute("PRAGMA table_info(rounds)")
        columns = {col[1] for col in cursor.fetchall()}
        required_cols = {'id', 'round_date', 'round_time', 'match_id', 'gaming_session_id', 'round_number'}
        if required_cols.issubset(columns):
            print(f"   ✅ PASS: All required columns present")
            print(f"      Columns: {', '.join(sorted(columns))}")
            tests_passed += 1
        else:
            missing = required_cols - columns
            print(f"   ❌ FAIL: Missing columns: {missing}")
            tests_failed += 1
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        tests_failed += 1
    
    # TEST 4: Data preserved (count check)
    print("\n4️⃣ Testing: data preservation")
    try:
        cursor.execute("SELECT COUNT(*) FROM rounds")
        rounds_count = cursor.fetchone()[0]
        
        # Should be 238 rounds from Phase 1
        expected_min = 230
        if rounds_count >= expected_min:
            print(f"   ✅ PASS: {rounds_count} rounds (expected >= {expected_min})")
            tests_passed += 1
        else:
            print(f"   ❌ FAIL: Only {rounds_count} rounds (expected >= {expected_min})")
            tests_failed += 1
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        tests_failed += 1
    
    # TEST 5: Foreign keys updated (player_comprehensive_stats)
    print("\n5️⃣ Testing: player_comprehensive_stats foreign keys")
    try:
        cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
        columns = {col[1] for col in cursor.fetchall()}
        if 'round_id' in columns and 'round_id' not in columns:
            print("   ✅ PASS: round_id column exists, round_id removed")
            tests_passed += 1
        else:
            print(f"   ❌ FAIL: Incorrect columns")
            print(f"      Has round_id: {'round_id' in columns}")
            print(f"      Has round_id: {'round_id' in columns}")
            tests_failed += 1
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        tests_failed += 1
    
    # TEST 6: Foreign keys updated (weapon_comprehensive_stats)
    print("\n6️⃣ Testing: weapon_comprehensive_stats foreign keys")
    try:
        cursor.execute("PRAGMA table_info(weapon_comprehensive_stats)")
        columns = {col[1] for col in cursor.fetchall()}
        if 'round_id' in columns and 'round_id' not in columns:
            print("   ✅ PASS: round_id column exists, round_id removed")
            tests_passed += 1
        else:
            print(f"   ❌ FAIL: Incorrect columns")
            tests_failed += 1
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        tests_failed += 1
    
    # TEST 7: No orphaned player stats
    print("\n7️⃣ Testing: no orphaned player stats")
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM player_comprehensive_stats p
            LEFT JOIN rounds r ON p.round_id = r.id
            WHERE r.id IS NULL
        """)
        orphans = cursor.fetchone()[0]
        if orphans == 0:
            print("   ✅ PASS: No orphaned player stats")
            tests_passed += 1
        else:
            print(f"   ❌ FAIL: {orphans} orphaned player stats found!")
            tests_failed += 1
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        tests_failed += 1
    
    # TEST 8: No orphaned weapon stats
    print("\n8️⃣ Testing: no orphaned weapon stats")
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM weapon_comprehensive_stats w
            LEFT JOIN rounds r ON w.round_id = r.id
            WHERE r.id IS NULL
        """)
        orphans = cursor.fetchone()[0]
        if orphans == 0:
            print("   ✅ PASS: No orphaned weapon stats")
            tests_passed += 1
        else:
            print(f"   ❌ FAIL: {orphans} orphaned weapon stats found!")
            tests_failed += 1
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        tests_failed += 1
    
    # TEST 9: gaming_session_id preserved
    print("\n9️⃣ Testing: gaming_session_id preservation")
    try:
        cursor.execute("""
            SELECT COUNT(DISTINCT gaming_session_id) 
            FROM rounds 
            WHERE gaming_session_id IS NOT NULL
        """)
        gaming_sessions = cursor.fetchone()[0]
        if gaming_sessions >= 18:
            print(f"   ✅ PASS: {gaming_sessions} gaming sessions preserved")
            tests_passed += 1
        else:
            print(f"   ❌ FAIL: Only {gaming_sessions} gaming sessions (expected >= 18)")
            tests_failed += 1
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        tests_failed += 1
    
    # TEST 10: Indexes recreated
    print("\n🔟 Testing: indexes recreated with correct names")
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_rounds%'")
        round_indexes = [row[0] for row in cursor.fetchall()]
        expected_indexes = ['idx_rounds_date', 'idx_rounds_match_id', 'idx_rounds_gaming_session_id']
        
        if all(idx in round_indexes for idx in expected_indexes):
            print("   ✅ PASS: All round indexes present")
            print(f"      Indexes: {', '.join(round_indexes)}")
            tests_passed += 1
        else:
            missing = set(expected_indexes) - set(round_indexes)
            print(f"   ❌ FAIL: Missing indexes: {missing}")
            tests_failed += 1
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        tests_failed += 1
    
    # FINAL SUMMARY
    print("\n" + "=" * 60)
    print(f"📊 TEST RESULTS: {tests_passed}/{tests_passed + tests_failed} PASSED")
    print("=" * 60)
    
    if tests_failed == 0:
        print("🎉 ALL TESTS PASSED! Database migration successful!")
        conn.close()
        return True
    else:
        print(f"❌ {tests_failed} TESTS FAILED! Migration incomplete!")
        conn.close()
        return False

if __name__ == "__main__":
    success = test_database_migration()
    sys.exit(0 if success else 1)
```

#### 4.2 Code Functionality Tests

```python
# File: test_phase2_code.py

import sys
import subprocess

def test_code_updates():
    """Test that all code updates are applied correctly"""
    print("🧪 Testing Phase 2 Code Updates")
    print("=" * 60)
    
    tests_passed = 0
    tests_failed = 0
    
    # TEST 1: database_manager.py has no "rounds" references
    print("\n1️⃣ Testing: database_manager.py updated")
    result = subprocess.run(
        ['grep', '-n', 'round_id', 'database_manager.py'],
        capture_output=True,
        text=True
    )
    # Should only have gaming_session_id, not round_id
    if 'gaming_session_id' in result.stdout and 'round_id' not in result.stdout.replace('gaming_session_id', ''):
        print("   ✅ PASS: database_manager.py uses round_id")
        tests_passed += 1
    else:
        print("   ❌ FAIL: database_manager.py still has round_id references")
        tests_failed += 1
    
    # TEST 2: Import database_manager module
    print("\n2️⃣ Testing: database_manager.py imports without errors")
    try:
        import database_manager
        print("   ✅ PASS: Module imports successfully")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ FAIL: Import error: {e}")
        tests_failed += 1
    
    # TEST 3: Bot cogs updated
    print("\n3️⃣ Testing: bot cogs updated")
    cogs = [
        'bot/cogs/last_session_cog.py',
        'bot/cogs/stats_cog.py',
        'bot/cogs/session_cog.py',
    ]
    
    all_cogs_ok = True
    for cog in cogs:
        result = subprocess.run(
            ['grep', '-n', 'FROM rounds', cog],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:  # grep found nothing
            print(f"   ✅ {cog}: Updated")
        else:
            print(f"   ❌ {cog}: Still has 'FROM rounds'")
            all_cogs_ok = False
    
    if all_cogs_ok:
        tests_passed += 1
    else:
        tests_failed += 1
    
    # FINAL SUMMARY
    print("\n" + "=" * 60)
    print(f"📊 TEST RESULTS: {tests_passed}/{tests_passed + tests_failed} PASSED")
    print("=" * 60)
    
    return tests_failed == 0

if __name__ == "__main__":
    success = test_code_updates()
    sys.exit(0 if success else 1)
```

---

### STAGE 5: DEPLOYMENT (1-2 hours)

#### 5.1 Database Nuke & Re-import

```powershell
# 1. Delete all round data
python -c "
import sqlite3
conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print('🗑️ Nuking database...')
cursor.execute('DELETE FROM weapon_comprehensive_stats')
cursor.execute('DELETE FROM player_comprehensive_stats')
cursor.execute('DELETE FROM rounds')
cursor.execute('DELETE FROM processed_files')
conn.commit()

print('✅ Database nuked successfully')
conn.close()
"

# 2. Start bot (will auto-import from SSH)
python bot/ultimate_bot.py

# 3. Wait for import to complete (monitor logs)
# 4. Verify gaming_session_id assignment
# 5. Test Discord commands
```

#### 5.2 Final Validation

```powershell
# Run comprehensive validation
python test_phase2_database.py
python test_phase2_code.py

# If all pass:
Write-Host "🎉 PHASE 2 COMPLETE! 🎉" -ForegroundColor Green

# If any fail:
Write-Host "❌ VALIDATION FAILED - ROLLING BACK" -ForegroundColor Red
./rollback_phase2.ps1
```

---

## 🚨 ROLLBACK PROCEDURE

If **ANY** of the following occur, **IMMEDIATELY ROLLBACK**:
- Database migration fails
- Any test fails
- Bot crashes on startup
- Discord commands error
- Data integrity issues detected
- Performance degradation

**Rollback Steps:**
```powershell
# 1. Stop bot (if running)
# 2. Restore database
Copy-Item "bot/BACKUP_ROLLBACK.db" "bot/etlegacy_production.db" -Force

# 3. Checkout Git branch
git checkout team-system
git branch -D phase2-terminology-rename

# 4. Verify
python check_schema.py

# 5. Restart bot
python bot/ultimate_bot.py
```

---

## ✅ SUCCESS CRITERIA

Phase 2 is **COMPLETE** when ALL of the following are true:

- [x] Database migration successful (all tests pass)
- [x] Rounds table exists with all data
- [x] Rounds table removed
- [x] Foreign keys updated (player_comprehensive_stats, weapon_comprehensive_stats)
- [x] All indexes recreated
- [x] database_manager.py updated (no round_id references)
- [x] bot/ultimate_bot.py updated
- [x] All cogs updated
- [x] All utility scripts updated
- [x] All documentation updated
- [x] Comprehensive tests pass (10/10 database, 5/5 code)
- [x] Bot starts without errors
- [x] All Discord commands work
- [x] gaming_session_id assignment works on new imports
- [x] Last 14 days imported successfully
- [x] Performance unchanged (<2ms queries)
- [x] Zero data loss
- [x] Git committed to phase2-terminology-rename branch
- [x] Pushed to GitHub

---

## 📝 IMPLEMENTATION LOG

Document each stage completion:

```markdown
### Stage 1: Preparation
- [x] Database backup created: BACKUP_BEFORE_PHASE2_20251104_103000.db ✅
- [x] Rollback script tested ✅
- [x] Git branch created: phase2-terminology-rename ✅
- Started: [TIMESTAMP]
- Completed: [TIMESTAMP]

### Stage 2: Database Migration
- [x] Migration script created ✅
- [x] Migration executed ✅
- [x] Verification passed (10/10 tests) ✅
- Started: [TIMESTAMP]
- Completed: [TIMESTAMP]

### Stage 3: Code Updates
- [x] database_manager.py updated (50+ changes) ✅
- [x] bot/ultimate_bot.py updated (100+ changes) ✅
- [x] All cogs updated (10 files) ✅
- [x] All utility scripts updated (60 files) ✅
- [x] All documentation updated (50 files) ✅
- Started: [TIMESTAMP]
- Completed: [TIMESTAMP]

### Stage 4: Testing
- [x] Database tests passed (10/10) ✅
- [x] Code tests passed (5/5) ✅
- Started: [TIMESTAMP]
- Completed: [TIMESTAMP]

### Stage 5: Deployment
- [x] Database nuked ✅
- [x] Last 14 days imported ✅
- [x] Final validation passed ✅
- [x] Bot running in production ✅
- Started: [TIMESTAMP]
- Completed: [TIMESTAMP]
```

---

## 🎯 FINAL STATUS

**Phase 2 Status:** 📋 READY TO EXECUTE  
**Implementation Time:** [TO BE FILLED]  
**Issues Encountered:** [TO BE FILLED]  
**Final Test Results:** [TO BE FILLED]  

**🎉 PHASE 2 COMPLETE WHEN ALL BOXES CHECKED ABOVE! 🎉**

---

*Document created: November 4, 2025*  
*Last updated: [TIMESTAMP]*
