# 🔧 Parser Field Mapping Fix - Complete Documentation

**Date:** October 3, 2025  
**Status:** ✅ FIXED AND VERIFIED  
**Database Import:** 24,774 records successfully imported

---

## 🐛 Problem Summary

During bulk import, the parser was throwing **hundreds of "list index out of range" errors** when trying to read field 36 (`repairs_constructions`).

---

## 🔍 Root Cause Analysis

### What We Discovered

1. **The lua writes 36 TAB-separated fields (indices 0-35), NOT 37!**
   - Parser was trying to access `tab_fields[36]` for `repairs_constructions`
   - But the lua only writes fields 0-35

2. **`repairs_constructions` (topshots[19]) is tracked but NEVER written to file**
   - Line 100 in c0rnp0rn3.lua defines `topshots[i][19] = repairs/constructions`
   - Line 726 increments it: `topshots[tonumber(engi)][19] = topshots[tonumber(engi)][19] + 1`
   - **But line 273 (the stats output) only writes topshots[i][1] through topshots[i][18]**

### Evidence from Files

Test file: `2025-04-03-215602-etl_adlernest-round-2.txt`

```
Player line structure:
GUID\name\rounds\team\weaponMask weaponStats [TAB] field0 [TAB] field1 ... [TAB] field35

Extended part has 36 TAB-separated fields:
Field count: 36
Last 5 fields: ['0', '0', '0', '1', '0']  (fields 31-35)
                                            ^^^^^^^^^^^ field 35 is the LAST field!
```

---

## ✅ The Fix

### Code Changes in `community_stats_parser.py`

**Line 664:** Updated comment
```python
# OLD: After weapon stats come TAB-separated fields (0-36)
# NEW: After weapon stats come TAB-separated fields (0-35) = 36 fields
```

**Line 673:** Updated comment
```python
# OLD: Actual format has 37 TAB-separated fields (per c0rnp0rn3.lua line 269)
# NEW: Actual format has 36 TAB-separated fields (per c0rnp0rn3.lua line 273)
```

**Lines 728-733:** Removed field 36 access, added explanatory comments
```python
'multikill_6x': int(tab_fields[33]),
'useless_kills': int(tab_fields[34]),
'full_selfkills': int(tab_fields[35]),
# NOTE: repairs_constructions (topshots[19]) is NOT written by lua!
# 36 fields total: Tab[0-35]
```

**Line 737:** Updated error message
```python
# OLD: print(f"Warning: Could not parse all 37 fields: {e}")
# NEW: print(f"Warning: Could not parse all 36 fields: {e}")
```

---

## 📊 Complete Field Mapping (36 Fields)

| Index | Field Name | Type | Lua Source |
|-------|-----------|------|------------|
| 0 | damage_given | int | damageGiven |
| 1 | damage_received | int | damageReceived |
| 2 | team_damage_given | int | teamDamageGiven |
| 3 | team_damage_received | int | teamDamageReceived |
| 4 | gibs | int | gibs |
| 5 | selfkills | int | selfkills |
| 6 | teamkills | int | teamkills |
| 7 | teamgibs | int | teamgibs |
| 8 | time_played_percent | float | timePlayed (% of round time) |
| 9 | xp | int | xp |
| 10 | killing_spree | int | topshots[i][1] |
| 11 | death_spree | int | topshots[i][2] |
| 12 | kill_assists | int | topshots[i][3] |
| 13 | kill_steals | int | topshots[i][4] |
| 14 | headshot_kills | int | topshots[i][5] |
| 15 | objectives_stolen | int | topshots[i][6] |
| 16 | objectives_returned | int | topshots[i][7] |
| 17 | dynamites_planted | int | topshots[i][8] |
| 18 | dynamites_defused | int | topshots[i][9] |
| 19 | times_revived | int | topshots[i][10] |
| 20 | bullets_fired | int | topshots[i][11] |
| 21 | dpm | float | topshots[i][12] (0.0 from lua) |
| 22 | **time_played_minutes** | float | **roundNum((tp/1000)/60, 1)** ✅ |
| 23 | tank_meatshield | float | topshots[i][13] |
| 24 | time_dead_ratio | float | topshots[i][14] |
| 25 | time_dead_minutes | float | roundNum((death_time_total[i] / 60000), 1) |
| 26 | kd_ratio | float | kd |
| 27 | useful_kills | int | topshots[i][15] |
| 28 | denied_playtime | int | math.floor(topshots[i][16]/1000) |
| 29 | multikill_2x | int | multikills[i][1] |
| 30 | multikill_3x | int | multikills[i][2] |
| 31 | multikill_4x | int | multikills[i][3] |
| 32 | multikill_5x | int | multikills[i][4] |
| 33 | multikill_6x | int | multikills[i][5] |
| 34 | useless_kills | int | topshots[i][17] |
| 35 | full_selfkills | int | topshots[i][18] |
| ❌ 36 | ~~repairs_constructions~~ | ~~int~~ | **NOT WRITTEN** (topshots[i][19] exists in lua but isn't output) |

---

## 🧪 Verification Results

### Import Test
```bash
python tools/simple_bulk_import.py local_stats\*.txt
```

**Results:**
- ✅ **24,774 records imported** successfully
- ✅ **NO "list index out of range" errors**
- ✅ Only 100 legitimate failures ("insufficient lines" from corrupted 2024 files)
- ✅ **20,158 records (81%) have time_played_seconds > 0**

### Database Verification
```python
python verify_import.py
```

**Sample Data:**
```
Player Name               Time (s)     Time       Minutes    DPM
--------------------------------------------------------------------------------
bl^>Auss^>:X              600          10:00      10.0       580.5
^>.pek                    600          10:00      10.0       226.3
.wjs:)                    600          10:00      10.0       204.5
SuperBoyy                 720          12:00      12.0       245.4
```

✅ **Time data is accurate:** 600 seconds = 10:00, 720 seconds = 12:00  
✅ **repairs_constructions = 0** for all records (as expected)  
✅ **DPM calculations are correct**

---

## 📝 Key Takeaways

1. **Lua only writes 36 fields (0-35), not 37 (0-36)**
   - c0rnp0rn3.lua line 273 shows exactly 36 format specifiers after the first `%s`

2. **repairs_constructions is a dead field**
   - Tracked in memory but never written to stats files
   - Database column exists but will always be 0

3. **Field 22 contains actual time data**
   - `time_played_minutes` = lua-rounded minutes (e.g., 10.0, 12.0, 11.6)
   - Parser converts this to seconds for storage: `time_played_seconds = round(minutes * 60)`

4. **Always verify against source code**
   - Documentation can be wrong
   - Count actual fields in files
   - Trace through lua to see what's actually written

---

## 🔗 Related Documents

- `HEADER_FORMAT_UPDATE.md` - New 9-field header format with exact playtime_seconds
- `FIELD_MAPPING_FROM_DEV.md` - Original field mapping (had incorrect field count)
- `recreate_database.py` - Database schema (includes unused repairs_constructions column)

---

*Fixed by: GitHub Copilot*  
*Verified on: October 3, 2025*  
*Import test: 24,774 records, 0 field errors*
