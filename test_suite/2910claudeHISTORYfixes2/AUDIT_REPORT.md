# ET:LEGACY STATS PARSER - COMPREHENSIVE AUDIT REPORT
**Date**: October 29, 2025  
**Project**: slomix-stats / etlegacy-discord-bot  
**Auditor**: Claude (Anthropic)

## EXECUTIVE SUMMARY

This audit examined the ET:Legacy stats ingestion and parser pipeline (SSH → local_stats → parser → DB import → processed_files → Discord). **7 bugs were identified** (one initial concern was found to NOT be a bug), with 2 HIGH-PRIORITY bugs causing complete data loss and incorrect statistics. Fixes have been developed and tested for the critical bugs.

### Critical Findings
- 🔴 **BUG #1**: Float parsing error causing **ALL damage data to be lost**
- 🔴 **BUG #2**: Round 2 files processed with cumulative stats instead of differential
- 🔴 **BUG #7**: No database transaction handling - partial writes can cause data loss

---

## BUG INVENTORY

### 🔴 HIGH PRIORITY (Fix Immediately)

#### BUG #1: Float Parsing in Extended Stats [CRITICAL]
**Status**: FIXED  
**Severity**: HIGH - Data Loss  
**Impact**: ALL damage, XP, and objective stats are lost

**Description**:
The parser attempts to parse float values as integers in the extended stats section. Fields like `xp` (0.0), `time_played` (82.5), `kd` (2.4), etc. are formatted as floats in c0rnp0rn7.lua but parsed as ints in Python, causing `ValueError` and defaulting all extended stats to 0.

**Affected Fields**:
- `time_played` (tab_fields[8])
- `planted` (tab_fields[21])
- `xp` (tab_fields[22])
- `combatxp` (tab_fields[23])
- `time_axis` (tab_fields[24])
- `time_allies` (tab_fields[25])
- `kd` (tab_fields[26])

**Evidence**:
```
⚠️ Warning: Failed to parse extended stats for vid: invalid literal for int() with base 10: '0.0'
Player: vid
Damage Given: 0  # Should be 639!
```

**Root Cause**:
```python
# WRONG - Line ~460 in community_stats_parser.py
additional_stats = {
    'xp': int(tab_fields[22]),  # ❌ Trying to parse float as int!
}
```

**Fix**:
```python
# CORRECT - Use float() for float fields
additional_stats = {
    'time_played': float(tab_fields[8]),
    'planted': float(tab_fields[21]),
    'xp': float(tab_fields[22]),
    'combatxp': float(tab_fields[23]),
    'time_axis': float(tab_fields[24]),
    'time_allies': float(tab_fields[25]),
    'kd': float(tab_fields[26]),
}
```

**Test Results**:
```
BEFORE FIX:
  1. bronze.: 5K/3D (K/D: 1.67, Damage: 0, DPM: 0.0)  ❌

AFTER FIX:
  1. bronze.: 5K/3D (K/D: 1.67, Damage: 1166, DPM: 485.8)  ✅
```

---

#### BUG #2: Round 2 File Matching [CRITICAL]
**Status**: FIXED  
**Severity**: HIGH - Wrong Data  
**Impact**: Round 2 stats include Round 1 data (cumulative instead of differential)

**Description**:
The `find_corresponding_round_1_file()` function fails to locate Round 1 files when the Round 2 file path has no directory component. This causes Round 2 files to be processed with cumulative stats (Round 1 + Round 2 combined) instead of Round 2-only differential stats.

**Evidence**:
```
🔍 Detected Round 2 file: 2025-10-23-222205-te_escape2-round-2.txt
⚠️ Warning: Could not find Round 1 file for 2025-10-23-222205-te_escape2-round-2.txt
   Parsing as regular file (cumulative stats will be included)
❌ FAIL: Round 2 file processed without differential calculation
```

**Root Cause**:
```python
# WRONG - Line ~182 in community_stats_parser.py
def find_corresponding_round_1_file(self, round_2_file_path: str) -> Optional[str]:
    filename = os.path.basename(round_2_file_path)
    directory = os.path.dirname(round_2_file_path)  # Empty string if no path!
    
    # Empty directory means glob pattern looks in '' which fails
    search_pattern = f"{date}-*-{map_name}-round-1.txt"
    pattern_path = os.path.join(directory, search_pattern)  # '' + pattern = fails
```

**Fix**:
```python
# CORRECT - Default to current directory if no directory in path
def find_corresponding_round_1_file(self, round_2_file_path: str) -> Optional[str]:
    filename = os.path.basename(round_2_file_path)
    directory = os.path.dirname(round_2_file_path)
    
    # FIX: If directory is empty, use current directory
    if not directory:
        directory = "."
```

**Test Results**:
```
BEFORE FIX:
🔍 Detected Round 2 file: 2025-10-23-222205-te_escape2-round-2.txt
⚠️ Warning: Could not find Round 1 file
Differential: False  ❌

AFTER FIX:
🔍 Detected Round 2 file: 2025-10-23-222205-te_escape2-round-2.txt
📂 Found Round 1 file: 2025-10-23-221845-te_escape2-round-1.txt
Differential: True  ✅
```

---

#### BUG #7: Database Write Guarantee [CRITICAL]
**Status**: NOT FIXED (Requires DB schema changes)  
**Severity**: HIGH - Data Loss  
**Impact**: Partial DB writes can cause permanent data loss

**Description**:
The database import process does not wrap writes in transactions. If a write fails partway through (e.g., after session row but before all players), the file is still marked as processed, causing permanent data loss.

**Risk Scenario**:
```
1. Parse file: 2025-10-23-222205-te_escape2-round-2.txt
2. Begin import (NO TRANSACTION):
   - ✅ INSERT INTO sessions VALUES (...)
   - ✅ INSERT INTO player_comprehensive_stats (player 1)
   - ✅ INSERT INTO player_comprehensive_stats (player 2)
   - ❌ INSERT INTO player_comprehensive_stats (player 3) -- DB ERROR!
   - File marked as processed in processed_files table
   - Players 4-6 NEVER WRITTEN!
3. Result: Permanent data loss, can't reprocess file
```

**Evidence**:
```python
# From project knowledge - NO transaction wrapper visible
async def process_gamestats_file(self, local_path, filename):
    stats_data = parser.parse_stats_file(local_path)
    
    # No BEGIN TRANSACTION here!
    async with aiosqlite.connect(self.db_path) as db:
        await db.execute('INSERT INTO sessions...')
        await db.execute('INSERT INTO player_comprehensive_stats...')  # Can fail!
        await db.execute('INSERT INTO processed_files...')  # Marks as done!
```

**Recommended Fix**:
```python
async def process_gamestats_file(self, local_path, filename):
    stats_data = parser.parse_stats_file(local_path)
    
    async with aiosqlite.connect(self.db_path) as db:
        try:
            await db.execute('BEGIN TRANSACTION')
            
            # All DB writes here
            await db.execute('INSERT INTO sessions...')
            for player in stats_data['players']:
                await db.execute('INSERT INTO player_comprehensive_stats...')
            
            # ONLY mark as processed if all writes succeed
            await db.execute('INSERT INTO processed_files...')
            
            await db.execute('COMMIT')
        except Exception as e:
            await db.execute('ROLLBACK')
            logger.error(f"DB import failed: {e}")
            raise  # Don't mark file as processed!
```

---

### 🟡 MEDIUM PRIORITY

#### BUG #3: Round 2 Race Condition
**Severity**: MEDIUM - Timing  
**Impact**: Round 2 may be processed before Round 1 is available

**Description**:
If Round 2 file arrives/is detected before Round 1 file is processed, the differential calculation fails and Round 2 is processed with cumulative stats.

**Scenario**:
```
Time    Event
22:18   Round 1 ends, file created on server
22:19   SSH poll detects Round 1 file, starts download
22:20   Round 1 download completes, queued for processing
22:22   Round 2 ends, file created on server
22:22   SSH poll detects Round 2 file, starts download
22:22   Round 2 download completes, PROCESSED IMMEDIATELY
        ❌ Round 1 not yet in processed_files DB!
        ❌ Round 2 processed without differential
22:23   Round 1 finishes processing
        ❌ TOO LATE! Round 2 already done wrong
```

**Recommended Fix**:
```python
def should_process_file(self, filename):
    # If this is a Round 2 file, check for Round 1 first
    if "-round-2.txt" in filename:
        round_1_file = self.find_round_1_for_round_2(filename)
        if round_1_file and round_1_file not in self.processed_files:
            logger.info(f"Waiting for Round 1 file {round_1_file} before processing Round 2")
            return False  # Defer Round 2 until Round 1 is done
    return True
```

---

#### ~~BUG #4: Player GUID Changes~~ [NOT A BUG]
**Status**: ✅ **RESOLVED** - This is NOT a bug!  
**Severity**: N/A  
**Impact**: None - Stats persist correctly

**Description**:
Initial concern was that player reconnects between rounds could change GUIDs, breaking differential calculation. **However, this is already handled by ET:Legacy engine**.

**Why this works**:
1. All stats are stored in ET:Legacy engine's session data (`sess.damage_given`, `sess.kills`, etc.)
2. c0rnp0rn7.lua just **reads** these stats from the engine, it doesn't manage them
3. The engine maintains session continuity across rounds and reconnects
4. GUIDs remain consistent throughout the match
5. Test data confirms: All 6 players have identical GUIDs in Round 1 and Round 2

**Evidence**:
```
Round 1 GUIDs: D8423F90, 652EB4A6, 7B84BE88, EDBB5DA9, 5D989160, 2B5938F5
Round 2 GUIDs: 7B84BE88, D8423F90, EDBB5DA9, 2B5938F5, 5D989160, 652EB4A6
                ✅ Perfect match!
```

**Credit**: Thanks to the user for pointing out that ET:Legacy engine handles this!

---

#### BUG #6: New File Detection
**Severity**: MEDIUM - Timing  
**Impact**: Files may be processed out of order or missed

**Description**:
SSH monitoring polls every 30 seconds. If multiple files appear between polls, they are processed in alphabetical order, which may not be chronological order.

**Scenario**:
```
22:18:45  Round 1 file created: 2025-10-23-221845-te_escape2-round-1.txt
22:22:05  Round 2 file created: 2025-10-23-222205-te_escape2-round-2.txt
22:22:20  SSH poll detects BOTH files
          Files sorted alphabetically:
          1. 2025-10-23-221845-... (Round 1) ✅ Processed first
          2. 2025-10-23-222205-... (Round 2) ✅ Processed second
          
          This works because timestamps are in filename!
          BUT if filenames were different format, could process out of order.
```

**Recommended Fix**:
```python
async def endstats_monitor(self):
    remote_files = await self.ssh_list_remote_files(ssh_config)
    
    # Sort by timestamp extracted from filename before processing
    def extract_timestamp(filename):
        # Extract YYYY-MM-DD-HHMMSS from filename
        parts = filename.split('-')
        if len(parts) >= 4:
            return parts[3]  # HHMMSS
        return filename
    
    remote_files.sort(key=extract_timestamp)  # Process in chronological order
```

---

#### BUG #8: Double Processing Prevention
**Severity**: MEDIUM - Data Integrity  
**Impact**: Files could be processed twice if cache is stale

**Description**:
The 4-layer check in `should_process_file()` relies on in-memory cache. If bot restarts between processing and cache refresh, cache is empty and file could be re-processed.

**Recommended Fix**:
```python
async def on_ready(self):
    """Load processed files cache on bot startup"""
    async with aiosqlite.connect(self.db_path) as db:
        cursor = await db.execute(
            'SELECT filename FROM processed_files WHERE success = 1'
        )
        rows = await cursor.fetchall()
        self.processed_files = {row[0] for row in rows}
    logger.info(f"Loaded {len(self.processed_files)} processed files into cache")
```

**Also add UNIQUE constraint**:
```sql
ALTER TABLE processed_files ADD CONSTRAINT unique_filename UNIQUE (filename);
```

---

### 🟢 LOW PRIORITY

#### BUG #5: Time Storage Inconsistency
**Severity**: LOW - Code Quality  
**Impact**: Both `time_played_seconds` and `time_played_minutes` stored, may get out of sync

**Description**:
Parser stores time in both seconds (primary) and minutes (deprecated) format. Both are calculated from same source, but could theoretically diverge if code changes.

**Recommended Fix**:
- Document `time_played_minutes` as deprecated
- Remove it in next major version
- Only use `time_played_seconds` for all calculations

---

## REPRODUCTION STEPS

### Setup Test Environment
```bash
# 1. Clone or create test directory
mkdir -p etlegacy-audit
cd etlegacy-audit

# 2. Copy test files (provided in /mnt/project/)
cp /path/to/2025-10-23-*.txt .
cp /path/to/c0rnp0rn7.lua .

# 3. Copy parser code
cp /path/to/community_stats_parser.py .
```

### Test BUG #1: Float Parsing
```bash
# Run parser on any file
python3 community_stats_parser.py

# Expected output (BROKEN):
# ⚠️ Warning: Failed to parse extended stats for vid: invalid literal for int() with base 10: '0.0'
# Damage Given: 0  ❌

# With FIX:
# Damage Given: 639  ✅
```

### Test BUG #2: Round 2 Matching
```bash
# Run parser on Round 2 file
python3 -c "
from community_stats_parser import C0RNP0RN3StatsParser
parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('2025-10-23-222205-te_escape2-round-2.txt')
print(f'Differential: {result.get(\"differential_calculation\", False)}')
"

# Expected output (BROKEN):
# ⚠️ Warning: Could not find Round 1 file
# Differential: False  ❌

# With FIX:
# 📂 Found Round 1 file: 2025-10-23-221845-te_escape2-round-1.txt
# Differential: True  ✅
```

### Run Comprehensive Bug Test Suite
```bash
python3 bug_tests.py

# This runs all 8 bug tests and generates a detailed report
```

---

## EXACT CODE DIFFS

### DIFF #1: Fix Float Parsing (community_stats_parser.py)

**Location**: Line ~460-490 in `parse_player_line()` method

```diff
                         # Basic stats - CORRECT field order from c0rnp0rn3.lua:
                         additional_stats = {
                             'damage_given': int(tab_fields[0]),
                             'damage_received': int(tab_fields[1]),
                             'team_damage_given': int(tab_fields[2]),
                             'team_damage_received': int(tab_fields[3]),
                             'gibs': int(tab_fields[4]),
                             'self_kills': int(tab_fields[5]),
                             'team_kills': int(tab_fields[6]),
                             'team_gibs': int(tab_fields[7]),
-                            'time_played': int(tab_fields[8]),
+                            'time_played': float(tab_fields[8]),  # FLOAT!
                         }

                         objective_stats = {
                             'health_given': int(tab_fields[9]),
                             'revives': int(tab_fields[10]),
                             'ammo_given': int(tab_fields[11]),
                             'construction': int(tab_fields[12]),
                             'demolition': int(tab_fields[13]),
                             'captures': int(tab_fields[14]),
                             'damage_team_given': int(tab_fields[15]),
                             'damage_team_received': int(tab_fields[16]),
                             'poison': int(tab_fields[17]),
                             'teleporter_travel': int(tab_fields[18]),
                             'teleporter_usage': int(tab_fields[19]),
                             'defused': int(tab_fields[20]),
-                            'planted': int(tab_fields[21]),
-                            'xp': int(tab_fields[22]),
-                            'combatxp': int(tab_fields[23]),
-                            'time_axis': int(tab_fields[24]),
-                            'time_allies': int(tab_fields[25]),
-                            'multikill_2': int(tab_fields[26]),
+                            'planted': float(tab_fields[21]),     # FLOAT!
+                            'xp': float(tab_fields[22]),          # FLOAT!
+                            'combatxp': float(tab_fields[23]),    # FLOAT!
+                            'time_axis': float(tab_fields[24]),   # FLOAT!
+                            'time_allies': float(tab_fields[25]), # FLOAT!
+                            'kd': float(tab_fields[26]),          # FLOAT!
+                            'multikill_2': int(tab_fields[27]),
```

### DIFF #2: Fix Round 2 File Matching (community_stats_parser.py)

**Location**: Line ~182-190 in `find_corresponding_round_1_file()` method

```diff
     def find_corresponding_round_1_file(self, round_2_file_path: str) -> Optional[str]:
         """Find the corresponding Round 1 file for a Round 2 file"""
         filename = os.path.basename(round_2_file_path)
         directory = os.path.dirname(round_2_file_path)
+        
+        # FIX: If directory is empty, use current directory
+        if not directory:
+            directory = "."

         # Extract date, map from Round 2 filename: YYYY-MM-DD-HHMMSS-mapname-round-2.txt
         parts = filename.split('-')
         if len(parts) < 6:
             return None
```

### DIFF #3: Add Transaction Support (ultimate_bot.py)

**Location**: Line ~XXX in `process_gamestats_file()` method

```diff
     async def process_gamestats_file(self, local_path, filename):
         """Process a gamestats file: parse and import to database"""
         try:
             from community_stats_parser import C0RNP0RN3StatsParser
             
             parser = C0RNP0RN3StatsParser()
             stats_data = parser.parse_stats_file(local_path)
             
             if not stats_data or stats_data.get('error'):
                 raise Exception(f"Parser error")
             
             async with aiosqlite.connect(self.db_path) as db:
+                try:
+                    await db.execute('BEGIN TRANSACTION')
+                    
                     # Import session
                     await db.execute('INSERT INTO sessions...')
                     
                     # Import players
                     for player in stats_data['players']:
                         await db.execute('INSERT INTO player_comprehensive_stats...')
                     
                     # Mark as processed ONLY if all writes succeed
                     await db.execute('INSERT INTO processed_files...')
+                    
+                    await db.execute('COMMIT')
+                    logger.info(f"✅ Successfully imported {filename}")
+                    
+                except Exception as e:
+                    await db.execute('ROLLBACK')
+                    logger.error(f"❌ DB import failed, rolled back: {e}")
+                    raise  # Re-raise to prevent marking as processed
```

---

## TESTING RESULTS

### Before Fixes
```
Test #1: Float Parsing             ❌ FAIL (damage_given = 0)
Test #2: Round 2 Matching          ❌ FAIL (no Round 1 found)
Test #3: Round 2 Race Condition    ⚠️  DOCUMENTED
Test #4: Player GUID Consistency   ✅ NOT A BUG (engine handles this)
Test #5: Time Storage              ✅ PASS
Test #6: New File Detection        ⚠️  DOCUMENTED
Test #7: DB Write Guarantee        ⚠️  NOT TESTED (needs DB)
Test #8: Double Processing         ⚠️  DOCUMENTED
```

### After Fixes
```
Test #1: Float Parsing             ✅ PASS (damage_given = 639)
Test #2: Round 2 Matching          ✅ PASS (Round 1 found, differential = True)
Test #3: Round 2 Race Condition    ⚠️  DOCUMENTED
Test #4: Player GUID Consistency   ✅ NOT A BUG (engine handles this)
Test #5: Time Storage              ✅ PASS
Test #6: New File Detection        ⚠️  DOCUMENTED
Test #7: DB Write Guarantee        🔴 NOT FIXED (critical!)
Test #8: Double Processing         ⚠️  DOCUMENTED
```

---

## RECOMMENDATIONS (PRIORITIZED)

### Immediate Action Required (Next 24h)
1. **✅ Apply DIFF #1** - Fix float parsing (DONE in test environment)
2. **✅ Apply DIFF #2** - Fix Round 2 matching (DONE in test environment)
3. **🔴 Apply DIFF #3** - Add transaction support (HIGH PRIORITY)
4. **Test thoroughly** - Run bug_tests.py and validate with real data

### Short Term (Next Week)
5. **Add file sorting** - Sort files by timestamp before processing
6. **Add startup cache** - Load processed_files on bot startup
7. **Add UNIQUE constraint** - Prevent duplicate processing at DB level
8. **Add retry logic** - Retry Round 2 if Round 1 not found

### Medium Term (Next Month)
9. **Deprecate time_played_minutes** - Remove in favor of time_played_seconds
10. **Add monitoring/alerts** - Detect when files are skipped or processed wrong
11. **Add data validation** - Sanity checks on parsed stats before DB import
12. **Improve error handling** - Better logging and recovery from failures

---

## FILES DELIVERED

1. `community_stats_parser.py` - Original parser (with bugs)
2. `community_stats_parser_FIXED.py` - Fixed parser (Bugs #1 and #2 resolved)
3. `bug_tests.py` - Comprehensive test suite for all 8 bugs
4. `AUDIT_REPORT.md` - This report

---

## CONCLUSION

The ET:Legacy stats parser has **2 critical bugs causing data loss and incorrect statistics**. Both have been fixed and tested. One initial concern (BUG #4: GUID changes) was found to NOT be a bug - the ET:Legacy engine handles session persistence perfectly. The most urgent remaining issue is lack of database transactions (Bug #7), which could cause permanent data loss if writes fail partway through.

**Recommended immediate action**: Deploy fixes for Bugs #1 and #2, then implement transaction support (Bug #7) before processing any more production data.

---

**Report Generated**: October 29, 2025  
**Audit Status**: COMPLETE  
**Bugs Found**: 7 (1 false positive eliminated)  
**Fixes Status**: 2/7 IMPLEMENTED, 5/7 DOCUMENTED
