# 📝 PARSER UPDATE - Support for New Header Format

**Date:** October 3, 2025  
**Status:** ✅ IMPLEMENTED  
**Backward Compatible:** Yes

---

## 🔄 What Changed

### NEW c0rnp0rn3.lua (Updated Version)

The lua script now writes **actual playtime in seconds** as the **9th field** in the header.

**Lua Code (line 281):**
```lua
local header = string.format("%s\\%s\\%s\\%d\\%d\\%d\\%s\\%s\\%s\n", 
    servername, mapname, config, round, defenderteam, winnerteam, 
    timelimit, nextTimeLimit, 
    ((round_end_time - round_start_time) / 1000))  -- NEW: playtime in seconds
```

---

## 📋 Header Format Comparison

### OLD Format (8 fields)
```
^a#^7p^au^7rans^a.^7only\etl_adlernest\legacy3\1\1\2\10:00\3:51
```

**Fields:**
1. servername
2. mapname
3. config
4. round
5. defenderteam
6. winnerteam
7. timelimit (MM:SS)
8. **actual_time (MM:SS)** ← Parser converts this to seconds

### NEW Format (9 fields)
```
^a#^7p^au^7rans^a.^7only\etl_adlernest\legacy3\1\1\2\10:00\0:00\231
```

**Fields:**
1. servername
2. mapname
3. config
4. round
5. defenderteam
6. winnerteam
7. timelimit (MM:SS)
8. nextTimeLimit (MM:SS) - **can be 0:00**
9. **actual_playtime_seconds** ← NEW! Exact seconds (e.g., 231)

---

## 💡 Why This Change?

### Problem with OLD Format
When `g_nextTimeLimit` is 0:00, we can't rely on parsing MM:SS for accurate time.

**Example:**
```
Old header: ...\10:00\0:00
            timelimit^  ^actual_time (WRONG!)
```

If actual_time shows 0:00, we don't know the real playtime!

### Solution: NEW Format
```
New header: ...\10:00\0:00\231
            timelimit^ ^0:00  ^231 seconds (EXACT!)
```

The 9th field gives us **exact playtime from the server** regardless of what g_nextTimeLimit shows.

---

## 🔧 Parser Implementation

### Code Changes (community_stats_parser.py)

```python
# Check for NEW lua format: 9th field = actual playtime in seconds
actual_playtime_seconds = None
if len(header_parts) >= 9:
    try:
        # New format has exact playtime in seconds as 9th field
        actual_playtime_seconds = float(header_parts[8])
    except (ValueError, IndexError):
        actual_playtime_seconds = None

# Calculate time in SECONDS (primary storage format)
if actual_playtime_seconds is not None:
    # NEW FORMAT: Use exact seconds from header field 9
    round_time_seconds = int(actual_playtime_seconds)
else:
    # OLD FORMAT: Parse MM:SS from header field 8
    round_time_seconds = self.parse_time_to_seconds(actual_time)
    if round_time_seconds == 0:
        round_time_seconds = 300  # Default 5 minutes if unknown
```

---

## ✅ Compatibility

### Backward Compatible
- ✅ Works with **all existing files** (8-field header)
- ✅ Gracefully falls back to parsing MM:SS
- ✅ No changes needed for old data imports

### Forward Compatible
- ✅ Ready for **new lua version** (9-field header)
- ✅ Automatically detects and uses exact seconds
- ✅ More accurate DPM calculations

---

## 🧪 Testing

### Test Script: `test_header_formats.py`

```bash
python test_header_formats.py
```

**Results:**
- ✅ OLD format (Oct 2 files): Parses correctly (231 seconds from "3:51")
- ✅ NEW format: Ready to use exact seconds from field 9
- ✅ DPM calculations: Accurate for both formats

---

## 📊 Impact on DPM Calculations

### OLD Format
```
Header: ...\3:51
Parse: 3*60 + 51 = 231 seconds
DPM: (damage * 60) / 231
```

### NEW Format
```
Header: ...\0:00\231
Use: 231 seconds (exact!)
DPM: (damage * 60) / 231
```

**Result:** Same DPM for this example, but NEW format works even when g_nextTimeLimit is wrong!

---

## 🚀 Deployment

### Current Status
- ✅ Parser updated and tested
- ✅ Backward compatible with all existing files
- ⏳ Waiting for new lua files to test new format

### When New Files Arrive
1. Parser will **automatically detect** 9-field header
2. Use **exact seconds** from field 9
3. No code changes needed!
4. More accurate DPM, especially for edge cases

---

## 📝 Developer Notes

### Key Points
1. **Always check header length**: `if len(header_parts) >= 9`
2. **Graceful fallback**: Old format still works
3. **Exact time source**: New format is more reliable
4. **Integer seconds**: Convert float to int for consistency

### Future Considerations
- Old files will remain in database with MM:SS parsed times
- New files will have exact server-measured times
- Both are correct, new format is just more precise
- No need to re-import old data

---

## ✨ Summary

**What we did:**
- Added support for 9-field header with exact playtime_seconds
- Maintained backward compatibility with 8-field header
- Parser automatically detects and uses best time source

**Result:**
- ✅ Works with all existing files
- ✅ Ready for new lua version
- ✅ More accurate DPM when g_nextTimeLimit is unreliable
- ✅ Zero breaking changes!

---

*Implementation completed: October 3, 2025*
