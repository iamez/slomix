# Issues Found - October 4, 2025

## 🐛 ISSUE 1: Graph 2 Shows All Zeros

### Problem
Graph 2 panels show:
- **Medic Heroes** (Revives Given): All 0s ❌
- **Strategic Killers** (Most Useful Kills): All 0s ❌
- **Gib Masters**: Working ✅
- **Damage Dealers**: Working ✅

### Root Cause
Database query confirmed ALL players have:
- `revives_given = 0`
- `most_useful_kills = 0`

This means the **parser is not extracting these stats** from the game logs.

### Solution Options

**Option A: Remove the broken panels from Graph 2**
- Keep only Gibs and Damage (working)
- Make it a 1x2 or 2x1 layout
- Quick fix, loses functionality

**Option B: Fix the parser to extract these stats**
- Requires understanding the game log format
- Need to map which fields in the raw log correspond to:
  - `revives_given` (medic revives performed)
  - `most_useful_kills` (objective-related kills)
- More work but preserves functionality

**Recommendation:** **Option A** (remove broken panels) for now, fix parser later

---

## 🐛 ISSUE 2: Escape Map Count

### User Report
"4 rounds of escape (2 maps) but bot only shows 1"

### Database Reality
Latest session date: **2025-10-02**

Sessions on this date:
```
te_escape2 | Round 1 | Count: 1
te_escape2 | Round 2 | Count: 1
```

This equals **1 complete map play** (2 rounds), which is what the bot displays.

### Possible Causes

1. **Missing import**: Only imported 1 of the 2 escape sessions
   - Check if files exist: `local_stats/*escape*2025-10-02*`
   - Run import again if files found

2. **Different date**: User thinking of a different session date
   - Check all dates for escape counts

3. **Duplicate session**: Same session imported twice
   - Already checked, no duplicates found

### To Investigate
Run this command to check all escape sessions:
```powershell
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('SELECT session_date, COUNT(*) FROM sessions WHERE map_name = ? AND round_number = 2 GROUP BY session_date ORDER BY session_date DESC', ('te_escape2',)); rows = cursor.fetchall(); [print(f'{r[0]}: {r[1]} complete escape plays') for r in rows]; conn.close()"
```

---

## 🎨 ISSUE 3: Emoji Warnings (Cosmetic Only)

### Problem
Matplotlib warnings about missing glyphs:
```
UserWarning: Glyph 128165 (\N{COLLISION SYMBOL}) missing from font(s) DejaVu Sans.
UserWarning: Glyph 128202 (\N{BAR CHART}) missing from font(s) DejaVu Sans.
UserWarning: Glyph 127919 (\N{DIRECT HIT}) missing from font(s) DejaVu Sans.
UserWarning: Glyph 127922 (\N{GAME DIE}) missing from font(s) DejaVu Sans.
```

Affected titles:
- 💥 Damage Given vs Received  
- 📊 Damage Efficiency Ratio
- 🎯 Total Ammunition Fired
- 🎲 Bullets per Kill

### Impact
- Graphs still generate correctly ✅
- Emojis don't render in graph titles (shows boxes)
- **Purely cosmetic**, doesn't affect functionality

### Solution
Replace emoji titles with text-only:
- 💥 → "Damage Given vs Received"
- 📊 → "Damage Efficiency Ratio"  
- 🎯 → "Total Ammunition Fired"
- 🎲 → "Accuracy Metric"

---

## 🎯 RECOMMENDED FIXES

### Priority 1: Fix Graph 2 (Immediate)
Remove broken panels or switch to different stats that work:
- Option: Show `repairs_constructions`, `tank_meatshield`, etc.
- Option: Remove Graph 2 entirely (still have 3 other graphs)

### Priority 2: Check Escape Import (User Verification Needed)
- User needs to verify: How many escape stat files exist for 2025-10-02?
- If 4 rounds were played, there should be 4 files:
  - `*escape*round-1*.txt` (first play)
  - `*escape*round-2*.txt` (first play)
  - `*escape*round-1*.txt` (second play)
  - `*escape*round-2*.txt` (second play)

### Priority 3: Remove Emoji from Graph Titles (Cosmetic)
- Quick find/replace in Graph 4 code
- Eliminates warnings

---

## 💡 QUICK FIX CODE

### Fix Graph 2: Remove Broken Panels

Change Graph 2 from 2x2 to 1x2 (only Gibs and Damage):

```python
# Old: fig2, ((ax3, ax4), (ax5, ax6)) = plt.subplots(2, 2, figsize=(14, 10))
# New:
fig2, (ax4, ax6) = plt.subplots(1, 2, figsize=(14, 6))

# Keep only:
# - ax4: Gibs
# - ax6: Damage Dealers

# Remove ax3 (Revives) and ax5 (Useful Kills) code
```

### Fix Graph 4: Remove Emoji Warnings

```python
# Line ~2291
ax7.set_title('Damage Given vs Received', ...)  # Remove 💥

# Line ~2303  
ax8.set_title('Damage Efficiency Ratio', ...)   # Remove 📊

# Line ~2315
ax9.set_title('Total Ammunition Fired', ...)    # Remove 🎯

# Line ~2327
ax10.set_title('Accuracy Metric (Lower = Better)', ...)  # Remove 🎲
```

---

## ✅ What's Working Great

- ✅ All 8 text embeds display perfectly
- ✅ Special Awards (MESSAGE 7) - All 12 awards functional
- ✅ Chaos Stats (MESSAGE 8) - All 5 leaderboards working
- ✅ Graph 1: K/D/DPM - Perfect ✅
- ✅ Graph 3: Per-Map Breakdown - Perfect ✅
- ✅ Graph 4: Combat Efficiency - Perfect (just emoji warnings)
- ⚠️ Graph 2: 2 of 4 panels broken (Revives, Useful Kills = 0)

---

## 🚀 Next Steps

1. **User**: Confirm how many escape stat files exist for 2025-10-02
2. **Dev**: Apply Quick Fix for Graph 2 (remove broken panels)
3. **Dev**: Remove emojis from Graph 4 titles (eliminate warnings)
4. **Later**: Fix parser to extract `revives_given` and `most_useful_kills`

Would you like me to apply the quick fixes now?
