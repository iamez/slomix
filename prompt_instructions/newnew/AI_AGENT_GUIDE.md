# 🤖 AI AGENT QUICK REFERENCE GUIDE
**Last Updated**: October 4, 2025  
**Purpose**: Single source of truth for AI agents working on this project  
**Read this FIRST before making ANY changes**

---

## 🚨 CRITICAL INFO (Read This First!)

### Current System (October 4, 2025):
```
✅ Status: FULLY WORKING
✅ Database: etlegacy_production.db (UNIFIED SCHEMA)
✅ Records: 12,414 player records across 1,456 sessions
✅ All objective stats working (revives, assists, dynamites, etc.)
✅ Import script FIXED: Now allows multiple plays per day (Oct 4, 2025)
```

### Database Schema: **UNIFIED** (3 tables, 53 columns)
```
Tables:
  1. sessions (7 fields)
  2. player_comprehensive_stats (53 columns - includes ALL objective stats)
  3. weapon_comprehensive_stats (weapon details)
  4. player_links (Discord linking)
  5. processed_files (import tracking)

Key Detail: ALL STATS IN ONE TABLE (player_comprehensive_stats)
No separate player_objective_stats table!
```

### Import Script: **tools/simple_bulk_import.py**
```powershell
# ✅ CORRECT:
python tools/simple_bulk_import.py local_stats/2025-*.txt

# ❌ WRONG - DO NOT USE:
python dev/bulk_import_stats.py        # Wrong schema (split)
python tools/fixed_bulk_import.py      # Different database
```

---

## ⚡ QUICK ANSWERS (When User Asks...)

### Q: "Which database schema does the bot use?"
**A**: UNIFIED schema (3 tables, 53 columns in player_comprehensive_stats)

### Q: "How many columns in player_comprehensive_stats?"
**A**: 53 total columns:
- Column 1: `id` (auto-increment primary key)
- Columns 2-52: Data fields (session info + player stats + objectives)
- Column 53: `created_at` (timestamp)

### Q: "Where are objective stats stored?"
**A**: In `player_comprehensive_stats` table (columns 31-43):
- kill_assists, objectives_completed, objectives_destroyed
- objectives_stolen, objectives_returned
- dynamites_planted, dynamites_defused
- times_revived, revives_given
- most_useful_kills, useless_kills, kill_steals, denied_playtime

**NOT in a separate table!** (Old split schema had player_objective_stats - that's deprecated)

### Q: "Which import script should I use?"
**A**: `tools/simple_bulk_import.py` - This is the ONLY correct script.

### Q: "Why are there multiple import scripts?"
**A**: Schema evolution:
- `dev/bulk_import_stats.py` - Old split schema (4 tables, 35 columns) ❌
- `tools/simple_bulk_import.py` - Current unified schema (3 tables, 53 columns) ✅
- `tools/fixed_bulk_import.py` - Experimental (different database) ⚠️

### Q: "Stats showing zeros in Discord bot?"
**A**: Schema mismatch! Bot expects unified schema. Check:
```powershell
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('PRAGMA table_info(player_comprehensive_stats)'); print(f'Columns: {len(cursor.fetchall())}'); # Should be 53"
```

### Q: "Import fails with 'column count mismatch'?"
**A**: You're using wrong import script. Use `tools/simple_bulk_import.py`

### Q: "How do I recreate the database?"
**A**: 
```powershell
# 1. Backup current database
cp etlegacy_production.db database_backups/etlegacy_production_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').db

# 2. Create fresh unified schema
python create_unified_database.py

# 3. Import all stats
python tools/simple_bulk_import.py local_stats/2025-*.txt
```

### Q: "What files are critical for the bot to run?"
**A**: Only 5 files:
1. `bot/ultimate_bot.py` - Main bot
2. `bot/community_stats_parser.py` - Parser
3. `bot/image_generator.py` - Image generation
4. `etlegacy_production.db` - Database
5. `.env` - Bot token

---

## 🔍 VERIFICATION COMMANDS

### Check Database Schema:
```powershell
# Should return 53
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('PRAGMA table_info(player_comprehensive_stats)'); cols = cursor.fetchall(); print(f'Columns: {len(cols)}'); print('✅ Unified schema' if len(cols) == 53 else '❌ WRONG SCHEMA!')"
```

### Check Data Population:
```powershell
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM player_comprehensive_stats'); total = cursor.fetchone()[0]; cursor.execute('SELECT SUM(times_revived), SUM(kill_assists), SUM(dynamites_planted) FROM player_comprehensive_stats'); r = cursor.fetchone(); print(f'Total records: {total:,}'); print(f'Revives: {r[0]:,}'); print(f'Assists: {r[1]:,}'); print(f'Dynamites: {r[2]:,}')"
```

### Check Bot Compatibility:
```powershell
# This query should work (bot expects it)
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('SELECT times_revived, kill_assists FROM player_comprehensive_stats LIMIT 1'); result = cursor.fetchone(); print('✅ Bot-compatible!' if result else '❌ Wrong schema!')"
```

### Check Import Script:
```powershell
# Verify you're using the right one
where.exe python
python tools/simple_bulk_import.py --help  # Should work
```

---

## 🚨 TROUBLESHOOTING DECISION TREE

### Problem: "Stats show zeros in Discord bot"
**Diagnosis**: Schema mismatch  
**Solution**:
1. Check column count: `PRAGMA table_info(player_comprehensive_stats)` → Should be 53
2. If not 53: Recreate database with unified schema
3. Re-import all files with `tools/simple_bulk_import.py`

### Problem: "Import fails with 'no such column' error"
**Diagnosis**: Using wrong import script  
**Solution**: Use `tools/simple_bulk_import.py` (NOT dev/bulk_import_stats.py)

### Problem: "Import fails with 'column count mismatch'"
**Diagnosis**: Database has wrong schema OR wrong import script  
**Solution**:
1. Check schema column count (should be 53)
2. Verify using `tools/simple_bulk_import.py`
3. If still fails: Recreate database

### Problem: "Bot can't find objective stats"
**Diagnosis**: Using split schema (old 4-table design)  
**Solution**: Migrate to unified schema (recreate database + re-import)

### Problem: "Round 2 stats showing cumulative instead of differential"
**Diagnosis**: Parser issue (should auto-detect Round 1)  
**Solution**: Parser handles this - check that Round 1 file exists in same directory

### Problem: "Duplicate session error on import"
**Diagnosis**: Session already exists (same date + map + round)  
**Solution**: Normal behavior - script skips duplicates. Check processed_files table.

### Problem: "Missing rounds when multiple plays of same map per day"
**Diagnosis**: Import script was preventing multiple plays of same map on same date  
**Solution**: FIXED (October 4, 2025) - Import script now uses full timestamp for uniqueness  
**Details**: Modified `tools/simple_bulk_import.py` to use YYYY-MM-DD-HHMMSS instead of just YYYY-MM-DD for session identification  
**Example**: Now allows both "2025-10-02-220200-te_escape2" AND "2025-10-02-221225-te_escape2" on same day

---

## 📋 COMPLETE FIELD LIST (53 columns)

### player_comprehensive_stats table:
```
 1. id (PRIMARY KEY, auto-increment)
 2. session_id (FOREIGN KEY → sessions.id)
 3. session_date (date string: YYYY-MM-DD)
 4. map_name (e.g., "etl_adlernest")
 5. round_number (1 or 2)
 6. player_guid (8-character hex ID)
 7. player_name (in-game name with color codes)
 8. clean_name (name without color codes)
 9. team (1=Axis, 2=Allies)
10. kills (total kills)
11. deaths (total deaths)
12. damage_given (damage dealt)
13. damage_received (damage taken)
14. team_damage_given (friendly fire damage dealt)
15. team_damage_received (friendly fire damage taken)
16. gibs (gibbed kills)
17. self_kills (suicide count)
18. team_kills (teamkills)
19. team_gibs (gibbed teamkills)
20. headshot_kills (headshots)
21. time_played_seconds (actual time played in seconds) ⭐ PRIMARY TIME FIELD
22. time_played_minutes (minutes, calculated from seconds)
23. time_dead_minutes (time dead in minutes)
24. time_dead_ratio (percentage of time dead)
25. xp (experience points)
26. kd_ratio (kill/death ratio)
27. dpm (damage per minute)
28. efficiency (combat efficiency percentage)
29. bullets_fired (total shots fired)
30. accuracy (hit percentage)
31. kill_assists (assisted kills) ⭐ OBJECTIVE STAT
32. objectives_completed (objectives finished) ⭐ OBJECTIVE STAT
33. objectives_destroyed (objectives destroyed) ⭐ OBJECTIVE STAT
34. objectives_stolen (objectives stolen) ⭐ OBJECTIVE STAT
35. objectives_returned (objectives returned) ⭐ OBJECTIVE STAT
36. dynamites_planted (dynamites planted) ⭐ OBJECTIVE STAT
37. dynamites_defused (dynamites defused) ⭐ OBJECTIVE STAT
38. times_revived (times player was revived) ⭐ OBJECTIVE STAT
39. revives_given (revives given to others) ⭐ OBJECTIVE STAT
40. most_useful_kills (high-value target kills) ⭐ OBJECTIVE STAT
41. useless_kills (low-value kills) ⭐ OBJECTIVE STAT
42. kill_steals (kill steals) ⭐ OBJECTIVE STAT
43. denied_playtime (seconds of enemy playtime denied) ⭐ OBJECTIVE STAT
44. constructions (construction builds)
45. tank_meatshield (tank damage absorbed)
46. double_kills (double kills - multikill)
47. triple_kills (triple kills - multikill)
48. quad_kills (quad kills - multikill)
49. multi_kills (penta kills - multikill)
50. mega_kills (hexa+ kills - multikill)
51. killing_spree_best (best killing spree)
52. death_spree_worst (worst death spree)
53. created_at (timestamp, auto-generated)
```

**Key Points**:
- Columns 31-43: Objective/support stats (what was missing in old split schema)
- Column 21 (time_played_seconds): Primary time tracking field
- All 52 data fields are inserted by import script (id and created_at are auto-generated)

---

## 🗂️ FILE STRUCTURE (What Matters)

### 🔴 CRITICAL - Bot Runtime (5 files):
```
bot/ultimate_bot.py              # Main Discord bot (830 lines)
bot/community_stats_parser.py    # Stats parser (724 lines)
bot/image_generator.py           # Session images (313 lines)
etlegacy_production.db           # Production database
.env                             # Bot token & config
```

### 🟡 CRITICAL - Data Pipeline (2 files + 1 dir):
```
tools/simple_bulk_import.py      # ✅ CORRECT import script
local_stats/*.txt                # Stats files (1,862 files)
```

### 🔵 IMPORTANT - Support:
```
create_unified_database.py       # Database creator
requirements.txt                 # Python dependencies
README.md                        # Main documentation
database_backups/                # Database backups
```

### ⚪ DEPRECATED - DO NOT USE:
```
dev/bulk_import_stats.py         # ❌ Old split schema
tools/fixed_bulk_import.py       # ❌ Different database
```

### 📚 DOCUMENTATION (needs updates):
```
COPILOT_INSTRUCTIONS.md          # ❌ OUTDATED - references split schema
DATABASE_EXPLAINED.md            # ❌ OUTDATED - shows 4 tables
docs/                            # ⚠️ Needs review
```

---

## 📊 SCHEMA EVOLUTION HISTORY

### Why Three Schemas Exist:

#### **Version 1: SPLIT** (Deprecated - Pre-Oct 2024)
```
Problem: Bot queries player_comprehensive_stats but objectives in separate table
Design: 4 tables (sessions, player_comprehensive_stats, weapon_comprehensive_stats, player_objective_stats)
Columns: 35 in player_comprehensive_stats + 27 in player_objective_stats
Import: dev/bulk_import_stats.py
Status: ❌ DEPRECATED
```

#### **Version 2: UNIFIED** (Current - Oct 4, 2025)
```
Solution: All stats in ONE table for easier bot queries
Design: 3 tables (sessions, player_comprehensive_stats, weapon_comprehensive_stats)
Columns: 53 in player_comprehensive_stats (includes all objectives)
Import: tools/simple_bulk_import.py
Status: ✅ CURRENT PRODUCTION
```

#### **Version 3: ENHANCED** (Experimental)
```
Experiment: Per-round granularity with different structure
Database: etlegacy_fixed_bulk.db (separate file)
Import: tools/fixed_bulk_import.py
Status: ⚠️ Not bot-compatible, experimental only
```

### Migration Path (Split → Unified):
```powershell
# If you have old split schema database:
# 1. Backup old database
cp etlegacy_production.db etlegacy_production_old_split_schema.db

# 2. Create new unified schema
python create_unified_database.py

# 3. Re-import all stats with correct script
python tools/simple_bulk_import.py local_stats/*.txt

# Result: Unified schema with all objective stats working
```

---

## 🎯 BOT QUERY EXPECTATIONS

### What the Discord Bot Expects:

```python
# Line 719 in bot/ultimate_bot.py:
SELECT DISTINCT session_date FROM sessions

# Line 1056-1061: Objective stats query
SELECT 
    clean_name, xp, kill_assists, objectives_stolen, 
    objectives_returned, dynamites_planted, dynamites_defused,
    times_revived, double_kills, triple_kills, quad_kills,
    multi_kills, mega_kills, denied_playtime, most_useful_kills,
    useless_kills, gibs, killing_spree_best, death_spree_worst
FROM player_comprehensive_stats 
WHERE session_id IN (...)
```

**Critical**: Bot queries `player_comprehensive_stats` for objective stats.  
If using split schema, these columns don't exist → bot shows zeros!

---

## 🔧 COMMON OPERATIONS

### Import New Stats:
```powershell
# Single file:
python tools/simple_bulk_import.py local_stats/2025-10-04-*.txt

# All 2025 files:
python tools/simple_bulk_import.py local_stats/2025-*.txt

# All files:
python tools/simple_bulk_import.py local_stats/*.txt
```

### Check Import Status:
```powershell
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*), MIN(processed_at), MAX(processed_at) FROM processed_files WHERE success = 1'); r = cursor.fetchone(); print(f'Imported: {r[0]} files'); print(f'First: {r[1]}'); print(f'Last: {r[2]}')"
```

### Verify Data Quality:
```powershell
# Check for zeros in objective stats
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM player_comprehensive_stats WHERE times_revived = 0 AND kill_assists = 0 AND dynamites_planted = 0'); zero_count = cursor.fetchone()[0]; cursor.execute('SELECT COUNT(*) FROM player_comprehensive_stats'); total = cursor.fetchone()[0]; print(f'Records with all zeros: {zero_count}/{total} ({zero_count/total*100:.1f}%)')"
```

### Database Backup:
```powershell
# Create timestamped backup
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
cp etlegacy_production.db "database_backups/etlegacy_production_backup_$timestamp.db"
echo "Backup created: database_backups/etlegacy_production_backup_$timestamp.db"
```

---

## 🎓 PARSER DETAILS

### c0rnp0rn3.lua Output Format:

**File naming**: `YYYY-MM-DD-HHMMSS-mapname-round-N.txt`  
Example: `2025-10-02-211808-etl_adlernest-round-1.txt`

**File structure**:
```
Line 1: Header (ETL Server\mapname\game_type\round\team_wins\players\time_limit\actual_time\actual_seconds)
Line 2+: Player lines (guid\name\team\class\weapon_stats [TAB] 38 tab-separated objective stats)
```

**38 TAB-separated fields** (after weapon stats):
```
1. damage_given          14. headshot_kills        27. kd_ratio
2. damage_received       15. objectives_stolen     28. useful_kills
3. team_damage_given     16. objectives_returned   29. denied_playtime
4. team_damage_received  17. dynamites_planted     30. multikill_2x
5. gibs                  18. dynamites_defused     31. multikill_3x
6. self_kills            19. times_revived         32. multikill_4x
7. team_kills            20. bullets_fired         33. multikill_5x
8. team_gibs             21. dpm (Lua = 0, we calc) 34. multikill_6x
9. time_played_percent   22. time_played_minutes   35. useless_kills
10. xp                   23. tank_meatshield       36. full_selfkills
11. killing_spree        24. time_dead_ratio       37. repairs_constructions
12. death_spree          25. time_dead_minutes     38. revives_given
13. kill_assists         26. kd_ratio
```

### Parser Handles:
- ✅ Header parsing (map, round, time)
- ✅ Player data extraction (all 38 fields)
- ✅ Weapon stats parsing
- ✅ Round 2 differential (auto-finds Round 1, subtracts cumulative stats)
- ✅ Time conversion (seconds → minutes)
- ✅ DPM calculation (overrides Lua's 0.0 with real calculation)

---

## 🚀 RUNNING THE BOT

### Prerequisites:
```powershell
# Install dependencies
pip install -r requirements.txt

# Configure .env file
cp .env.example .env
# Edit .env and add your DISCORD_TOKEN
```

### Start Bot:
```powershell
cd g:\VisualStudio\Python\stats
python bot/ultimate_bot.py
```

### Check Bot Status:
```powershell
# In Discord, type:
!ping              # Test bot responsiveness
!last_session      # Test database queries
!stats <player>    # Test player queries
```

---

## ⚠️ CRITICAL WARNINGS

### ❌ DO NOT:
1. **DO NOT use `dev/bulk_import_stats.py`** - Wrong schema (split)
2. **DO NOT manually edit database** - Use import scripts
3. **DO NOT delete processed_files table** - Tracks what's imported
4. **DO NOT assume documentation is current** - Most docs reference old schema
5. **DO NOT trust column counts in docs** - Verify with `PRAGMA table_info`

### ✅ DO:
1. **DO backup database** before major changes
2. **DO use `tools/simple_bulk_import.py`** for imports
3. **DO verify schema** with column count check (should be 53)
4. **DO check this file** before making changes
5. **DO test on single file** before bulk importing

---

## 📞 WHEN THINGS GO WRONG

### Error Messages & Solutions:

**"no such column: times_revived"**  
→ Wrong schema (split). Need unified schema (53 columns)

**"table player_comprehensive_stats has no column named X"**  
→ Using wrong import script. Use tools/simple_bulk_import.py

**"Error: 51 values for 53 columns"**  
→ Import script bug. Check simple_bulk_import.py field mapping (lines 120-173)

**"Stats show zeros in Discord bot"**  
→ Schema mismatch. Verify column count = 53

**"Duplicate session error"**  
→ Normal. Script skips duplicates. Check processed_files table.

**"Parser can't find Round 1 file for Round 2"**  
→ Round 1 file missing or different naming. Check local_stats/ directory.

---

## 🎯 SUCCESS CHECKLIST

**System is correct when**:

- [x] Database schema has 53 columns in player_comprehensive_stats
- [x] All objective stats (revives, assists, etc.) show non-zero values
- [x] Import uses tools/simple_bulk_import.py
- [x] Bot queries work (!last_session shows objective stats)
- [x] Database file is etlegacy_production.db (not etlegacy_fixed_bulk.db)
- [x] No errors about missing columns

**Current Status (Oct 4, 2025)**: ✅ ALL CHECKS PASS

---

## 📚 ADDITIONAL RESOURCES

**For detailed technical info, see**:
- `PROJECT_CRITICAL_FILES_MAP.md` - Complete file inventory
- `DOCUMENTATION_AUDIT_SUMMARY.md` - Documentation review
- `docs/BOT_COMPLETE_GUIDE.md` - Bot internals
- `docs/PARSER_DOCUMENTATION.md` - Parser details

**For quick verification**:
- Run commands in "Verification" section above
- Check column count: Should be 53
- Check data: Objective stats should be non-zero

---

## 🤖 FOR AI AGENTS: INSTRUCTIONS TO SELF

**When user asks you to work on this project**:

1. **READ THIS FILE FIRST** - Don't trust memory or other docs
2. **VERIFY SCHEMA** - Check column count = 53
3. **USE CORRECT SCRIPT** - tools/simple_bulk_import.py only
4. **CHECK DATABASE** - etlegacy_production.db (not other DBs)
5. **BACKUP FIRST** - Before any destructive operations
6. **TEST SMALL** - Single file before bulk operations

**When confused**:
- Check "Quick Answers" section above
- Run verification commands
- Don't assume - verify!

**When user reports problems**:
- Use "Troubleshooting Decision Tree" section
- Check schema first (most common issue)
- Verify import script selection

---

**Last Verified**: October 4, 2025 - All systems working ✅  
**Next Review**: When schema or import process changes

---

## 💡 TL;DR (Too Long; Didn't Read)

```
Schema: UNIFIED (3 tables, 53 columns)
Import: tools/simple_bulk_import.py
Database: etlegacy_production.db
Status: WORKING ✅

Don't use: dev/bulk_import_stats.py (wrong schema)
Don't trust: Old documentation (references split schema)

Verify with: PRAGMA table_info(player_comprehensive_stats)
Expected: 53 columns
```

**When in doubt → Check this file → Verify schema → Use correct import script**

---

*This file was created because even the developer forgot the correct schema after one day. 
Documentation matters! 📚*
