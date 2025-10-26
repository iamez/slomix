# 🎮 ETLegacy Discord Bot - COMPLETE PROJECT CONTEXT

**Date**: October 2, 2025  
**Status**: Ready for implementation after solving cumulative stats bug

---

## 🎯 **PROJECT OVERVIEW**

### **What We Have:**
- **Complete Discord bot** with 56+ commands (831 lines)
- **Working parser** for c0rnp0rn3.lua stats files
- **Production database** with 1,168 sessions, 15,767 round stats
- **All infrastructure** ready for deployment

### **What We're Fixing:**
- **Cumulative stats bug** in Round 2 data
- **DPM calculation** for differential rounds
- **Database re-import** with corrected stats

---

## 🚨 **THE CUMULATIVE STATS BUG**

### **Root Cause:**
c0rnp0rn3.lua generates stats where:
- **Round 1**: Shows Round 1 stats only ✅
- **Round 2**: Shows Round 1 + Round 2 combined ❌ (cumulative)

### **Evidence Confirmed:**
```
Player: carniee
├── Round 1: 5 kills, 1529 damage  
├── Round 2: 12 kills, 2483 damage (CUMULATIVE)
└── Round 2 ONLY: 7 kills, 954 damage (CALCULATED)
```

### **Impact:**
- **DPM values inflated** in database (30,000+ instead of 300+)
- **Round 2 statistics wrong** (show cumulative instead of round-only)
- **Leaderboards incorrect** (based on inflated cumulative data)

---

## ⏱️ **STOPWATCH MODE TIMING (SOLVED)**

### **How Stopwatch Works:**
1. **Round 1**: Team A attacks, completes objective in **3:56**
2. **Round 2**: Team B attacks, must beat **3:56** to win
3. **If Team B completes in 3:20**: Team B wins (faster time)
4. **If Team B hits time limit**: Game stops, Team A wins

### **Time Fields Meaning:**
- **map_time**: "12:00" = Map time limit (varies: 10/12/15 min)
- **actual_time**: Time when objective completed or time limit hit
  - **Round 1**: "3:56" = Time when Round 1 completed
  - **Round 2**: "3:20" = Time when Round 2 completed

### **Round Duration Calculation:**
- **Round 1 duration**: 3:56 (236 seconds)
- **Round 2 duration**: 3:20 (200 seconds) 
- **Both are independent round durations!**

---

## 📊 **CORRECT DPM CALCULATION**

### **Formula:**
```
DPM = Damage Given ÷ Round Duration (minutes)
```

### **Examples:**
```
Round 1 (carniee):
├── Damage: 1529
├── Duration: 3:56 = 3.93 minutes  
└── DPM: 1529 ÷ 3.93 = 388.7 DPM ✅

Round 2 ONLY (carniee):
├── Damage: 954 (2483 - 1529)
├── Duration: 3:20 = 3.33 minutes
└── DPM: 954 ÷ 3.33 = 286.5 DPM ✅

Combined Map Stats (carniee):
├── Total Damage: 2483 (1529 + 954)
├── Total Duration: 7:16 = 7.27 minutes (3.93 + 3.33)
└── Combined DPM: 2483 ÷ 7.27 = 341.5 DPM ✅
```

---

## 🔧 **THE SOLUTION**

### **Phase 1: Differential Calculation**
1. **Detect Round 2 files** by filename pattern
2. **Find matching Round 1 file** by map/timestamp proximity  
3. **Calculate Round 2 ONLY stats** = Round 2 cumulative - Round 1
4. **Use Round 2 actual_time** for DPM calculation

### **Phase 2: Database Structure**
```sql
-- Three types of records:
player_round_stats    -- Individual round performance  
player_map_stats      -- Combined map session totals
sessions              -- Match session metadata
```

### **Phase 3: Bot Commands**
- `!stats player round1` - Round 1 only stats
- `!stats player round2` - Round 2 only stats  
- `!stats player total` - Combined map stats
- `!top_dpm` - Realistic DPM leaderboard (200-800 range)

---

## 🏗️ **IMPLEMENTATION PLAN**

### **Step 1: Enhanced Parser**
- [ ] Add Round 2 detection logic
- [ ] Implement differential calculation
- [ ] Fix DPM calculation for differential rounds
- [ ] Test with provided test files

### **Step 2: Database Rebuild**
- [ ] Delete corrupted database
- [ ] Re-import all stats with fixed parser
- [ ] Verify realistic DPM values (200-800 range)
- [ ] Test 3-tier command system

### **Step 3: Bot Deployment**
- [ ] Test all 56+ commands
- [ ] Verify Discord integration
- [ ] Deploy to production
- [ ] Monitor performance

---

## 📁 **KEY FILES**

### **Core Bot:**
- `bot/ultimate_bot.py` - Main bot (831 lines, production ready)
- `bot/community_stats_parser.py` - Stats parser (needs differential fix)

### **Database:**
- `database/etlegacy_perfect.db` - Current (has inflated DPM)
- Will be replaced with corrected database

### **Test Data:**
- `test_files/*.txt` - c0rnp0rn3.lua generated stats files
- Confirmed cumulative bug in Round 2 files

### **Tools:**
- `tools/fixed_differential_calculator.py` - Previous attempt at fix
- `tools/fixed_bulk_import.py` - Database import system

---

## 🎯 **SUCCESS CRITERIA**

### **When Complete:**
- [ ] `!top_dpm` shows 200-800 DPM (not 30,000+)
- [ ] Round 2 stats show only Round 2 performance
- [ ] Combined stats accurately sum both rounds
- [ ] All 1,168+ sessions correctly imported
- [ ] Bot ready for production Discord deployment

### **Expected DPM Ranges:**
- **Defensive/Support**: 100-300 DPM
- **Average Fraggers**: 300-600 DPM  
- **High Performers**: 600-1000 DPM
- **Exceptional**: 1000+ DPM (rare)

---

## 💡 **KEY INSIGHTS**

1. **Parser is mathematically correct** - problem was cumulative data
2. **c0rnp0rn3.lua behavior is known** - Round 2 includes Round 1
3. **Stopwatch timing understood** - each round has independent duration
4. **Database needs rebuild** - not just DPM correction
5. **Bot infrastructure solid** - 80% ready for production

---

## 🚀 **NEXT ACTIONS**

**IMMEDIATE**: Implement differential calculation in parser
**THEN**: Test with provided Round 1/2 file pairs  
**FINALLY**: Rebuild database and deploy bot

**The bot is ready - we just need to fix the cumulative stats bug!** 🎮