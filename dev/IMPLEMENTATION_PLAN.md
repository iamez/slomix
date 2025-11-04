# ET:Legacy Discord Bot - Implementation Plan & Action List
**Generated:** October 3, 2025  
**Status:** Ready to Begin Implementation

---

## 📋 CURRENT STATUS SUMMARY

### ✅ What's Working
- ✅ **Parser fixed** - All 5 test files parsed successfully (including Round 2 differential)
- ✅ **3,218 stat files ready** (1,842 from 2025, 1,376 from 2024)
- ✅ **20 unique maps** identified in 2025 data
- ✅ **Discord bot structure** exists with cog pattern
- ✅ **SSH configuration** ready
- ✅ **Database schema** comprehensive and well-designed

### ⚠️ Issues Found
- ⚠️ **8 database files** exist - needs consolidation
- ⚠️ **No bulk import tool** - can't populate database yet
- ⚠️ **Discord commands** not implemented

### 🎯 Validation Results
```
Databases found: 8
  • etlegacy_comprehensive.db (76 KB) - 50 player stats, 300 weapon stats
  • etlegacy_discord_ready.db (48 KB) - 3 sessions, empty stats
  • etlegacy_perfect.db (96 KB) - 52 player stats
  • dev/etlegacy_comprehensive.db (56 KB) - 48 player stats, 10 links
  • Multiple empty databases

Parser tests: 5/5 successful ✅
Issues: 0 ✅
```

---

## 🚀 PHASE 1: DATABASE FOUNDATION (Priority: CRITICAL)

### Task 1.1: Create Production Database ✅ READY TO DO
**File:** `dev/create_production_database.py`

**What it does:**
- Creates `etlegacy_production.db` with comprehensive schema
- Based on `initialize_database.py` schema (already perfect)
- Adds indexes for performance
- Documents every table and field

**Schema Tables:**
1. **sessions** - Match/round metadata
2. **player_comprehensive_stats** - ALL player stats (43+ fields)
3. **weapon_comprehensive_stats** - Per-weapon stats (28 weapons)
4. **player_links** - Discord ↔ GUID mapping
5. **processed_files** - Import tracking

**Estimated time:** 30 minutes  
**Dependencies:** None  
**Risk:** Low

---

### Task 1.2: Build Bulk Import Tool ✅ READY TO DO
**File:** `dev/bulk_import_stats.py`

**What it does:**
- Scans `local_stats/` folder
- Parses all `.txt` files using `community_stats_parser.py`
- Inserts into `etlegacy_production.db`
- Progress tracking (console + log file)
- Duplicate detection (skip already processed files)
- Error handling (continues on failures, logs issues)
- Summary report at end

**Features:**
```python
- Parse 3,218 files
- Extract ~25,000+ player records
- Extract ~200,000+ weapon stats
- Track progress: [=====>....] 45% (1450/3218)
- Error recovery: Continue on parse failures
- Performance: ~100 files/minute
- Estimated runtime: 35 minutes for full import
```

**Configuration options:**
```python
--year 2025          # Only import 2025 files (for testing)
--limit 100          # Only import first 100 files
--resume             # Resume from last processed file
--verify             # Verify database after import
--clean              # Delete database and start fresh
```

**Estimated time:** 2-3 hours to build, 35 minutes to run  
**Dependencies:** Task 1.1 complete  
**Risk:** Medium (complex parsing logic)

---

### Task 1.3: Database Verification Tool ✅ READY TO DO
**File:** `dev/verify_database_integrity.py`

**What it does:**
- Counts records in all tables
- Validates foreign keys
- Checks for orphaned records
- Identifies duplicate entries
- Statistics per map, per player
- Data quality report

**Sample output:**
```
✅ Database: etlegacy_production.db
📊 Sessions: 1,609 matches
👥 Players: 25,432 records (347 unique GUIDs)
🔫 Weapon stats: 203,481 records
🔗 Player links: 10 Discord users linked
📁 Processed files: 3,218

📈 Data Quality:
   ✅ No orphaned records
   ✅ All foreign keys valid
   ⚠️  23 duplicate player names (same GUID, OK)
   ✅ Average 15.8 players per session
   
🗺️  Top 5 Maps:
   1. te_escape2: 522 matches
   2. etl_adlernest: 289 matches
   3. supply: 229 matches
   4. etl_sp_delivery: 215 matches
   5. sw_goldrush_te: 195 matches
```

**Estimated time:** 1 hour  
**Dependencies:** Task 1.2 complete  
**Risk:** Low

---

## 🎮 PHASE 2: DISCORD BOT COMMANDS (Priority: HIGH)

### Task 2.1: Implement `/stats` Command
**File:** `bot/ultimate_bot.py` (modify existing cog)

**Command signature:**
```python
/stats [@user or player_name] [timeframe]
```

**Examples:**
```
/stats @Puran                    # Stats for Discord user
/stats .wjs                      # Stats for player name
/stats @Puran today              # Today's stats only
/stats vid week                  # Last 7 days
/stats                           # Your own stats (if linked)
```

**What it shows:**
```
🎯 Player Stats: .wjs (Last 7 days)
════════════════════════════════════════
⚔️ Combat: 247K / 189D (K/D: 1.31) 🔥
💊 Damage: 45,823 dealt / 38,192 taken
🎯 Accuracy: 32.4% (2,847 hits / 8,779 shots)
💀 Headshots: 156 (6.3% of kills)

🏆 Best Performances:
   • Best K/D: 2.85 (supply, Jan 15)
   • Most Kills: 34 (etl_adlernest, Jan 20)
   • Best Streak: 12 kills

🔫 Favorite Weapons:
   1. MP40: 182K (35.2% acc) ⚡
   2. Thompson: 48K (31.8% acc)
   3. Luger: 12K (38.1% acc) 🎯

📊 Matches: 42 games (7.2 hrs played)
```

**Estimated time:** 3-4 hours  
**Dependencies:** Phase 1 complete  
**Risk:** Medium (Discord embed formatting)

---

### Task 2.2: Implement `/leaderboard` Command
**File:** `bot/ultimate_bot.py` (add to cog)

**Command signature:**
```python
/leaderboard [stat_type] [timeframe] [map]
```

**Examples:**
```
/leaderboard kills               # Top 10 by kills (all time)
/leaderboard kd week             # Top 10 K/D last 7 days
/leaderboard accuracy supply     # Top 10 accuracy on Supply map
/leaderboard headshots month     # Top 10 headshots this month
```

**Stat types:**
- `kills`, `kd`, `accuracy`, `headshots`, `dpm` (damage per minute)
- `efficiency`, `playtime`, `wins`, `streaks`

**What it shows:**
```
🏆 Leaderboard: Most Kills (All Time)
════════════════════════════════════════
🥇 .wjs          2,847 kills (K/D: 1.42)
🥈 vid           2,634 kills (K/D: 1.38)
🥉 s&o.lgz       2,521 kills (K/D: 1.29)
4️⃣ SuperBoyy    2,418 kills (K/D: 1.51) 🔥
5️⃣ .olz         2,103 kills (K/D: 1.18)
6️⃣ carniee      1,982 kills (K/D: 1.33)
7️⃣ bronze.      1,876 kills (K/D: 1.24)
8️⃣ endekk       1,654 kills (K/D: 1.16)
9️⃣ XI-WANG      1,421 kills (K/D: 1.08)
🔟 i p k i s s  1,298 kills (K/D: 0.94)

📊 Based on 1,842 matches since Jan 2025
```

**Estimated time:** 2-3 hours  
**Dependencies:** Task 2.1 complete  
**Risk:** Low

---

### Task 2.3: Implement `/match` Command
**File:** `bot/ultimate_bot.py` (add to cog)

**Command signature:**
```python
/match [date or session_id]
```

**Examples:**
```
/match 1234                      # Match ID 1234
/match 2025-01-15                # All matches on Jan 15
/match latest                    # Most recent match
/match                           # Latest match you played
```

**What it shows:**
```
📍 Match #1234: etl_adlernest (Round 2)
════════════════════════════════════════
📅 Date: Jan 15, 2025, 21:30
⏱️  Duration: 5:32
🏆 Winner: Allies ✅
🛡️  Defenders: Axis

🌟 MVP: .wjs (18K/9D, 2.0 K/D) 🔥

🎯 Top Performers:
🥇 🔴 .wjs         18K/9D  (2.00)
🥈 🔵 vid          15K/11D (1.36)
🥉 🔴 SuperBoyy    14K/10D (1.40)

📊 Team Stats:
   Axis:   42 kills, 3,821 damage
   Allies: 38 kills, 3,542 damage
   
👥 6 players
```

**Estimated time:** 2 hours  
**Dependencies:** Task 2.1 complete  
**Risk:** Low

---

### Task 2.4: Implement `/compare` Command
**File:** `bot/ultimate_bot.py` (add to cog)

**Command signature:**
```python
/compare [@user1 or name1] [@user2 or name2] [timeframe]
```

**Examples:**
```
/compare @Puran @Vid
/compare .wjs SuperBoyy week
/compare endekk .olz month supply
```

**What it shows:**
```
⚔️ Head-to-Head: .wjs vs vid (All Time)
════════════════════════════════════════
                .wjs      vs      vid
Kills:          2,847            2,634   🔴
Deaths:         2,005            1,908   
K/D Ratio:      1.42             1.38    🔴
Accuracy:       32.4%            35.1%   🔵
Headshots:      156              187     🔵
Damage/Min:     428              445     🔵
Best Streak:    12               15      🔵
Playtime:       42.3 hrs         38.7 hrs 🔴

🗺️ Best Maps:
.wjs:    supply (K/D: 1.85)
vid:     etl_adlernest (K/D: 1.72)

⚔️ Direct Encounters: 12 matches together
   .wjs wins: 7
   vid wins: 5
```

**Estimated time:** 3 hours  
**Dependencies:** Task 2.1 complete  
**Risk:** Medium (complex queries)

---

### Task 2.5: Implement `/history` Command
**File:** `bot/ultimate_bot.py` (add to cog)

**Command signature:**
```python
/history [@user or player_name] [stat_type]
```

**Examples:**
```
/history @Puran kd
/history .wjs accuracy
/history vid
```

**What it shows:**
- Graph (ASCII or image) of performance over time
- Trends (improving, declining, stable)
- Milestones (first match, 1000th kill, etc.)

**Sample:**
```
📈 Performance History: .wjs (K/D Ratio)
════════════════════════════════════════
Jan 2025 ━━━━━━━━━━━━━━━━━━━━━━━ 30 days
1.60│                    ╭─╮
1.50│                ╭───╯ ╰─╮
1.40│           ╭────╯        ╰─╮
1.30│       ╭───╯                ╰──╮
1.20│   ╭───╯                       ╰╮
1.10│───╯                            ╰─
    └─────────────────────────────────
    1/1                          1/30

📊 Stats:
   Average K/D: 1.42
   Trend: ↗️ Improving (+0.18 this month)
   Best day: Jan 28 (1.85 K/D)
   Matches: 42
```

**Estimated time:** 4-5 hours (if creating ASCII graphs)  
**Dependencies:** Task 2.1 complete  
**Risk:** High (visualization complexity)

---

## 🔗 PHASE 3: PLAYER LINKING (Priority: MEDIUM)

### Task 3.1: Implement `/link` Command
**File:** `bot/ultimate_bot.py` (add to cog)

**Purpose:** Allow players to link their Discord account to their in-game GUID

**Command signature:**
```python
/link [player_name]
/link                    # Show current link
/unlink                  # Remove link
```

**Flow:**
1. User runs `/link .wjs`
2. Bot searches database for GUID with that name
3. If multiple GUIDs found (aliases), shows list
4. User confirms which GUID
5. Bot stores link in `player_links` table

**Example interaction:**
```
User: /link .wjs

Bot: 
🔍 Found player: .wjs
GUID: FDA127DF
Recent names: .wjs, wjs, ^3.w^7js
Matches played: 127
Last seen: Jan 30, 2025

React with ✅ to confirm linking your Discord account
to this in-game profile.
```

**Estimated time:** 2 hours  
**Dependencies:** Phase 1 complete  
**Risk:** Low

---

### Task 3.2: GUID Alias Management
**File:** `dev/manage_player_aliases.py`

**Purpose:** Administrative tool to merge/view player aliases

**Features:**
```python
- View all names for a GUID
- View all GUIDs for a name pattern
- Merge multiple GUIDs (if same person, different GUIDs)
- Export player directory
```

**Estimated time:** 2 hours  
**Dependencies:** Phase 1 complete  
**Risk:** Low

---

## 🔄 PHASE 4: AUTOMATION (Priority: MEDIUM)

### Task 4.1: SSH File Monitor
**Status:** Code exists in `ultimate_bot.py`, needs testing

**What it does:**
- Every 5 minutes, checks `/home/et/.etlegacy/legacy/gamestats/`
- Downloads new `.txt` files to `local_stats/`
- Triggers auto-processing

**Testing needed:**
- SSH connection stability
- File download reliability
- Permission handling
- Error recovery

**Estimated time:** 2 hours testing/refinement  
**Dependencies:** Phase 1 complete  
**Risk:** Medium (server connectivity)

---

### Task 4.2: Auto-Processing New Files
**File:** `bot/ultimate_bot.py` (add background task)

**What it does:**
- Watches `local_stats/` folder for new files
- Auto-parses with `community_stats_parser.py`
- Auto-inserts into database
- Checks `processed_files` table to avoid duplicates

**Estimated time:** 2 hours  
**Dependencies:** Task 4.1 complete  
**Risk:** Low

---

### Task 4.3: Auto-Post Round Results
**File:** `bot/ultimate_bot.py` (add to auto-processing)

**What it does:**
- After processing new file, posts to configured Discord channel
- Uses existing embed creation from `community_stats_parser.py`
- Configurable: can disable auto-posting

**Example:**
```
[New round complete! → #stats-channel]

🏆 Round 2 Complete
📍 Map: etl_adlernest
🎮 Duration: 5:32
🌟 MVP: .wjs (18K/9D)

[See full stats] button
```

**Estimated time:** 1 hour  
**Dependencies:** Task 4.2 complete  
**Risk:** Low

---

## 📦 PHASE 5: POLISH & DOCUMENTATION (Priority: LOW)

### Task 5.1: User Documentation
**File:** `docs/USER_GUIDE.md`

**Contents:**
- How to link your account
- All available commands with examples
- How to read stats
- Troubleshooting

**Estimated time:** 2 hours  
**Dependencies:** Phase 2 complete  
**Risk:** None

---

### Task 5.2: Admin Documentation
**File:** `docs/ADMIN_GUIDE.md`

**Contents:**
- Setup instructions
- Database management
- Backup procedures
- Troubleshooting SSH issues
- How to manually import files

**Estimated time:** 2 hours  
**Dependencies:** All phases complete  
**Risk:** None

---

### Task 5.3: Code Comments & Docstrings
**Status:** Partially done, needs completion

**What to do:**
- Add docstrings to all functions
- Explain complex logic sections
- Document data structures
- Add type hints

**Estimated time:** 3 hours  
**Dependencies:** None (ongoing)  
**Risk:** None

---

## ⏱️ TIME ESTIMATES

### Phase 1: Database Foundation
- Task 1.1: 0.5 hours
- Task 1.2: 2-3 hours + 0.6 hour runtime
- Task 1.3: 1 hour
**Phase Total: 4-5 hours**

### Phase 2: Discord Commands
- Task 2.1: 3-4 hours
- Task 2.2: 2-3 hours
- Task 2.3: 2 hours
- Task 2.4: 3 hours
- Task 2.5: 4-5 hours (optional)
**Phase Total: 14-17 hours**

### Phase 3: Player Linking
- Task 3.1: 2 hours
- Task 3.2: 2 hours
**Phase Total: 4 hours**

### Phase 4: Automation
- Task 4.1: 2 hours
- Task 4.2: 2 hours
- Task 4.3: 1 hour
**Phase Total: 5 hours**

### Phase 5: Documentation
- Task 5.1: 2 hours
- Task 5.2: 2 hours
- Task 5.3: 3 hours
**Phase Total: 7 hours**

### **GRAND TOTAL: 34-38 hours of development**

---

## 🎯 RECOMMENDED EXECUTION ORDER

### Week 1: Foundation
1. ✅ Create production database (Task 1.1)
2. ✅ Build bulk import tool (Task 1.2)
3. ✅ Run import on 2025 files (testing)
4. ✅ Verify database (Task 1.3)
5. ✅ Run full import (all files)

### Week 2: Core Commands
6. ✅ Implement `/stats` (Task 2.1)
7. ✅ Implement `/leaderboard` (Task 2.2)
8. ✅ Test commands with real data
9. ✅ Implement `/match` (Task 2.3)

### Week 3: Advanced Features
10. ✅ Implement `/compare` (Task 2.4)
11. ✅ Implement `/link` (Task 3.1)
12. ✅ Test automation (Tasks 4.1-4.3)

### Week 4: Polish
13. ✅ Optional: `/history` command (Task 2.5)
14. ✅ Documentation (Phase 5)
15. ✅ Final testing & deployment

---

## 🚨 BLOCKERS & RISKS

### Critical Blockers
- None identified ✅

### Medium Risks
1. **SSH connectivity** - Mitigation: Test early, have manual fallback
2. **Database performance** - Mitigation: Add indexes, optimize queries
3. **Parser edge cases** - Mitigation: Extensive testing, error handling

### Low Risks
1. **Discord rate limits** - Mitigation: Add cooldowns
2. **Large embed size** - Mitigation: Paginate results
3. **Database size** - Mitigation: Archive old data periodically

---

## ✅ NEXT IMMEDIATE ACTIONS

1. **START HERE:** Task 1.1 - Create production database
2. **THEN:** Task 1.2 - Build bulk import tool
3. **THEN:** Run import and verify
4. **THEN:** Choose which command to implement first

**Recommendation:** Start with Phase 1 tasks in sequence. Each takes 30 min - 3 hours, highly parallelizable if working with team.

---

## 📊 SUCCESS METRICS

After completion, we should have:
- ✅ 1 production database with 3,218+ matches
- ✅ 25,000+ player records
- ✅ 200,000+ weapon stats
- ✅ 5+ working Discord commands
- ✅ Automatic file processing
- ✅ Complete documentation
- ✅ Happy users! 🎉

---

**END OF IMPLEMENTATION PLAN**
