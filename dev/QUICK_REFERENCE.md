# 🎯 DPM Fix - Quick Reference Card

**Last Updated:** October 3, 2025

---

## ✅ COMPLETED

### Parser Fix (Lines 386-417)
- ✅ Round 2 differential now preserves `time_played_minutes`
- ✅ Tested: vid Round 2 shows 3.8 min (was 0.0)
- ✅ Verified against raw files

---

## ⚠️ DECISION NEEDED

### Which DPM System to Use?

**Option A: Dual DPM (Recommended)**
```
Store BOTH:
- session_dpm (simple, always available)
- player_dpm (accurate, personalized)

Display: "DPM: 380.5 (session: 344.9)"
```

**Option B: Replace with Player DPM**
```
Store ONLY:
- dpm = damage / player_time

Simpler but loses historical comparison
```

**👉 USER: Please choose Option A or B**

---

## 📋 TODO (After Decision)

### If Option A (Dual DPM):
1. Add `player_dpm` column to database
2. Update parser to calculate both
3. Update bot to display both
4. Re-import database

### If Option B (Replace):
1. Update parser DPM calculation (line 494-502)
2. Re-import database
3. Bot works as-is

---

## 🔢 Key Numbers

### Current (WRONG):
- Bot shows: 302.53 DPM (AVG)
- "Our DPM": 514.88 DPM (inflated)

### After Fix (ESTIMATED):
- Correct DPM: ~350-380 DPM
- 41% of records will now have time data

---

## 📂 Important Files

### Modified:
- `bot/community_stats_parser.py` (lines 386-417)

### Documentation:
- `dev/DPM_FIX_PROGRESS_LOG.md` (full history)
- `dev/DPM_FIX_COMPLETE_SUMMARY.md` (technical)

### Test Files:
- `local_stats/2025-10-02-211808-etl_adlernest-round-1.txt`
- `local_stats/2025-10-02-212249-etl_adlernest-round-2.txt`

---

## 🎓 Remember

1. **c0rnp0rn3.lua Field 21 = 0.0** (doesn't calculate DPM)
2. **Field 23 = time_played_minutes** (the data we need)
3. **Round 2 cumulative** = R1 time + R2 time
4. **Parser calculates** = R2 cumulative - R1 = R2 only
5. **Always document** progress before moving forward!

---

## 🚀 Next Session

Start by choosing Option A or B, then proceed with implementation!
