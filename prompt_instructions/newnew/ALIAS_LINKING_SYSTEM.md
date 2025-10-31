# 🔗 ALIAS & LINKING SYSTEM DOCUMENTATION
**Created**: October 4, 2025  
**Purpose**: Document the comprehensive player alias detection and Discord linking system  
**Status**: 🚧 IN PROGRESS

---

## 📋 PROJECT OVERVIEW

### **Goal**: 
Build an intelligent Discord account linking system that:
1. Tracks all player name variations (aliases) per GUID
2. Makes self-linking easy with smart suggestions
3. Supports admin/friend linking with confirmations
4. Shows recent aliases in stats (max 3)
5. Consolidates stats across all aliases

### **Current Database**: 
- **File**: `etlegacy_production.db`
- **Schema**: UNIFIED (3 tables, 53 columns)
- **Players**: 25 unique GUIDs
- **Names**: 47 unique names (1.88 names per GUID)
- **Aliases Found**: 10 players with multiple names

### **Hardcoded Mappings Found**:
Located in `dev/link_discord_users.py` - **42 Discord users** pre-mapped:

```python
DISCORD_MAPPINGS = {
    "Lagger": "232574066471600128",
    "illy-ya": "414541532071460874", 
    "seareal": "231165917604741121",  # admin/dev/Ciril
    "m1ke": "335371284085211137",
    "Mravac": "1176115498245697610",
    "vid": "509737538555084810",
    # ... 36 more mappings
}
```

**Note**: These need to be migrated to `etlegacy_production.db` player_links table

---

## 🏗️ SYSTEM ARCHITECTURE

### **Phase 1: Foundation** ✅ IN PROGRESS
1. Create `player_aliases` table
2. Build alias population script
3. Migrate hardcoded Discord mappings

### **Phase 2: Bot Commands** (Next)
1. Enhanced `!link` command (self-linking)
2. `!link <name>` (fuzzy search)
3. `!link <GUID>` (direct)
4. `!select <number>` (reaction alternative)
5. `!link @user <GUID>` (admin linking)

### **Phase 3: Display & UX** (Future)
1. Show aliases in `!stats`
2. Add reaction buttons
3. Consolidate stats queries

---

## 📊 DATABASE SCHEMA CHANGES

### **New Table: player_aliases**

```sql
CREATE TABLE IF NOT EXISTS player_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_guid TEXT NOT NULL,
    player_name TEXT NOT NULL,
    clean_name TEXT NOT NULL,
    first_seen TEXT NOT NULL,        -- ISO datetime
    last_seen TEXT NOT NULL,          -- ISO datetime
    times_used INTEGER DEFAULT 1,     -- How many times this name appeared
    UNIQUE(player_guid, clean_name)
);

CREATE INDEX idx_aliases_guid ON player_aliases(player_guid);
CREATE INDEX idx_aliases_clean ON player_aliases(clean_name);
CREATE INDEX idx_aliases_last_seen ON player_aliases(last_seen DESC);
```

**Purpose**: Track all name variations with usage statistics

---

### **Update Table: player_links**

Current structure (needs verification):
```sql
CREATE TABLE player_links (
    discord_id BIGINT PRIMARY KEY,
    discord_username TEXT NOT NULL,
    et_guid TEXT UNIQUE NOT NULL,
    et_name TEXT,
    linked_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verified BOOLEAN DEFAULT FALSE
);
```

**Action Needed**: 
1. Check if table exists in production DB
2. Verify column names match bot expectations
3. Migrate 42 hardcoded mappings

---

## 🔍 ALIAS DETECTION RESULTS

From `check_aliases.py` run on production database:

### **Top 10 Players with Multiple Aliases:**

1. **ciril** (GUID: E587CA5F) - 8 names!
   - Names: ciril, Zlatorog, fl0w3r, warmup week, ez, Jaka V., Jaka V. #1001noc, Ciril
   - Records: 140 games

2. **s&o.lgz** (GUID: 1C747DF1) - 4 names
   - Names: s&o.lgz, SBudgetLagger, EUROSpinLagger, SmetarskiProner
   - Records: 1,498 games

3. **^<ABD-AL-KL3M3N** (GUID: 3C0354D3) - 4 names
   - Names: ^<ABD-AL-KL3M3N, one^>4ass.squAze, squAze Bros, It's squAze
   - Records: 38 games

4. **Aimless.KaNii** (GUID: A2C6BEBA) - 3 names
   - Names: Aimless.KaNii, Kanii, KaNii
   - Records: 52 games

5. **.wjs** (GUID: FDA127DF) - 3 names
   - Names: .wjs, temu.wjs, wiseBoy
   - Records: 967 games

(Continued for 5 more players...)

**Insight**: Alias detection is critical - 10 out of 25 players (40%) use multiple names!

---

## 🎯 USER EXPERIENCE FLOW

### **Scenario 1: Self-Linking** `!link`

**User Command**: `!link` (no arguments)

**Bot Response**:
```
🔍 Found multiple players matching your activity:

1️⃣ **s&o.lgz** (GUID: 1C747DF1)
   └─ 1,498 games | 18,234 kills | Last: 2025-10-04
   └─ Also: SBudgetLagger, EUROSpinLagger

2️⃣ **carniee** (GUID: 0A26D447)  
   └─ 1,294 games | 15,422 kills | Last: 2025-10-03
   └─ Also: -slo.carniee-

3️⃣ **bronze.** (GUID: 2B5938F5)
   └─ 795 games | 9,843 kills | Last: 2025-10-02
   └─ Also: bronzelow-

React 1️⃣/2️⃣/3️⃣ or use `!select 1` to link!
```

**Implementation Notes**:
- Search for unlinked GUIDs
- Rank by recent activity + total kills
- Show max 3 most recent aliases
- Add reaction listeners + !select command

---

### **Scenario 2: Name Search** `!link carniee`

**User Command**: `!link carniee`

**Bot Response**:
```
🔍 Found matching players:

1️⃣ **carniee** (GUID: 0A26D447)
   └─ 1,294 games | 15,422 kills | 1.34 K/D
   └─ Also: -slo.carniee-
   └─ Last: 2025-10-03 20:45

2️⃣ **carnie** (GUID: ABC12345)  ← Similar name
   └─ 23 games | 234 kills | 0.87 K/D
   └─ Last: 2024-08-12 14:22

React 1️⃣ to link, or use `!select 1`
```

**Implementation Notes**:
- Fuzzy name matching (Levenshtein distance)
- Search in player_aliases table
- Show stats preview
- Highlight most likely match

---

### **Scenario 3: Direct GUID** `!link 1C747DF1`

**User Command**: `!link 1C747DF1`

**Bot Response**:
```
🔗 Linking your account to GUID 1C747DF1...

   **s&o.lgz**
   └─ Recent: SmetarskiProner, EUROSpinLagger, s&o.lgz
   └─ Stats: 1,498 games | 18,234 kills | 1.89 K/D
   └─ Activity: 2024-09-15 to 2025-10-04

✅ **Is this you?**
React ✅ to confirm, or ❌ to cancel
```

**Implementation Notes**:
- Validate GUID exists
- Show 3 most recent aliases
- Add confirmation step
- Prevent accidental links

---

### **Scenario 4: Admin Linking** `!link @user 1C747DF1`

**User Command**: `!link @vid 1C747DF1` (requires permissions)

**Bot Response**:
```
🔗 Linking <@509737538555084810> to GUID 1C747DF1...

   **s&o.lgz**
   └─ Aliases: SmetarskiProner, EUROSpinLagger, s&o.lgz, SBudgetLagger
   └─ Stats: 1,498 games | 18,234 kills | 1.89 K/D
   └─ DPM: 342.5 | Efficiency: 67.8%

✅ **Confirm linking @vid?**
React ✅ by admin to confirm
```

**Implementation Notes**:
- Check user has MANAGE_GUILD permission
- Show full alias list
- Require admin confirmation
- Log admin actions

---

## 💾 DATA MIGRATION PLAN

### **Step 1: Check Production Database**
```powershell
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('PRAGMA table_info(player_links)'); cols = cursor.fetchall(); print('Columns:', [(c[1], c[2]) for c in cols])"
```

### **Step 2: Create player_aliases Table**
- Run migration script (to be created)
- Populate from player_comprehensive_stats
- Verify data quality

### **Step 3: Migrate Hardcoded Mappings**
- Extract DISCORD_MAPPINGS from link_discord_users.py
- Match Discord names to GUIDs in production DB
- Insert into player_links table
- Verify all 42 mappings applied

---

## 📝 IMPLEMENTATION CHECKLIST

### **Phase 1: Foundation** 🚧
- [ ] Create player_aliases table
- [ ] Build alias detection script
- [ ] Populate aliases from historical data
- [ ] Verify alias data quality
- [ ] Check player_links table structure
- [ ] Migrate 42 hardcoded Discord mappings
- [ ] Verify all mappings work

### **Phase 2: Bot Commands** 📋
- [ ] Implement !link (self-linking)
- [ ] Implement !link <name> (search)
- [ ] Implement !link <GUID> (direct)
- [ ] Implement !select <number>
- [ ] Implement !link @user <GUID> (admin)
- [ ] Add reaction listeners
- [ ] Add confirmation flows

### **Phase 3: Display** 🎨
- [ ] Update !stats to show aliases
- [ ] Limit alias display to 3 most recent
- [ ] Add timestamps to alias display
- [ ] Test all Discord UI flows

### **Phase 4: Testing** ✅
- [ ] Test self-linking with multiple options
- [ ] Test name search with fuzzy matching
- [ ] Test GUID validation
- [ ] Test admin linking permissions
- [ ] Test reaction buttons
- [ ] Test !select command
- [ ] Load testing with concurrent users

---

## 🐛 KNOWN ISSUES & CONSIDERATIONS

### **Issue 1: Color Codes**
- ET:Legacy uses ^X color codes in names
- Current clean_name removes them
- Need consistent cleaning across all systems

### **Issue 2: Case Sensitivity**
- "carniee" vs "Carniee" vs "CARNIEE"
- Fuzzy matching needed
- Index on LOWER(clean_name) for performance

### **Issue 3: Multiple Plays Per Day**
- Fixed Oct 4, 2025 in import script
- Aliases need to handle this correctly
- Test with 2025-10-02 data (2x te_escape2)

### **Issue 4: Reaction Timeouts**
- Discord reactions expire after inactivity
- Need timeout handling (default: 60 seconds)
- Clear reactions after selection

### **Issue 5: Concurrent Linking**
- Multiple users might link same GUID
- Need transaction locking
- Show clear error messages

---

## 📊 SUCCESS METRICS

### **Functionality**:
- ✅ All 25 GUIDs have complete alias records
- ✅ All 42 hardcoded Discord mappings migrated
- ✅ Self-linking works with 3 options max
- ✅ Fuzzy name search finds correct player
- ✅ Admin linking has permission checks
- ✅ Reactions and !select both work

### **Performance**:
- ✅ Alias query < 100ms
- ✅ Link command response < 2 seconds
- ✅ No database locks on concurrent links

### **User Experience**:
- ✅ Clear, intuitive messages
- ✅ No more than 3 aliases shown
- ✅ Recent activity highlighted
- ✅ Confirmation prevents mistakes

---

## 🔧 DEVELOPMENT COMMANDS

### **Check Aliases**:
```powershell
python check_aliases.py
```

### **Test Bot Locally**:
```powershell
python bot/ultimate_bot.py
```

### **Migrate Mappings** (to be created):
```powershell
python tools/migrate_discord_mappings.py
```

### **Populate Aliases** (to be created):
```powershell
python tools/populate_player_aliases.py
```

---

## 📚 RELATED DOCUMENTATION

- **Main Guide**: `docs/AI_AGENT_GUIDE.md`
- **Bot Guide**: `docs/BOT_COMPLETE_GUIDE.md`
- **Database Schema**: `docs/DATABASE_SCHEMA.md`
- **Test Results**: `docs/BOT_DEPLOYMENT_TEST_RESULTS.md`

---

## 📅 TIMELINE

**October 4, 2025 - Session 1 (22:30-23:00 UTC)**:
- ✅ Alias detection analysis complete
- ✅ Found 42 hardcoded Discord mappings in `dev/link_discord_users.py`
- ✅ Documented system architecture in `docs/ALIAS_LINKING_SYSTEM.md`
- ✅ Created `player_aliases` table with 8 columns + 3 indexes
- ✅ Populated 48 aliases from 12,414 historical records
- ✅ Verified: 25 GUIDs, avg 1.92 aliases per player
- ✅ Top alias users: ciril (8 names), s&o.lgz (4 names), squAze (4 names)

**Phase 1 Status**: ✅ **COMPLETE** (Foundation built!)

**Next - Phase 2**:
- [ ] Migrate 42 hardcoded Discord mappings to player_links
- [ ] Build enhanced !link command (self-linking)
- [ ] Add !select command
- [ ] Test with production bot

---

**Status**: 🚧 **Phase 1 - Foundation in Progress**  
**Next Action**: Create player_aliases table and migration script  
**Estimated Time**: ~2 hours for Phase 1  

---

*This is a living document - update as system evolves*
