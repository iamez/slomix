# 🗺️ PROJECT CRITICAL FILES MAP
**Created**: October 4, 2025  
**Purpose**: Map out EXACTLY which files are critical for bot operation and documentation  
**Context**: 200+ files in workspace, need to identify what matters

---

## 🎯 THE COMPLETE PICTURE

### What We Have Now (October 4, 2025):
- ✅ **Working System**: Bot + Database + Import + 12,402 records
- ✅ **Unified Schema**: 3 tables, 53 columns in player_comprehensive_stats
- ✅ **All Stats Working**: Revives, assists, dynamites all populated
- ❌ **Documentation Problem**: All docs reference OLD split schema

### What Caused Today's Confusion:
1. **Three different database schemas** existed with no explanation
2. **Three different import scripts** with no guidance on which to use
3. **All documentation outdated** - referenced wrong schema
4. **No troubleshooting guide** for schema issues

### The Goal:
> "Ultimate doc/readme for this project... instructions for ai agents... to avoid future long sessions of back and forth chatting"

---

## 🔴 TIER 1: CRITICAL - BOT RUNTIME FILES

**These files are REQUIRED for the Discord bot to run:**

### 1. `bot/ultimate_bot.py` (Main Bot - 830+ lines)
**What it does**: Discord bot application  
**Dependencies**: 
- `bot/community_stats_parser.py` (for parsing stats files)
- `bot/image_generator.py` (for generating session images)
- `etlegacy_production.db` (database)

**Key Functions**:
- Command handlers (!last_session, !stats, !leaderboard, etc.)
- Database queries (expects UNIFIED schema)
- Discord embed generation
- Auto-linking system

**Critical Schema Expectations**:
```python
# Line 719: Queries sessions table
SELECT DISTINCT session_date FROM sessions

# Line 1056-1061: Queries player_comprehensive_stats
SELECT ... FROM player_comprehensive_stats WHERE session_id IN (...)
# EXPECTS: All objective stats in ONE table (unified schema)
```

**Status**: ✅ Working, queries unified schema correctly

---

### 2. `bot/community_stats_parser.py` (Parser - 724 lines)
**What it does**: Parses c0rnp0rn3.lua stats output files  
**Input**: `.txt` files like `2025-10-02-211808-etl_adlernest-round-1.txt`  
**Output**: Python dictionary with all stats

**Key Capabilities**:
- Parses header (map, round, time)
- Extracts player stats (38 fields after weapon data)
- Handles weapon stats
- Round 2 differential calculation

**Important**: Parser is CORRECT - extracts all 38 fields properly

**Status**: ✅ Working correctly

---

### 3. `bot/image_generator.py` (Image Generation - 313 lines)
**What it does**: Creates session summary images using PIL  
**Purpose**: Visual session cards for Discord embeds

**Status**: ✅ Exists, functionality confirmed

---

### 4. `etlegacy_production.db` (Production Database)
**What it contains**: 
- **Tables**: 6 tables (5 real + 1 sqlite_sequence)
  1. `sessions` - Game sessions
  2. `player_comprehensive_stats` - **53 columns** (UNIFIED schema)
  3. `weapon_comprehensive_stats` - Weapon details
  4. `player_links` - Discord user linking
  5. `processed_files` - Import tracking

**Current Status**:
```
Total player records: 12,402
Revives: 15,661 ✅
Assists: 23,606 ✅
Dynamites: 4,095 ✅
Useless Kills: 22,076 ✅
```

**Critical Schema Detail**:
- `player_comprehensive_stats` has **53 columns** (52 data + id)
- **INCLUDES all objective stats** (no separate player_objective_stats table)
- This is **UNIFIED schema** - bot expects this

**Status**: ✅ Correct schema, fully populated

---

### 5. `.env` (Environment Configuration)
**What it contains**:
- `DISCORD_TOKEN` - Bot authentication
- Database paths
- Server configuration

**Status**: ✅ Exists

---

## 🟡 TIER 2: CRITICAL - DATA PIPELINE FILES

**These files are REQUIRED to import new stats:**

### 6. `tools/simple_bulk_import.py` (Import Script - 340 lines)
**What it does**: Imports stats files into database  
**Uses**: `bot/community_stats_parser.py`  
**Target**: `etlegacy_production.db` (UNIFIED schema)

**Critical Features**:
- Inserts **51 values** into player_comprehensive_stats (matches 53-column schema: 51 data + id + created_at auto)
- Uses correct field mapping
- Handles Round 2 differential
- Tracks processed files

**Field Mapping** (Lines 120-173):
```python
values = (
    session_id,                    # 1
    session_date,                  # 2
    result['map_name'],            # 3
    result['round_num'],           # 4
    player_guid,                   # 5
    player_name,                   # 6
    clean_name,                    # 7
    team,                          # 8
    kills,                         # 9
    deaths,                        # 10
    # ... 41 more fields ...
    death_spree                    # 51
)
```

**Status**: ✅ **THIS IS THE CORRECT IMPORT SCRIPT TO USE**

---

### 7. `local_stats/` (Stats Files Directory)
**What it contains**: `.txt` files from game server  
**File format**: `2025-10-02-211808-etl_adlernest-round-1.txt`  
**Total files**: 1,862 files (all imported)

**Status**: ✅ All files processed

---

## 🔵 TIER 3: IMPORTANT - SUPPORTING FILES

**These files support operations but aren't runtime-critical:**

### 8. `create_unified_database.py` (Database Creator)
**What it does**: Creates fresh database with UNIFIED schema  
**Creates**:
- `sessions` table (7 fields)
- `player_comprehensive_stats` table (53 columns total)
- `weapon_comprehensive_stats` table
- `player_links` table
- `processed_files` table

**When to use**: When recreating database from scratch

**Status**: ✅ Successfully created current production DB

---

### 9. `requirements.txt` (Dependencies)
**What it contains**:
```
discord.py>=2.3.0
aiosqlite
matplotlib
Pillow
```

**Status**: ✅ Exists

---

## ⚪ TIER 4: DEPRECATED/WRONG - DO NOT USE

**These files use WRONG schema or are outdated:**

### ❌ `dev/bulk_import_stats.py` 
**Problem**: Imports into SPLIT schema (4 tables, 35 columns)  
**Why it exists**: Old approach before unified schema  
**Status**: ❌ **DO NOT USE** - Wrong schema

### ❌ `tools/fixed_bulk_import.py`
**Problem**: Imports into different database (etlegacy_fixed_bulk.db)  
**Why it exists**: Experimental approach  
**Status**: ❌ **DO NOT USE** - Different DB

---

## 📚 TIER 5: DOCUMENTATION FILES

### Current Documentation Status:

#### ❌ **OUTDATED** (Need complete rewrite):
1. `COPILOT_INSTRUCTIONS.md` (509 lines) - References SPLIT schema
2. `DATABASE_EXPLAINED.md` (443 lines) - Shows 4 tables, 35 columns
3. `docs/DATABASE_SCHEMA.md` - Likely references old schema

#### ⚠️ **NEEDS UPDATE**:
4. `README.md` (121 lines) - Statistics outdated (1,168 vs 12,402 records)

#### ✅ **VALUABLE** (Need to review):
5. `docs/BOT_COMPLETE_GUIDE.md` - Bot documentation
6. `docs/PARSER_DOCUMENTATION.md` - Parser technical docs
7. `docs/C0RNP0RN3_ANALYSIS.md` - Lua script analysis

#### 📋 **STATUS FILES** (50+ files, need consolidation):
- `BULK_IMPORT_FIX_COMPLETE.md`
- `IMPORT_READY.md`
- `FIX_COMPLETE_SUMMARY.md`
- `FIXES_COMPLETE.md`
- ... 46 more similar files

**Problem**: Too scattered, conflicting info, hard to find answers

---

## 🗂️ DIRECTORY STRUCTURE - WHAT MATTERS

```
stats/
├── 🔴 bot/                           # CRITICAL - Bot runtime
│   ├── ultimate_bot.py              # Main bot (MUST HAVE)
│   ├── community_stats_parser.py    # Parser (MUST HAVE)
│   ├── image_generator.py           # Images (MUST HAVE)
│   └── etlegacy_production.db       # Database (MUST HAVE)
│
├── 🟡 tools/                         # CRITICAL - Data pipeline
│   ├── simple_bulk_import.py        # ✅ CORRECT import script
│   ├── fixed_bulk_import.py         # ❌ WRONG - different DB
│   └── ... other tools
│
├── 🟡 local_stats/                   # CRITICAL - Stats files
│   └── 2025-*.txt                   # 1,862 files
│
├── 🔵 docs/                          # IMPORTANT - Documentation
│   ├── BOT_COMPLETE_GUIDE.md
│   ├── DATABASE_SCHEMA.md           # ❌ Needs update
│   ├── PARSER_DOCUMENTATION.md
│   └── ... 11 more docs
│
├── ⚪ dev/                           # DEPRECATED - Old code
│   └── bulk_import_stats.py        # ❌ WRONG - split schema
│
├── 🔴 etlegacy_production.db         # CRITICAL - Production DB
├── 🔴 .env                           # CRITICAL - Bot token
├── 🔵 README.md                      # IMPORTANT - Main docs
├── ❌ COPILOT_INSTRUCTIONS.md        # OUTDATED
├── ❌ DATABASE_EXPLAINED.md          # OUTDATED
│
└── ... 180+ other files             # Test scripts, analysis, status docs
```

---

## 🎯 THE THREE SCHEMAS PROBLEM (Root Cause of Today's Confusion)

### Schema Evolution History:

#### **Schema 1: SPLIT** (Deprecated - October 2024)
```
Tables: 4
- sessions
- player_comprehensive_stats (35 columns)
- weapon_comprehensive_stats
- player_objective_stats (27 columns)

Problem: Bot queries only player_comprehensive_stats, misses objectives
Import Script: dev/bulk_import_stats.py
Status: ❌ DEPRECATED
```

#### **Schema 2: UNIFIED** (Current - October 4, 2025)
```
Tables: 3
- sessions (7 fields)
- player_comprehensive_stats (53 columns - includes ALL objectives)
- weapon_comprehensive_stats

Advantage: All stats in one table, bot can query everything
Import Script: tools/simple_bulk_import.py
Status: ✅ CURRENT PRODUCTION
Database: etlegacy_production.db
```

#### **Schema 3: ENHANCED** (Experimental)
```
Tables: Different structure
- player_round_stats (per-round granularity)

Import Script: tools/fixed_bulk_import.py
Database: etlegacy_fixed_bulk.db (separate file)
Status: ⚠️ Experimental, not bot-compatible
```

### Why This Was Confusing:

**No documentation explained**:
1. ❌ Which schema the bot expects (Answer: UNIFIED)
2. ❌ Why three schemas exist (Answer: Evolution, experimentation)
3. ❌ Which import script to use (Answer: tools/simple_bulk_import.py)
4. ❌ How to verify compatibility (Answer: Check table structure)

**Result**: User recreated DB with wrong schema, multiple failed imports, long debugging session

---

## 🔍 HOW TO VERIFY YOUR SETUP

### Check Database Schema:
```powershell
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('PRAGMA table_info(player_comprehensive_stats)'); cols = cursor.fetchall(); print(f'Columns: {len(cols)}'); print('Has unified schema!' if len(cols) == 53 else 'WRONG SCHEMA!')"
```

**Expected Output**: `Columns: 53` and `Has unified schema!`

### Check Import Script:
```powershell
# CORRECT:
python tools/simple_bulk_import.py local_stats/2025-*.txt

# WRONG:
python dev/bulk_import_stats.py  # Uses split schema!
```

### Check Bot Compatibility:
```powershell
# Bot expects these queries to work:
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('SELECT times_revived FROM player_comprehensive_stats LIMIT 1'); print('✅ Bot-compatible!' if cursor.fetchone() else '❌ Wrong schema!')"
```

---

## 📋 QUICK REFERENCE FOR AI AGENTS

### Q: Which database schema does the bot use?
**A**: UNIFIED schema (3 tables, 53 columns in player_comprehensive_stats)

### Q: Which import script should I use?
**A**: `tools/simple_bulk_import.py`

### Q: How many columns in player_comprehensive_stats?
**A**: 53 total (52 data + id, created_at is auto-generated separately)

### Q: Where is the production database?
**A**: `etlegacy_production.db` in root directory

### Q: What if stats show zeros?
**A**: Check schema - bot expects unified schema with all stats in player_comprehensive_stats

### Q: What if import fails with "column count mismatch"?
**A**: You're using wrong import script. Use `tools/simple_bulk_import.py`

### Q: How do I recreate the database?
**A**: Run `python create_unified_database.py`, then `python tools/simple_bulk_import.py local_stats/*.txt`

---

## 🎓 KEY INSIGHTS FOR DOCUMENTATION

### What Must Be In Ultimate Documentation:

1. **Schema Quick Reference** (First thing AI agents need)
   - Current schema: UNIFIED (3 tables, 53 columns)
   - Why this schema: Bot queries all stats from one table
   - How to verify: Check column count

2. **Critical File List** (This document)
   - Bot runtime: 5 files
   - Data pipeline: 2 files + directory
   - Everything else: Supporting/deprecated

3. **Schema Evolution History** (Prevents confusion)
   - Why three schemas exist
   - Which one is current
   - Migration story

4. **Import Script Selection** (Critical decision point)
   - Correct: tools/simple_bulk_import.py
   - Wrong: dev/bulk_import_stats.py (split schema)
   - Wrong: tools/fixed_bulk_import.py (different DB)

5. **Troubleshooting Decision Tree**
   - Stats zeros → Check schema
   - Import fails → Check script selection
   - Bot errors → Check database compatibility

6. **Verification Commands** (How to check everything)
   - Schema check
   - Import verification
   - Bot compatibility test

---

## 🚦 SYSTEM HEALTH STATUS (October 4, 2025)

### ✅ WORKING:
- Discord bot runtime
- Parser (all 38 fields extracted)
- Database (unified schema, 12,402 records)
- Import pipeline (all 1,862 files processed)
- Objective stats (15,661 revives, 23,606 assists, etc.)

### ❌ BROKEN:
- Documentation (all references outdated split schema)
- Schema explanation (no docs explain unified vs split)
- Import guidance (no docs say which script to use)

### 🎯 NEEDED:
- AI_AGENT_GUIDE.md (quick answers)
- Updated COPILOT_INSTRUCTIONS.md (unified schema)
- Updated DATABASE_EXPLAINED.md (3 tables, 53 columns)
- Troubleshooting guide (schema issues)
- Consolidated changelog (from 50+ status files)

---

## 🎯 FOR AI AGENTS READING THIS

### If you're asked to work on this project:

1. **ALWAYS use UNIFIED schema** (3 tables, 53 columns)
2. **ALWAYS use tools/simple_bulk_import.py** for imports
3. **NEVER use dev/bulk_import_stats.py** (wrong schema)
4. **Database location**: `etlegacy_production.db` in root
5. **Bot expects**: All stats in player_comprehensive_stats (no separate objectives table)

### If something breaks:

1. **Check schema first**: `PRAGMA table_info(player_comprehensive_stats)` should return 53 columns
2. **Check import script**: Should be tools/simple_bulk_import.py
3. **Check database**: Should be etlegacy_production.db (not etlegacy_fixed_bulk.db)

### Before making changes:

1. **Backup database**: `database_backups/` folder
2. **Verify schema**: Check column count matches 53
3. **Test on single file**: Don't bulk import until verified

---

## 📊 FILE COUNT SUMMARY

**Total files in workspace**: 200+

**Critical files**: 12
- Runtime: 5 files
- Pipeline: 2 files + 1 directory
- Support: 5 files

**Documentation**: 64+
- Core docs: 3 files (all outdated)
- Technical docs: 14 files (need review)
- Status files: 50+ files (need consolidation)

**Deprecated**: 2+ files
- dev/bulk_import_stats.py (wrong schema)
- tools/fixed_bulk_import.py (different DB)

**Test/Analysis**: 130+ files
- Various test scripts
- Data analysis scripts
- Debug utilities

---

## ✅ COMPLETION CHECKLIST

**Understanding Complete When You Can Answer**:

- [ ] Which schema does the bot use? → UNIFIED (3 tables, 53 columns)
- [ ] Which import script to use? → tools/simple_bulk_import.py
- [ ] How many tables in production DB? → 3 (+ 2 support tables)
- [ ] Where are objective stats stored? → player_comprehensive_stats (not separate table)
- [ ] Why three schemas exist? → Evolution and experimentation
- [ ] What caused today's confusion? → No docs explained schema differences
- [ ] How to verify schema? → Check column count = 53
- [ ] What files are critical? → 12 files (5 runtime, 2 pipeline, 5 support)

---

**READY TO CREATE ULTIMATE DOCUMENTATION**: ✅

Now we have complete context:
1. ✅ Know exactly which files matter
2. ✅ Understand schema confusion problem
3. ✅ Mapped out entire system
4. ✅ Identified what's missing from docs
5. ✅ Clear on what needs to be created

**Next**: Create AI_AGENT_GUIDE.md with all these quick answers
