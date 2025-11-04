# 🔧 CRITICAL SCHEMA FIX - November 3, 2025

## 🚨 Problems Discovered

### Problem 1: Lost Sessions (472 files / 22% of data)
**Root Cause:** UNIQUE constraint was `(round_date, map_name, round_number)`

This assumed **only ONE game per map per day**, but reality:
- Players replay same map **MULTIPLE TIMES per day**
- Example: `te_escape2` played **4 times** on 2025-07-10
- Only the **FIRST** occurrence was imported
- All subsequent games were **REJECTED** by UNIQUE constraint

**Impact:** 
- ❌ Lost 472 sessions (22% of total data)
- ❌ Incomplete player statistics
- ❌ Missing matches from database

---

### Problem 2: Broken Round 1 ↔ Round 2 Pairing
**Root Cause:** No link between Round 1 and Round 2 of the SAME match

Files on same day:
```
2025-07-10-222059-te_escape2-round-1.txt  ← Match 1, R1
2025-07-10-222635-te_escape2-round-2.txt  ← Match 1, R2 (belongs to ↑)
2025-07-10-223622-te_escape2-round-1.txt  ← Match 2, R1
2025-07-10-224121-te_escape2-round-2.txt  ← Match 2, R2 (belongs to ↑)
```

**Old schema:** No way to know R1 and R2 belong together!
**Impact:**
- ❌ Can't calculate Round 2 differential (R2 - R1)
- ❌ Can't track match outcomes
- ❌ Can't analyze full match statistics

---

## ✅ Solution: Schema v2.0

### New `rounds` Table Schema:
```sql
CREATE TABLE rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_date TEXT NOT NULL,           -- YYYY-MM-DD
    round_time TEXT NOT NULL,           -- HHMMSS (NEW!)
    match_id TEXT NOT NULL,               -- date_time_map (NEW!)
    map_name TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    time_limit TEXT,
    actual_time TEXT,
    winner_team INTEGER DEFAULT 0,
    defender_team INTEGER DEFAULT 0,
    is_tied BOOLEAN DEFAULT FALSE,
    round_outcome TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(match_id, round_number)        -- NEW UNIQUE CONSTRAINT!
)
```

### Key Changes:
1. **Added `round_time`** - Captures HHMMSS from filename
2. **Added `match_id`** - Links Round 1 and Round 2 together
3. **Changed UNIQUE constraint** - From `(date, map, round)` to `(match_id, round)`

---

## 🎯 Match Pairing Algorithm

### For Round 1 Files:
```python
match_id = f"{date}_{time}_{map}"
# Example: "2025-07-10_222059_te_escape2"
```

### For Round 2 Files:
```python
# Find closest Round 1 file BEFORE this R2 (same date, same map)
# Use that R1's match_id
# This pairs R1 and R2 from the SAME match!
```

### Example:
```
Round 1: 2025-07-10-222059-te_escape2-round-1.txt
  → match_id = "2025-07-10_222059_te_escape2"
  
Round 2: 2025-07-10-222635-te_escape2-round-2.txt
  → Finds R1 at 222059 (closest before 222635)
  → Uses same match_id = "2025-07-10_222059_te_escape2"
  
✅ Both rounds linked by match_id!
```

---

## 📊 Expected Results After Fix

### Before Fix:
- ❌ 1,681 sessions imported (out of 2,153 files)
- ❌ 472 files rejected (22% lost)
- ❌ No R1↔R2 pairing
- ❌ Can't calculate R2 differential

### After Fix:
- ✅ **ALL 2,153 files imported** (0% lost)
- ✅ Round 1 and Round 2 properly paired
- ✅ Match tracking enabled
- ✅ Round 2 differential calculation works
- ✅ Multiple games per day supported

---

## 🧪 Test Results

Tested on 3 problematic date/map combinations:

### Test 1: 2025-07-10 - te_escape2
- Found: 4 Round 1, 4 Round 2
- **Result:** ✅ All 4 matches paired perfectly
- Time gaps: 329-576 seconds (5-9 minutes)

### Test 2: 2025-09-09 - et_brewdog  
- Found: 3 Round 1, 3 Round 2
- **Result:** ✅ All 3 matches paired perfectly
- Time gaps: 149-4488 seconds (2 min - 1 hour)

### Test 3: 2025-01-16 - te_escape2
- Found: 4 Round 1, 3 Round 2
- **Result:** ✅ 3 matches paired, 1 R1 orphaned (no R2 file exists)
- This is expected - server crash or players left

---

## 🔄 Migration Plan

1. **Stop bot** (if running)
2. **Run database_manager.py** option 3 (Rebuild from scratch)
3. **New schema automatically applied**
4. **All 2,153 files imported**
5. **Validate results**
6. **Test bot commands**

---

## ✅ ALL FIXES IN database_manager.py

**CRITICAL:** All fixes are in `database_manager.py` - the single source of truth!

- ✅ Schema v2.0 with match_id and round_time
- ✅ UNIQUE constraint updated
- ✅ Round pairing algorithm implemented
- ✅ New index on match_id for performance

**Next run = Clean database with ALL data!** 🎉

---

## 📝 Summary

**Your battle-testing approach caught TWO critical bugs:**

1. **Lost Data Bug** - 22% of sessions couldn't be imported
2. **Broken Pairing Bug** - Round 1 and Round 2 not linked

**Both fixed in database_manager.py - ready for nuclear rebuild!** ✅
