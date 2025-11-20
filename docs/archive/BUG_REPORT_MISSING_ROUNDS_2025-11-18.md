# 🐛 BUG REPORT: Missing Rounds Due to Transaction Isolation Issue

**Date:** 2025-11-18
**Severity:** HIGH
**Status:** CONFIRMED - Data Loss Detected

---

## 📋 SUMMARY

2 rounds from the 2025-11-16 gaming session are marked as "processed" in `processed_files` table but the actual round data was never inserted into the database. This confirms the **Transaction Isolation Bug** previously documented in bug fix logs.

---

## 🔍 EVIDENCE

### Files vs Database Mismatch

**Files on Disk (local_stats/):**
```
✅ 2025-11-16-230757-te_escape2-round-1.txt  (IN DATABASE)
✅ 2025-11-16-231621-te_escape2-round-2.txt  (IN DATABASE)
❌ 2025-11-16-232328-te_escape2-round-1.txt  (MISSING FROM DATABASE!)
❌ 2025-11-16-232817-te_escape2-round-2.txt  (MISSING FROM DATABASE!)
```

**processed_files Table:**
```sql
SELECT filename FROM processed_files
WHERE filename LIKE '%2025-11-16-232%te_escape2%';

-- Returns:
2025-11-16-232328-te_escape2-round-1.txt  ✓ (marked success)
2025-11-16-232817-te_escape2-round-2.txt  ✓ (marked success)
```

**rounds Table:**
```sql
SELECT round_time, map_name, round_number FROM rounds
WHERE round_date = '2025-11-16' AND map_name = 'te_escape2'
ORDER BY round_time;

-- Returns ONLY:
230757 - te_escape2 - R1
231621 - te_escape2 - R2
231621 - te_escape2 - R0

-- MISSING:
-- 232328 - te_escape2 - R1  ❌
-- 232817 - te_escape2 - R2  ❌
```

---

## 🎯 ROOT CAUSE

**Transaction Isolation Bug** (documented in BUGFIX_SESSION_NOV3_2025.md):

1. File download begins transaction
2. Stats are parsed
3. **`mark_file_processed()` is called INSIDE the transaction**
4. File is marked as "success=TRUE" in `processed_files`
5. **Main transaction FAILS or ROLLBACKS**
6. `processed_files` update persists (separate transaction)
7. **Result:** File marked processed, but data never saved

### Code Location

File: `postgresql_database_manager.py` (lines need review)

**Problematic pattern:**
```python
async with transaction:
    # Parse and insert data
    await insert_round(data)
    await insert_player_stats(data)
    await mark_file_processed(filename, success=True)  # ❌ WRONG!
    # If transaction fails here, mark persists but data doesn't
```

**Correct pattern:**
```python
try:
    async with transaction:
        # Parse and insert data
        await insert_round(data)
        await insert_player_stats(data)
        # Don't mark until transaction commits

    # AFTER transaction succeeds:
    await mark_file_processed(filename, success=True)  # ✅ CORRECT!
except:
    await mark_file_processed(filename, success=False, error=str(e))
```

---

## 📊 IMPACT ASSESSMENT

### Data Loss
- **2 rounds missing** from database
- **~12-14 player stat records missing**
- **Session appears incomplete** in Discord output

### User-Visible Issues

**Discord `!last_session` output shows:**
```
7 players • 10 rounds • Maps: etl_adlernest, etl_sp_delivery, supply, sw_goldrush_te, te_escape2
```

**WRONG! Should show:**
```
7 players • 12 rounds • Maps: etl_adlernest, etl_sp_delivery, supply (1x), sw_goldrush_te, te_escape2 (2x)
```

### Statistics Affected
- All player totals are UNDERSTATED by 2 rounds
- te_escape2 stats incomplete (only 1 match counted instead of 2)
- Map play counts INCORRECT

---

## 🔬 WHAT ACTUALLY HAPPENED

### Timeline - 2025-11-16 Session

```
21:49:53 - etl_adlernest R1       ✅ IN DB
22:19:32 - etl_adlernest R2/R0    ✅ IN DB
22:30:31 - supply R1              ✅ IN DB
22:38:57 - supply R2/R0           ✅ IN DB
22:49:20 - etl_sp_delivery R1     ✅ IN DB
22:58:53 - etl_sp_delivery R2/R0  ✅ IN DB

23:07:57 - te_escape2 R1 (Match 1) ✅ IN DB
23:16:21 - te_escape2 R2/R0        ✅ IN DB

>>> PLAYER SUBSTITUTION OCCURRED HERE <<<

23:23:28 - te_escape2 R1 (Match 2) ❌ MISSING! (but file exists and marked processed)
23:28:17 - te_escape2 R2           ❌ MISSING! (but file exists and marked processed)

23:37:25 - sw_goldrush_te R1       ✅ IN DB
23:46:17 - sw_goldrush_te R2/R0    ✅ IN DB
```

**Expected behavior:** When player joins/leaves mid-session, map is restarted (R1 again)
**Actual result:** Second te_escape2 match files processed but data lost

---

## ✅ FIX REQUIRED

### Immediate (High Priority)

1. **Fix transaction isolation in `postgresql_database_manager.py`:**
   - Move `mark_file_processed()` OUTSIDE transaction block
   - Only mark as processed AFTER successful commit

2. **Re-import missing rounds:**
   ```bash
   # Unmark files
   DELETE FROM processed_files
   WHERE filename IN (
       '2025-11-16-232328-te_escape2-round-1.txt',
       '2025-11-16-232817-te_escape2-round-2.txt'
   );

   # Then run import
   python3 postgresql_database_manager.py
   # Select option 2 (Import all files)
   ```

3. **Verify re-import:**
   ```sql
   SELECT COUNT(*) FROM rounds WHERE round_date = '2025-11-16';
   -- Should return 17 (currently returns 15)
   ```

### Long-term (Prevent Recurrence)

1. **Add integrity check:**
   - Count files vs database rounds daily
   - Alert if mismatch detected

2. **Add transaction logging:**
   - Log when transactions fail
   - Log when mark_file_processed succeeds but transaction fails

3. **Audit existing data:**
   - Check all dates for files-vs-rounds mismatches
   - Re-import any missing data

---

## 🔍 HOW TO DETECT THIS BUG

### Quick Check
```bash
# Count files
ls local_stats/2025-11-16-*.txt | wc -l

# Count rounds in DB
psql -d etlegacy -c "SELECT COUNT(*) FROM rounds WHERE round_date = '2025-11-16';"

# If different, investigate!
```

### Comprehensive Audit
```sql
-- Find dates with potential mismatches
SELECT
    round_date,
    COUNT(*) as db_rounds,
    (SELECT COUNT(*) FROM processed_files
     WHERE filename LIKE round_date || '%' AND success = TRUE) as processed_files
FROM rounds
GROUP BY round_date
HAVING COUNT(*) != (SELECT COUNT(*) FROM processed_files
                    WHERE filename LIKE round_date || '%' AND success = TRUE);
```

---

## 📈 VERIFICATION AFTER FIX

**Before Fix:**
- Files: 13
- Database rounds: 15 (including R0)
- Playable rounds (R1+R2): 10
- te_escape2 matches: 1

**After Fix (Expected):**
- Files: 13
- Database rounds: 17 (including R0)
- Playable rounds (R1+R2): 12
- te_escape2 matches: 2 ✅

---

## 🎯 PRIORITY: HIGH

**Reason:** This bug causes silent data loss. Users don't notice missing rounds until they specifically look for them. Every gaming session could be affected.

**Recommended Action:** Fix immediately and audit all historical data for similar losses.

---

**Report By:** Automated Testing System
**Confirmed By:** Manual verification of files vs database
**Related Issues:** BUGFIX_SESSION_NOV3_2025.md (Transaction Isolation Bug)
