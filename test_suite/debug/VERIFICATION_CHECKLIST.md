# ✅ VERIFICATION CHECKLIST - After AI Agent Fix

**Issue Found**: Weapon stats weren't being inserted due to missing NOT NULL columns  
**Fix Applied**: Added session_date, map_name, round_number to weapon inserts  
**Status**: Ready to test

---

## 🎯 STEP 1: Restart & Re-Import (5 minutes)

### 1.1 Restart the Bot
```bash
# Stop the bot (Ctrl+C if running in terminal)
# Or kill the process
pkill -f ultimate_bot.py

# Start it again
python ultimate_bot.py
# or
python3 ultimate_bot.py
```

### 1.2 Re-Import Recent Stats
In Discord, run one of these commands:

```
!sync_today
```

Or manually trigger import for a specific file:
```
!import_file 2025-10-30-230944-braundorf_b4-round-2.txt
```

**Expected**: Bot should process files without errors

---

## 🔍 STEP 2: Verify Weapon Stats (2 minutes)

### 2.1 Check Weapon Diagnostic Command

Get the session_id first:
```sql
SELECT id, map_name, round_number, session_date 
FROM sessions 
ORDER BY session_date DESC 
LIMIT 5;
```

Then in Discord:
```
!weapon_diag <session_id>
```

**Expected output:**
```
🔍 Weapon Stats Diagnostic for Session 123

Session: braundorf_b4 - Round 2
Date: 2025-10-30-230944

Weapon Rows: 84          ← Should be > 0 now!
Total Hits: 1,234        ← Should be > 0
Total Shots: 3,456       ← Should be > 0  
Total Headshots: 89      ← Should be > 0
```

**If you see zeros**, the fix didn't work and we need to check logs.

### 2.2 Manual SQL Check (Alternative)

If you don't have `!weapon_diag`, run this SQL query:

```sql
-- Check weapon stats for latest session
SELECT 
    s.id AS session_id,
    s.map_name,
    s.round_number,
    COUNT(*) AS weapon_rows,
    SUM(w.hits) AS total_hits,
    SUM(w.shots) AS total_shots,
    SUM(w.headshots) AS total_headshots
FROM sessions s
LEFT JOIN weapon_comprehensive_stats w ON w.session_id = s.id
WHERE s.session_date LIKE '2025-10-30%'
GROUP BY s.id
ORDER BY s.session_date DESC
LIMIT 5;
```

**Expected**: All rows should have weapon_rows > 0 and non-zero totals

---

## 🚨 STEP 3: Check Bot Logs (If Still Broken)

### 3.1 Look for ERROR Messages

```bash
# If bot is running in terminal, watch for:
tail -f bot.log | grep -i "error\|weapon"
```

Look for patterns like:
- ❌ `NOT NULL constraint failed: weapon_comprehensive_stats.XXX`
- ❌ `Failed to insert weapon stats for <player>:`
- ❌ `IntegrityError:`

### 3.2 If You See Errors

**Copy the full error traceback** and paste it to your AI agent. It will look like:

```
ERROR:UltimateBot:❌ Failed to insert weapon stats for vid: IntegrityError...
Traceback (most recent call last):
  File "ultimate_bot.py", line 1234, in _insert_player_stats
    ...
sqlite3.IntegrityError: NOT NULL constraint failed: weapon_comprehensive_stats.XXX
```

Your AI agent can then fix the specific column that's still missing.

---

## ✅ STEP 4: Verify Stats Are Correct (5 minutes)

### 4.1 Test Display Commands

Run these in Discord:

```
!stats <your_player_name>
!last_session
!leaderboard
```

**Check that:**
- ✅ Kills/Deaths match what you remember
- ✅ DPM values look reasonable (50-300 range)
- ✅ Accuracy isn't 0%
- ✅ Weapon stats show up
- ✅ Gibs, revives, objective stats are present

### 4.2 Compare with Raw Stats File

Open one of your stats files:
```
/mnt/project/2025-10-30-230944-braundorf_b4-round-2.txt
```

**Manually check a player:**
1. Find their line in the text file
2. Count their kills/deaths/damage
3. Compare with what bot displays
4. Should match!

---

## 🎯 DECISION TREE

### ✅ If Weapon Rows Now Show (Rows > 0)
**Success!** The fix worked. Your stats should be correct now.

**Next steps:**
- Test all commands thoroughly
- Mark this issue as resolved
- Add a test to prevent regression

### ❌ If Still Showing Zero Weapon Rows

**Check these:**

1. **Missing columns?**
   - Look for error: `no such column: XXX`
   - AI agent needs to add that column to the insert

2. **Wrong data types?**
   - Look for error: `datatype mismatch`
   - AI agent needs to cast values properly

3. **Transaction not committed?**
   - Check if there's a `await db.commit()` after inserts
   - Might be missing or in wrong place

4. **Parser not providing weapon_stats?**
   - Run: `python debug_stats.py <stats_file>`
   - Check if weapon_stats exists in output

### ❌ If Weapon Rows Exist But Stats Still Wrong

**Then the issue is elsewhere:**

1. **Check display queries** - SQL might be wrong
2. **Check calculations** - DPM/efficiency formulas
3. **Check aggregation** - How stats are summed for sessions

---

## 📊 EXPECTED RESULTS (After Fix)

### Before Fix:
```
!weapon_diag 123
→ Weapon Rows: 0          ← PROBLEM!
→ Total Hits: 0
→ Total Shots: 0
```

### After Fix:
```
!weapon_diag 123
→ Weapon Rows: 84         ← FIXED!
→ Total Hits: 1,234
→ Total Shots: 3,456
→ Accuracy: 35.7%
```

---

## 🔧 TROUBLESHOOTING

### Problem: "Session already exists" when re-importing

**Solution**: Delete and re-import

```sql
-- Find session ID
SELECT id, session_date, map_name FROM sessions 
WHERE session_date LIKE '2025-10-30%';

-- Delete that session (cascades to weapon_stats)
DELETE FROM sessions WHERE id = <session_id>;

-- Re-import
!import_file 2025-10-30-230944-braundorf_b4-round-2.txt
```

### Problem: Still getting NOT NULL errors

**Solution**: Check which column is failing

The error will say: `NOT NULL constraint failed: weapon_comprehensive_stats.XXX`

Tell your AI agent: "Still failing on column XXX, please add it to the insert"

### Problem: Weapon rows inserted but all zeros

**Solution**: Parser might not be providing weapon data

```bash
python debug_stats.py /mnt/project/2025-10-30-230944-braundorf_b4-round-2.txt
```

Check the output under "🔫 Weapon Stats" - if it shows "No weapon stats found", the parser isn't extracting them.

---

## 📝 WHAT TO REPORT BACK

After testing, report:

### If It Works ✅
```
✅ FIXED! 
- Weapon rows: 84
- Stats look correct
- All commands working
```

### If Still Broken ❌
```
❌ STILL BROKEN
- Weapon rows: [0 or number]
- Error message: [paste full traceback]
- !weapon_diag output: [paste]
- What I tried: [list steps]
```

---

## 🚀 QUICK COMMANDS

```bash
# 1. Restart bot
pkill -f ultimate_bot.py && python ultimate_bot.py &

# 2. Check latest session ID
sqlite3 etlegacy_production.db "SELECT id, map_name FROM sessions ORDER BY id DESC LIMIT 1;"

# 3. Check weapon stats for that session
sqlite3 etlegacy_production.db "SELECT COUNT(*) FROM weapon_comprehensive_stats WHERE session_id = <id>;"

# 4. Re-import in Discord
!sync_today
```

---

**Time needed**: 10-15 minutes  
**Success rate**: High (if agent fixed the right columns)  
**Next step**: Run the checklist and report results! 🎯
