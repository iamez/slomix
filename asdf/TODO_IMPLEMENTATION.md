# 📋 TODO LIST - ETLegacy Bot Cumulative Stats Fix

**Priority**: HIGH - Bot ready for production after this fix
**Target**: Complete within 1-2 work sessions

---

## 🔧 **PHASE 1: PARSER ENHANCEMENT**

### ✅ **COMPLETED**
- [x] Identified cumulative stats bug in Round 2 files
- [x] Confirmed c0rnp0rn3.lua behavior with test data
- [x] Understood stopwatch mode timing mechanics
- [x] Verified parser DPM calculation is mathematically correct

### 🚧 **IN PROGRESS**
- [ ] **Implement Round 2 Detection Logic**
  - Add method to detect Round 2 files by filename pattern
  - Parse timestamp and map name for Round 1/2 pairing
  - Handle edge cases (missing Round 1, orphan Round 2)

- [ ] **Add Differential Calculation**
  - Subtract Round 1 stats from Round 2 cumulative stats
  - Calculate Round 2-only damage, kills, deaths, etc.
  - Preserve Round 2 actual_time for DPM calculation

- [ ] **Enhanced Parse Methods**
  - Update `parse_stats_file()` to return round type
  - Add `calculate_round2_differential()` method
  - Test with provided te_escape2 Round 1/2 pair

---

## 🗄️ **PHASE 2: DATABASE REBUILD**

### 📋 **PREPARATION**
- [ ] **Backup Current Database**
  - Save etlegacy_perfect.db as etlegacy_corrupted_backup.db
  - Document current statistics for comparison

- [ ] **Test Import System**
  - Test fixed parser with test_files/ data
  - Verify realistic DPM values (200-800 range)
  - Ensure Round 1/Round 2/Combined stats all correct

### 🔄 **REBUILD PROCESS**
- [ ] **Delete Corrupted Database**
  - Remove etlegacy_perfect.db
  - Create fresh database with correct schema

- [ ] **Re-import All Stats**
  - Process all local_stats/ files with fixed parser
  - Import 1,168+ sessions with corrected calculations
  - Verify no DPM values exceed 2000

- [ ] **Validation Testing**
  - Test `!top_dpm` shows realistic values
  - Verify 3-tier command system works
  - Check session management functions

---

## 🤖 **PHASE 3: BOT DEPLOYMENT**

### 🧪 **TESTING**
- [ ] **Command Validation**
  - Test all 56+ bot commands
  - Verify `!stats player round1/round2/total` works
  - Check MVP system, leaderboards, auto-linking

- [ ] **Performance Testing**
  - Test Discord connection with real token
  - Verify database query performance
  - Check error handling and logging

### 🚀 **PRODUCTION DEPLOYMENT**
- [ ] **Environment Setup**
  - Configure production .env settings
  - Set up proper Discord bot permissions
  - Test in development Discord server first

- [ ] **Go Live**
  - Deploy to production Discord server
  - Monitor logs for errors
  - Announce corrected DPM system to users

---

## 📊 **SUCCESS METRICS**

### 🎯 **Technical Validation**
- [ ] DPM values in 100-1000 range (not 30,000+)
- [ ] Round 2 stats show differential (not cumulative)
- [ ] Combined map stats = Round 1 + Round 2
- [ ] Database contains all 1,168+ sessions

### 👥 **User Experience**
- [ ] `!top_dpm` shows believable leaderboard
- [ ] Commands respond within 2-3 seconds
- [ ] No error messages in normal usage
- [ ] MVP awards work correctly

---

## ⚠️ **RISK MITIGATION**

### 🛡️ **BACKUP STRATEGY**
- Keep corrupted database for rollback if needed
- Test all changes in development environment first
- Document all modifications for troubleshooting

### 🔍 **VALIDATION CHECKS**
- Compare before/after DPM distributions
- Verify math with manual calculations
- Test edge cases (single round, disconnected players)

---

## 📅 **TIMELINE ESTIMATE**

- **Phase 1 (Parser)**: 2-3 hours
- **Phase 2 (Database)**: 1-2 hours  
- **Phase 3 (Deployment)**: 1 hour
- **Total**: 4-6 hours of focused work

---

## 🎯 **CURRENT FOCUS**

**NEXT IMMEDIATE TASK**: 
Implement Round 2 detection and differential calculation in `community_stats_parser.py`

**READY TO START**: Parser enhancement with test file validation