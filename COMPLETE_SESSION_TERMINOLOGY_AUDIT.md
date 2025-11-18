# COMPLETE SESSION TERMINOLOGY AUDIT REPORT
# Date: November 4, 2025
# Total Files Scanned: 100+
# Critical Issues Found: FUNDAMENTAL ARCHITECTURE PROBLEM

## EXECUTIVE SUMMARY

**The Problem:** Day 0 terminology mistake affects entire codebase
- Database table named `rounds` actually stores **ROUNDS**
- Column named `round_id` actually means **round_id**
- No `gaming_session_id` exists
- Bot uses 30-minute gap workaround (should be 60 minutes)
- 231 database "rounds" = actually 231 **rounds**
- Example: Oct 19 has 23 "rounds" = should be 1 gaming session

**Impact:** HIGH - Affects database schema, bot logic, all queries, documentation

**Recommended Fix:** Phase 1 (Add gaming_session_id) → Phase 2 (Rename for clarity)

---

## CORRECT TERMINOLOGY

### 1. ROUND
- **Definition:** Single R1 or R2 file from one map
- **Example:** `2025-10-14_212256_R1_et_bremen_a2.txt`
- **Database:** Should be one row in `rounds` table (currently called `rounds`)
- **Duration:** ~12 minutes

### 2. MATCH  
- **Definition:** R1 + R2 pair on same map (both teams attack/defend)
- **Example:** et_bremen_a2 R1 (21:22) + R2 (21:44) = 1 match
- **Database:** Linked by `match_id` field ✅ (CORRECT)
- **Duration:** ~24 minutes (two rounds)

### 3. GAMING SESSION
- **Definition:** Entire night of continuous gameplay
- **Example:** Oct 14, 21:22-23:56 = 12 matches = 24 rounds = **1 gaming session**
- **Database:** Should have `gaming_session_id` column ❌ (MISSING)
- **Gap Threshold:** 60 minutes between files = new gaming session
- **Duration:** ~2-3 hours typical

---

## CRITICAL FILES REQUIRING CHANGES

### 🔥 PRIORITY 1: Core Database Layer

#### database_manager.py (1,139 lines)
**Status:** Uses "session" to mean "round" throughout entire file  
**Occurrences:** 50+ instances

**Schema Issues:**
```python
# Line 177-191: Wrong table name
CREATE TABLE rounds (  # ❌ Should be "rounds"
    id INTEGER PRIMARY KEY,  # ❌ This is round_id, not round_id
    round_date TEXT,
    round_time TEXT,
    match_id TEXT,  # ✅ CORRECT - pairs R1+R2
    map_name TEXT,
    round_number INTEGER,  # ✅ Proves it's rounds!
    winner_team INTEGER,
    defender_team INTEGER,
    is_tied INTEGER,
    round_outcome TEXT,
    map_id INTEGER,
    original_time_limit TEXT,
    time_to_beat TEXT,
    completion_time TEXT,
    created_at TEXT
)
```

**Foreign Key Issues:**
```python
# Line 200, 269: player_comprehensive_stats
round_id INTEGER NOT NULL,  # ❌ Actually round_id
FOREIGN KEY (round_id) REFERENCES sessions(id)  # ❌ round_id → rounds(id)

# Line 281, 295: weapon_comprehensive_stats
round_id INTEGER NOT NULL,  # ❌ Actually round_id
FOREIGN KEY (round_id) REFERENCES sessions(id)  # ❌ round_id → rounds(id)
```

**Constraint Issues:**
```python
# Line 272: player_comprehensive_stats
UNIQUE(round_id, player_guid)  # ❌ Actually unique by (round_id, player_guid)

# Line 298: weapon_comprehensive_stats
UNIQUE(round_id, player_guid, weapon_name)  # ❌ round_id constraint
```

**Index Issues:**
```python
# Line 359-363: Wrong names
CREATE INDEX idx_sessions_date_map ON sessions(round_date, map_name)  # ❌ rounds table
CREATE INDEX idx_sessions_match_id ON sessions(match_id)  # ❌ rounds table
CREATE INDEX idx_player_stats_session ON player_comprehensive_stats(round_id)  # ❌ round_id
CREATE INDEX idx_weapon_stats_session ON weapon_comprehensive_stats(round_id)  # ❌ round_id
```

**Function Names (All Wrong):**
- Line 486: `def create_session()` → Should be `create_round()`
- Line 535: `def insert_player_stats(round_id...)` → Parameter is round_id
- Line 642: `def insert_weapon_stats(round_id...)` → Parameter is round_id
- Line 387: `def _find_or_create_match_id(round_time...)` → ✅ CORRECT usage

**SQL Queries (50+ instances):**
- Line 107: `SELECT name FROM sqlite_master WHERE type='table' AND name='rounds'`
- Line 500: `SELECT id FROM rounds WHERE match_id = ? AND round_number = ?`
- Line 513: `INSERT INTO rounds (...) VALUES (...)`
- Line 895: `DELETE FROM rounds WHERE round_date BETWEEN ? AND ?`
- Line 951: `SELECT COUNT(*) FROM rounds`
- Line 967: `SELECT MIN(round_date), MAX(round_date) FROM rounds`
- Line 972: `SELECT COUNT(*) FROM rounds s LEFT JOIN player_comprehensive_stats p ON p.round_id = s.id WHERE p.round_id IS NULL`
- Line 980: `SELECT COUNT(*) FROM rounds s LEFT JOIN weapon_comprehensive_stats w ON w.round_id = s.id WHERE w.round_id IS NULL`

**Statistics Variables (All Wrong):**
- Line 71: `'sessions_created': 0` → Actually `rounds_created`
- Line 522: `self.stats['sessions_created'] += 1` → Counting rounds
- Line 815: `f"Sessions created: {self.stats['sessions_created']:,}"` → Reporting rounds
- Line 898: `sessions_deleted = cursor.rowcount` → rounds_deleted
- Line 909: `f"Deleted {sessions_deleted:,} sessions"` → Deleted rounds
- Line 976: `orphan_sessions = cursor.fetchone()[0]` → orphan_rounds
- Line 984: `no_weapon_sessions = cursor.fetchone()[0]` → no_weapon_rounds
- Line 989: `'rounds': round_count` → 'rounds': round_count
- Line 994: `'orphan_sessions': orphan_sessions` → orphan_rounds
- Line 995: `'no_weapon_sessions': no_weapon_sessions` → no_weapon_rounds
- Line 1000: `f"Sessions: {round_count:,}"` → Rounds count
- Line 1005: `f"Orphan sessions: {orphan_sessions:,}"` → Orphan rounds
- Line 1006: `f"No weapon sessions: {no_weapon_sessions:,}"` → No weapon rounds

**Comments/Documentation (Misleading):**
- Line 174: "# 1. Rounds table" → Should say "Rounds table"
- Line 175: `logger.info("   Creating rounds table...")` → Creating rounds table
- Line 970: "# Check for sessions without players" → Rounds without players
- Line 978: "# Check for sessions without weapons" → Rounds without weapons

---

### 🔥 PRIORITY 1: Bot Commands Layer

#### bot/cogs/last_session_cog.py (2,417 lines)
**Status:** Manually groups rounds using 30min gap (should use gaming_session_id)  
**Occurrences:** 60+ instances mixing terminology

**Gap Threshold Issues (CRITICAL):**
```python
# Line 120-126: WRONG THRESHOLD!
gap_minutes = (last_datetime - sess_datetime).total_seconds() / 60
if gap_minutes <= 30:  # ❌ Should be 60 minutes!
    gaming_session_ids.insert(0, sess[0])
else:
    break  # Gap too large - different gaming session

# Line 174-180: Another 30min check
gap_minutes = (sess_datetime - last_datetime).total_seconds() / 60
if gap_minutes <= 30:  # ❌ Should be 60 minutes!
    continuation_sessions.append(sess)
```

**SQL Queries (All reference wrong table/column names):**
```python
# Line 52-56: Queries rounds table
SELECT s.round_date FROM rounds s
WHERE EXISTS (SELECT 1 FROM player_comprehensive_stats p WHERE p.round_id = s.id)

# Line 82-85: Gets last round (calls it "session")
FROM rounds WHERE round_date = ? ORDER BY round_time DESC LIMIT 1

# Line 107-111: Gets previous rounds
FROM rounds WHERE round_date >= ? AND id < ? ORDER BY round_time DESC

# Line 136-140: Fetches rounds for gaming session
FROM rounds WHERE id IN ({session_ids_str}) ORDER BY round_time

# Line 160-165: Next day rounds
FROM rounds WHERE round_date = ? AND id > ? ORDER BY round_time

# Line 194-196: Player count query
WHERE round_id IN ({session_ids_str})

# Line 221-223: Date range query
FROM rounds WHERE id IN (?)

# All view functions query by round_id (actually round_id):
# Line 302, 315, 408, 456, 458, 505, 543, 587
```

**Variable Names (Confusing Mix):**
```python
# Line 92: Actually last_round_id
last_session_id = last_round[0]

# Line 98: CORRECT name (but built from round IDs)
gaming_session_ids = [last_session_id]

# Line 131: Actually round_ids_str
session_ids_str = ','.join(str(sid) for sid in gaming_session_ids)

# Line 141: Actually fetching rounds
primary_sessions = await cursor.fetchall()

# Line 147-149: Actually round IDs
last_session_id = primary_sessions[-1][0]
last_session_date = primary_sessions[-1][4]
last_session_time = primary_sessions[-1][5]

# Line 168: Actually next_day_rounds
next_day_sessions = await cursor.fetchall()

# Line 171: Actually continuation_rounds
continuation_sessions = []

# Line 184: Actually all_rounds
all_sessions = primary_sessions + continuation_sessions

# Line 185: Actually rounds data
sessions = [(s[0], s[1], s[2], s[3]) for s in all_sessions]

# Line 187-188: Actually round_ids
session_ids = [s[0] for s in sessions]
session_ids_str = ",".join("?" * len(session_ids))
```

**Function Parameters (All wrong names):**
```python
# Line 65: Returns round data, calls them sessions
async def _fetch_session_data(self, db, latest_date: str) -> Tuple[List, List, str, int]:

# Line 201: session_ids parameter actually contains round_ids
async def _get_hardcoded_teams(self, db, session_ids: List[int]) -> Optional[Dict]:

# Line 293: session_ids_str parameter actually round_ids_str
async def _show_objectives_view(self, ctx, db, latest_date: str, session_ids: List, session_ids_str: str, player_count: int):

# All other view functions have same issue:
# Lines 392, 446, 496, 531, 571
```

**Comments (Confusing Terminology):**
```python
# Line 44: Correct
"Get the most recent gaming session date from database."

# Line 67-71: Correct intent, wrong implementation
"Fetch all round data for the LAST gaming session.
We can't rely on round_date alone because there might be multiple
gaming sessions on the same day, so we use time-based logic,
grouping sessions that are within 30 minutes of each other.
This properly handles multiple gaming sessions on the same day."

# Line 78: Wrong - gets last ROUND
"Get the absolute last session (most recent by date and time)"

# Line 97: Wrong - "rounds" are rounds
"Now work BACKWARDS, collecting sessions within 30min gaps"

# Line 101: Wrong - "rounds" are rounds
"Get recent sessions before the last one (limit search to same day + previous day)"

# Line 116: Wrong - checking rounds
"Work backwards through sessions, stop at first gap > 30 minutes"

# Line 130: Mixing terms
"Now fetch full round data for the gaming session"

# Line 146: Wrong - rounds after midnight
"Check for sessions after midnight (next day)"

# Line 156: Wrong - rounds from next day
"Get sessions from next day that might be part of same gaming session"

# Line 170: Wrong - rounds within 30min
"Include next-day sessions if they're within 30min of last session"

# Line 183: Wrong - combining rounds
"Combine all rounds"

# Line 205-208: Correct concept, wrong implementation
"NOTE: Queries by date range of the gaming session rounds.
Args:
    session_ids: List of session IDs (rounds) for this gaming session"
```

---

## MEDIUM PRIORITY FILES

### Analysis/Utility Scripts (Need Updates After Schema Change)

#### list_all_sessions.py
**Queries rounds table:** Lines 27, 66, 90  
**Uses round_id:** Lines 67, 73, 91, 97  
**Impact:** Will break when table renamed

#### check_database_health.py
**Queries rounds table:** Lines 37, 82  
**Checks schema:** Line 37 `PRAGMA table_info(sessions)`  
**Counts sessions:** Lines 134, 137, 139  
**Expected tables:** Line 49 mentions 'gaming_sessions' - CORRECT!  
**Impact:** Medium - diagnostic script

#### check_session_terminology.py
**PURPOSE:** ✅ THIS FILE ALREADY IDENTIFIES THE PROBLEM!
```python
# Line 103-117: Correctly explains the issue
"""
ISSUE IDENTIFIED:
- ROUND = One R1 or R2 file
- MATCH = R1 + R2 on same map (both teams play)
- GAMING SESSION = When you sit down, play multiple maps/rounds, then log off
- Can have multiple gaming sessions in one day

But database has:
- 'rounds' table but it stores ROUNDS, not gaming sessions
- 'round_date' field (format: YYYY-MM-DD) but multiple rounds per date
- No way to distinguish:
  - Morning gaming session vs Evening gaming session
  - Multiple separate play sessions on same date

Need a 'gaming_session_id' with timestamp to group continuous play periods!
"""
```

#### backfill_session_winners.py
**Function name:** Line 13 `def backfill_session_winners()` → Should be `backfill_round_winners()`  
**Queries:** Lines 21, 43  
**Variables:** Lines 26, 28, 34, 46, 51  
**Impact:** Will need rename after schema change

#### backfill_team_history.py
**Function names:** Lines 130 `backfill_session()`, 219 `backfill_all_sessions()`  
**Comments:** Lines 5, 8, 109-110, 220, 224, 226, 236  
**Impact:** High - references session concepts correctly but queries rounds table

#### add_team_history_tables.py
**Comments:** Lines 5, 13, 20, 48, 109-110  
**Schema:** Line 48 `total_rounds INTEGER` - actually total_rounds  
**Impact:** Medium - team tracking across rounds

#### analyze_gaming_sessions.py
**PURPOSE:** ✅ CORRECT - Analyzes full gaming sessions by date  
**Function:** Line 13 `def analyze_gaming_session(date)` - ✅ CORRECT  
**Comment:** Line 6 defines gaming session correctly  
**Queries:** Line 25 `FROM rounds` but correctly treats them as rounds  
**Impact:** Low - already uses correct terminology

#### analytics/synergy_detector.py
**Queries rounds table:** Lines 211-213  
**Uses round_id:** Lines 206, 212-213, 225, 253, 255-256, 288, 290, 293, 307-308  
**Impact:** Medium - player synergy analysis

#### Map/Time Scripts
- `add_map_id_column.py` - Lines 17, 36, 72, 88
- `add_map_id.py` - Line 7
- `add_time_tracking_columns.py` - Lines 23, 28, 33, 43, 53, 66, 69
- `calculate_map_scores.py` - Lines 19, 50
- `backfill_time_values.py` - Lines 121, 147, 176

**Impact:** Low - will work after schema change, just need new column references

---

## LOW PRIORITY FILES

### Database Maintenance Scripts
- `check_all_databases.py` - Counts sessions
- `copy_db_to_bot.py` - Copies database
- `run_proper_import.py` - Import utility
- `proper_fix_clear_and_reimport.py` - Rebuild script
- `proper_rebuild.py` - Rebuild script

**Impact:** Low - maintenance scripts, easy to update

### Investigation/Debugging Scripts (Historical)
- `investigate_db.py`
- `investigate_missing_data.py`
- `check_session_id_conflict.py`
- `check_brewdog_duplicates.py`
- `find_lost_sessions.py`
- `analyze_nov2_stats.py`
- `analyze_oct28_oct30.py`
- `validate_data_accuracy.py`

**Impact:** Very Low - one-time debugging scripts

### Test Files
- `test_round_pairing.py` - Line 81 comment

**Impact:** None - just documentation

---

## MIGRATION PLAN

### PHASE 1: Add Gaming Round Tracking (Non-Breaking) ⏱️ 2-4 hours

**Goal:** Add gaming_session_id without breaking existing code

#### Step 1: Add Column to Database
```python
# In database_manager.py or migration script
cursor.execute("ALTER TABLE sessions ADD COLUMN gaming_session_id INTEGER")
conn.commit()
```

#### Step 2: Create Backfill Algorithm (60-minute gap logic)
```python
def calculate_gaming_session_ids():
    """
    Assign gaming_session_id to all rounds based on 60-minute gap threshold.
    """
    # Get all rounds sorted by date + time
    rounds = cursor.execute("""
        SELECT id, round_date, round_time
        FROM rounds
        ORDER BY round_date, round_time
    """).fetchall()
    
    gaming_session_id = 1
    last_datetime = None
    updates = []
    
    for round_id, date, time in rounds:
        current_datetime = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H%M%S")
        
        if last_datetime:
            gap_minutes = (current_datetime - last_datetime).total_seconds() / 60
            if gap_minutes > 60:  # 60-minute threshold
                gaming_session_id += 1
        
        updates.append((gaming_session_id, round_id))
        last_datetime = current_datetime
    
    # Bulk update
    cursor.executemany(
        "UPDATE sessions SET gaming_session_id = ? WHERE id = ?",
        updates
    )
    conn.commit()
```

#### Step 3: Update Bot to Use gaming_session_id
```python
# In bot/cogs/last_session_cog.py

# OLD CODE (Lines 78-130): Manual 30min gap grouping
# DELETE entire gap logic section

# NEW CODE:
async def _fetch_session_data(self, db, latest_date: str):
    """Get last gaming session by gaming_session_id"""
    
    # Get the most recent gaming_session_id
    async with db.execute("""
        SELECT DISTINCT gaming_session_id
        FROM rounds
        WHERE round_date = ?
        ORDER BY gaming_session_id DESC
        LIMIT 1
    """, (latest_date,)) as cursor:
        result = await cursor.fetchone()
    
    if not result:
        return [], [], "", 0
    
    latest_gaming_session_id = result[0]
    
    # Get all rounds for this gaming session
    async with db.execute("""
        SELECT id, map_name, round_number, match_id
        FROM rounds
        WHERE gaming_session_id = ?
        ORDER BY round_time
    """, (latest_gaming_session_id,)) as cursor:
        sessions = await cursor.fetchall()
    
    session_ids = [s[0] for s in sessions]
    # ... rest of function
```

#### Step 4: Change Gap Threshold (If Keeping Manual Logic as Backup)
```python
# Change all instances of:
if gap_minutes <= 30:  # OLD
# To:
if gap_minutes <= 60:  # NEW
```

#### Step 5: Test Phase 1
- [ ] Verify gaming_session_id assigned correctly to all 231 rounds
- [ ] Test Oct 19: All 23 rounds should have same gaming_session_id
- [ ] Test !last_round command shows correct gaming session
- [ ] Test midnight-crossing (rounds after midnight get same gaming_session_id)
- [ ] Import new files and verify gaming_session_id assigned

---

### PHASE 2: Rename for Clarity (Breaking) ⏱️ 8-12 hours

**Goal:** Fix terminology everywhere (breaking change, requires comprehensive testing)

#### Step 1: Rename Database Tables/Columns
```sql
-- Rename rounds table to rounds
ALTER TABLE sessions RENAME TO rounds;

-- Rename round_id to round_id in foreign keys
-- (SQLite doesn't support ALTER COLUMN, need to recreate tables)
-- Use database migration script

-- Update indexes
CREATE INDEX idx_rounds_date_map ON rounds(round_date, map_name);
CREATE INDEX idx_rounds_match_id ON rounds(match_id);
CREATE INDEX idx_player_stats_round ON player_comprehensive_stats(round_id);
CREATE INDEX idx_weapon_stats_round ON weapon_comprehensive_stats(round_id);
```

#### Step 2: Update database_manager.py
- Rename all functions: `create_session()` → `create_round()`
- Rename all variables: `round_id` → `round_id`
- Rename all statistics: `sessions_created` → `rounds_created`
- Update all SQL queries: `rounds` → `rounds`
- Update all comments

#### Step 3: Update Bot Cogs
- Update all SQL queries
- Rename variables
- Update comments

#### Step 4: Update All Utility Scripts
- 60+ files need updates
- Mostly find/replace: `rounds` → `rounds`, `round_id` → `round_id`

#### Step 5: Comprehensive Testing
- [ ] Import new files
- [ ] All bot commands work
- [ ] All queries return correct data
- [ ] No broken foreign keys
- [ ] Analytics scripts work

---

### PHASE 3: Proper Structure (Future) ⏱️ 16-24 hours

**Goal:** Create proper 3-tier architecture

#### Create New Tables
```sql
CREATE TABLE gaming_sessions (
    id INTEGER PRIMARY KEY,
    start_date TEXT,
    start_time TEXT,
    end_date TEXT,
    end_time TEXT,
    total_rounds INTEGER,
    total_matches INTEGER,
    duration_minutes INTEGER,
    created_at TEXT
);

CREATE TABLE matches (
    id INTEGER PRIMARY KEY,
    gaming_session_id INTEGER,
    match_id TEXT,  -- Links R1+R2
    map_name TEXT,
    map_id INTEGER,
    date TEXT,
    r1_round_id INTEGER,
    r2_round_id INTEGER,
    winner_team INTEGER,
    created_at TEXT,
    FOREIGN KEY (gaming_session_id) REFERENCES gaming_sessions(id),
    FOREIGN KEY (r1_round_id) REFERENCES rounds(id),
    FOREIGN KEY (r2_round_id) REFERENCES rounds(id)
);

CREATE TABLE rounds (
    id INTEGER PRIMARY KEY,
    match_id INTEGER,
    gaming_session_id INTEGER,
    round_number INTEGER,  -- 1 or 2
    map_name TEXT,
    map_id INTEGER,
    date TEXT,
    time TEXT,
    winner_team INTEGER,
    defender_team INTEGER,
    is_tied INTEGER,
    round_outcome TEXT,
    original_time_limit TEXT,
    time_to_beat TEXT,
    completion_time TEXT,
    created_at TEXT,
    FOREIGN KEY (match_id) REFERENCES matches(id),
    FOREIGN KEY (gaming_session_id) REFERENCES gaming_sessions(id)
);
```

---

## SUMMARY STATISTICS

**Files Requiring Changes:**
- Critical (MUST fix): 2 files (database_manager.py, last_session_cog.py)
- High priority: 15+ files (analysis scripts, backfill scripts)
- Medium priority: 30+ files (utility scripts)
- Low priority: 40+ files (one-time debugging scripts)

**Total "session" Occurrences:** 800+ across all files

**Recommended Approach:**
1. **Phase 1 FIRST** - Add gaming_session_id (non-breaking, 2-4 hours)
2. Test thoroughly with existing bot
3. **Phase 2 LATER** - Rename for clarity (breaking, 8-12 hours)
4. **Phase 3 FUTURE** - Proper 3-tier structure (enhancement, 16-24 hours)

**Critical Path:**
```
Phase 1 → Test → Deploy to production bot
    ↓
Phase 2 → Test → Full schema refactor
    ↓
Phase 3 → Test → Enhanced architecture
```

**Risk Assessment:**
- Phase 1: Low risk (adds column, doesn't break existing code)
- Phase 2: High risk (breaks all queries, needs comprehensive testing)
- Phase 3: Medium risk (new tables, but additive)

---

## NEXT STEPS

1. ✅ **Complete this audit** (DONE)
2. ⏳ **Implement Phase 1** - Add gaming_session_id column
3. ⏳ **Create backfill script** - Calculate gaming_session_id for 231 rounds
4. ⏳ **Test backfill** - Verify Oct 19 has 23 rounds with same gaming_session_id
5. ⏳ **Update bot** - Change last_session_cog.py to use gaming_session_id
6. ⏳ **Test bot** - Verify !last_round works correctly
7. ⏳ **Deploy Phase 1** - Push to production
8. ⏳ **Plan Phase 2** - Create detailed migration plan for rename
9. ⏳ **Review with user** - Get approval before Phase 2
10. ⏳ **Document changes** - Update README, CHANGELOG

---

## GLOSSARY FOR FUTURE REFERENCE

**CORRECT TERMS:**
- `rounds` table (stores individual R1/R2 files)
- `round_id` (primary key of rounds table)
- `match_id` (pairs R1+R2 on same map)
- `gaming_session_id` (groups continuous play)

**DEPRECATED TERMS (After Phase 2):**
- ~~`rounds` table~~ → Use `rounds` table
- ~~`round_id`~~ → Use `round_id`
- ~~`create_session()`~~ → Use `create_round()`

**ALWAYS CORRECT TERMS:**
- `match_id` ✅ (Already correct)
- `gaming session` ✅ (Correct concept)
- `round_number` ✅ (Already correct - shows R1 or R2)

---

END OF AUDIT REPORT
