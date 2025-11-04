# 🤖 AI COPILOT QUICK REFERENCE - Seconds-Based Time System

**Last Updated:** October 3, 2025  
**Status:** Implemented and tested ✅  
**Next Step:** Update bot queries

---

## 🎯 What Changed (TL;DR)

**OLD SYSTEM:** Time stored as decimal minutes (3.85)  
**NEW SYSTEM:** Time stored as seconds (231)

**Why:** Community consensus - seconds are clearer and more precise.

---

## 🔑 Key Facts

1. **Tab[22] = 0.0 ALWAYS** (lua never writes to it) ❌
2. **Tab[23] = actual time** (lua-rounded minutes, e.g., 3.9) ✅
3. **Session time** from header is exact MM:SS (e.g., "3:51")
4. **Primary storage:** `time_played_seconds` INTEGER
5. **Display format:** `time_display` string (e.g., "3:51")
6. **DPM calculation:** `(damage * 60) / seconds`

---

## 📝 Parser Changes

### What Parser Now Does
```python
# Reads session time from header
round_time_seconds = parse_time_to_seconds("3:51")  # 231

# Stores in player dict
player['time_played_seconds'] = 231  # PRIMARY (integer)
player['time_display'] = "3:51"      # DISPLAY (string)
player['time_played_minutes'] = 3.85 # BACKWARD COMPAT (float)

# Calculates DPM
player['dpm'] = (damage * 60) / 231  # Not damage / 3.85
```

### Round 2 Differential
```python
# Calculates R2-only time
diff_seconds = int((r2_time - r1_time) * 60)
differential_player['time_played_seconds'] = diff_seconds
differential_player['dpm'] = (damage * 60) / diff_seconds
```

---

## 🗄️ Database Schema

### Current Structure
```sql
player_comprehensive_stats:
  - time_played_seconds INTEGER  -- NEW (primary)
  - time_played_minutes REAL     -- OLD (backward compat)
  - dpm REAL                     -- Uses seconds now
```

### Sample Data
```
Player: vid
  time_played_seconds: 231
  time_played_minutes: 3.85
  time_display: "3:51"
  dpm: 344.94
```

---

## 🔍 Common Issues & Solutions

### Issue 1: "Why is time = 0?"
**Cause:** Reading Tab[22] instead of Tab[23]  
**Solution:** Parser now reads Tab[23] ✅

### Issue 2: "Round 2 differential has no time!"
**Cause:** Differential wasn't preserving time field  
**Solution:** Now calculates R2-only time in seconds ✅

### Issue 3: "DPM doesn't match expectations"
**Cause:** Using decimal minutes instead of seconds  
**Solution:** DPM now uses `(damage * 60) / seconds` ✅

### Issue 4: "3.85 minutes? File shows 3:51!"
**Cause:** Decimal minutes confusing  
**Solution:** Use time_display field for MM:SS format ✅

---

## 🧪 Testing Commands

```bash
# Test parser output
python dev/test_seconds_parser.py

# Test database integration
python dev/test_full_seconds_integration.py

# Check current database
python dev/check_database_time_storage.py
```

---

## 📊 Next Steps (Bot Update)

### What Needs Updating
File: `bot/ultimate_bot.py`

### OLD Query (uses minutes):
```python
SELECT 
    AVG(p.dpm) as avg_dpm,
    SUM(p.time_played_minutes) as total_time
FROM player_comprehensive_stats p
WHERE p.time_played_minutes > 0
```

### NEW Query (uses seconds):
```python
SELECT 
    -- Calculate DPM using seconds
    (SUM(p.damage_given) * 60.0) / NULLIF(SUM(p.time_played_seconds), 0) as dpm,
    
    -- Show time in MM:SS format
    SUM(p.time_played_seconds) as total_seconds
FROM player_comprehensive_stats p
WHERE p.time_played_seconds > 0
GROUP BY p.player_guid
```

### Display Helper
```python
def seconds_to_mmss(seconds: int) -> str:
    """Convert seconds to MM:SS display"""
    m = seconds // 60
    s = seconds % 60
    return f"{m}:{s:02d}"

# Usage
total_seconds = 231
display = seconds_to_mmss(total_seconds)  # "3:51"
```

---

## 📚 Related Documents

- **SECONDS_IMPLEMENTATION_COMPLETE.md** - Full implementation report (900+ lines)
- **SECONDS_IMPLEMENTATION_PLAN.md** - Complete guide with examples (500+ lines)
- **DPM_FIX_PROGRESS_LOG.md** - Historical progress log

---

## ⚠️ Important Reminders

1. **NEVER read Tab[22]** - it's always 0.0
2. **ALWAYS use time_played_seconds** for calculations
3. **Display time_display** to users (MM:SS format)
4. **Filter WHERE time_played_seconds > 0** in queries
5. **DPM formula:** `(damage * 60) / seconds` NOT `damage / minutes`

---

## ✅ Verification Checklist

When working with time data:
- [ ] Using time_played_seconds (not minutes)?
- [ ] Reading Tab[23] (not Tab[22])?
- [ ] Displaying MM:SS format (not decimal)?
- [ ] DPM using `(damage * 60) / seconds`?
- [ ] Filtering `WHERE time_played_seconds > 0`?

---

## 🎓 Community Quotes

> **SuperBoyy:** "0.1 minute je 6 sekund. Jz vse v sekunde spremenim."  
> _(0.1 minute is 6 seconds. I convert everything to seconds.)_

> **vid:** "convertej v sekunde pa bo lazi"  
> _(convert to seconds and it will be clearer)_

**Status:** ✅ **IMPLEMENTED** - We now match community standard!

---

*Quick Reference Version 1.0*  
*For detailed information, see SECONDS_IMPLEMENTATION_COMPLETE.md*
