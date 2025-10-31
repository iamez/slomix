# 🚨 EMERGENCY FIX - player_name Missing from Weapon Stats

**Error**: `NOT NULL constraint failed: weapon_comprehensive_stats.player_name`  
**Cause**: INSERT columns/values are misaligned or player_name is missing  
**Status**: Need to fix and re-import

---

## 🎯 RECOMMENDED APPROACH: Option A (Diagnostic First)

**Why**: We need to see EXACTLY what's being inserted to fix it properly

### Tell Your AI Agent This:

```
Choose Option A: Add diagnostic logging

I want to see the exact INSERT statement and values being used for weapon stats.
This will show us why player_name is missing or misaligned.

Please:
1. Add temporary logging to _insert_player_stats for weapon inserts
2. Log the insert_cols list and row_vals tuple for first 5 weapon rows
3. Show the complete INSERT SQL statement being executed

Then I'll restart the bot and import ONE file to capture the issue.
```

---

## 🔍 WHAT TO EXPECT

After AI agent adds logging and you re-import one file, you'll see output like:

```python
DEBUG: Weapon INSERT columns: ['session_id', 'session_date', 'map_name', 'round_number', 'player_guid', 'weapon_name', 'kills', ...]
DEBUG: Weapon INSERT values: (123, '2025-10-30', 'braundorf_b4', 2, 'A0B2063D', 'Thompson', 5, ...)
DEBUG: Weapon INSERT SQL: INSERT INTO weapon_comprehensive_stats (session_id, session_date, ...) VALUES (?, ?, ...)
```

**Look for:**
- ❌ Is `player_name` missing from the columns list?
- ❌ Is `player_name` in columns but value is missing?
- ❌ Are the number of columns ≠ number of values?
- ❌ Is the order wrong (player_name in wrong position)?

---

## 📋 STEP-BY-STEP AFTER DIAGNOSTIC

### Step 1: Stop Bot
```bash
# Press Ctrl+C in bot terminal
# Or kill process
pkill -f ultimate_bot.py
```

### Step 2: AI Agent Adds Logging
Tell your AI agent:
```
Add this logging to _insert_player_stats before weapon INSERT:

logger.error(f"DEBUG WEAPON INSERT:")
logger.error(f"  Columns: {insert_cols}")
logger.error(f"  Values: {row_vals}")
logger.error(f"  SQL: {insert_sql}")
```

### Step 3: Restart Bot & Test
```bash
# Start bot
python ultimate_bot.py

# In Discord, import ONE file
!import_file 2025-10-30-230944-braundorf_b4-round-2.txt
```

### Step 4: Check Logs
Look for the DEBUG output showing columns and values.

**Copy the full output and paste it to AI agent.**

### Step 5: AI Agent Fixes Alignment
Based on the debug output, AI agent will:
- Add `player_name` to columns if missing
- Fix the column order
- Ensure values match columns exactly

---

## 🔧 QUICK FIX IF YOU ALREADY KNOW THE ISSUE

If you want to try a manual fix (risky but faster):

### Check Current Code

Look in `ultimate_bot.py` around line 9750-9780 for:

```python
insert_cols = ["session_id"]
if "player_comprehensive_stat_id" in cols:
    insert_cols.append("player_comprehensive_stat_id")
if "player_guid" in cols:
    insert_cols.append("player_guid")
elif "player_name" in cols:  # ← This might be the issue
    insert_cols.append("player_name")
```

**Problem**: Using `elif` means if both `player_guid` AND `player_name` exist, only `player_guid` gets added!

**Fix**: Change `elif` to `if`:

```python
insert_cols = ["session_id"]
if "player_comprehensive_stat_id" in cols:
    insert_cols.append("player_comprehensive_stat_id")
if "player_guid" in cols:
    insert_cols.append("player_guid")
if "player_name" in cols:  # ← Changed elif to if
    insert_cols.append("player_name")
```

Then update the row_vals to match:

```python
row_vals = [session_id]
if "player_comprehensive_stat_id" in cols:
    row_vals.append(player_stats_id)
if "player_guid" in cols:
    row_vals.append(player.get("guid", "UNKNOWN"))
if "player_name" in cols:  # ← Changed elif to if
    row_vals.append(player.get("name", "Unknown"))
```

---

## 🗂️ CLEANUP BROKEN SESSIONS

After fixing the code, clean up broken sessions:

### Option 1: Quick SQL (Clean Last Week)
```sql
-- Find broken sessions (no weapon stats)
SELECT s.id, s.session_date, s.map_name, COUNT(w.id) AS weapon_rows
FROM sessions s
LEFT JOIN weapon_comprehensive_stats w ON w.session_id = s.id
WHERE s.session_date >= date('now', '-7 days')
GROUP BY s.id
HAVING weapon_rows = 0;

-- Delete them (they'll be re-imported)
DELETE FROM sessions WHERE id IN (
    SELECT s.id
    FROM sessions s
    LEFT JOIN weapon_comprehensive_stats w ON w.session_id = s.id
    WHERE s.session_date >= date('now', '-7 days')
    GROUP BY s.id
    HAVING COUNT(w.id) = 0
);

-- Also clear processed files so they'll re-import
DELETE FROM processed_files 
WHERE file_name LIKE '2025-10-%'
  AND success = 0;
```

### Option 2: Full Cleanup (Last Month)
```sql
-- Nuclear option: delete all sessions from October 2025
DELETE FROM sessions WHERE session_date LIKE '2025-10-%';
DELETE FROM processed_files WHERE file_name LIKE '2025-10-%';
```

Then re-import:
```
!sync_month
```

---

## 🎯 RECOMMENDED WORKFLOW

### Best Approach (Safe & Diagnostic)

1. **Stop bot** (Ctrl+C)
2. **Ask AI agent for Option A** (diagnostic logging)
3. **Restart bot**
4. **Import one file** (`!import_file <filename>`)
5. **Check logs** (copy output)
6. **Paste to AI agent** (shows exact problem)
7. **AI agent fixes** column/value alignment
8. **Clean broken sessions** (SQL above)
9. **Re-import** (`!sync_week` or `!sync_month`)
10. **Verify** with diagnostic_queries.sql

**Time**: 20-30 minutes  
**Risk**: Low (diagnostic first, then fix)

### Fast Approach (If You're Sure)

1. **Stop bot**
2. **Manually fix** elif → if in ultimate_bot.py
3. **Clean sessions** (SQL above)
4. **Restart bot**
5. **Re-import** (`!sync_month`)
6. **Verify** weapon_rows > 0

**Time**: 10 minutes  
**Risk**: Medium (if fix is wrong, still broken)

---

## 📊 VERIFICATION AFTER FIX

Run this query to verify weapon stats are now present:

```sql
-- Check latest 10 sessions
SELECT 
    s.id,
    s.session_date,
    s.map_name,
    COUNT(w.id) AS weapon_rows,
    SUM(w.hits) AS total_hits,
    SUM(w.shots) AS total_shots
FROM sessions s
LEFT JOIN weapon_comprehensive_stats w ON w.session_id = s.id
WHERE s.session_date >= date('now', '-7 days')
GROUP BY s.id
ORDER BY s.session_date DESC
LIMIT 10;
```

**Expected**: All sessions should have weapon_rows > 0

---

## 🚨 IF STILL BROKEN AFTER FIX

### Check These

1. **Schema Issue**
   ```sql
   PRAGMA table_info(weapon_comprehensive_stats);
   ```
   Verify `player_name` exists and is NOT NULL

2. **Parser Not Providing player_name**
   ```bash
   python debug_stats.py /mnt/project/2025-10-30-230944-braundorf_b4-round-2.txt
   ```
   Check if parser returns player 'name' field

3. **Column Order Wrong**
   Check if insert_cols order matches row_vals order EXACTLY

---

## 💡 WHAT TO TELL YOUR AI AGENT

Copy this prompt:

```
URGENT FIX NEEDED:

Error: NOT NULL constraint failed: weapon_comprehensive_stats.player_name

Issue: Weapon INSERT is missing player_name or columns/values are misaligned

Choose Option A: Add diagnostic logging

Please add logging to show:
1. insert_cols list (exact column names being inserted)
2. row_vals tuple (exact values being inserted)  
3. insert_sql (full SQL statement)

Log these for the first weapon row of the first player.

Then I'll:
1. Restart bot
2. Import one file
3. Copy the debug output back to you
4. You'll fix the column/value alignment based on what we see

After fixing, I'll clean broken sessions and re-import everything.
```

---

## ✅ SUCCESS CRITERIA

After fixing and re-importing:

- [ ] No more IntegrityError in logs
- [ ] weapon_rows > 0 for all sessions
- [ ] `!stats <player>` shows weapon-specific stats
- [ ] `!last_session` shows accurate data
- [ ] Accuracy values are 10-50% (not 0%)

---

**🎯 NEXT ACTION**: Tell your AI agent to choose **Option A** (diagnostic logging)

This will show us exactly what's wrong so we can fix it properly!
