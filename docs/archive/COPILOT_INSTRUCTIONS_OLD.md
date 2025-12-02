# 🤖 GitHub Copilot Instructions - ET:Legacy Discord Bot

## 📋 Project Overview
Discord bot for ET:Legacy game statistics with beautiful embeds, image generation, and comprehensive stat tracking.

## 🎯 Current Status (October 3, 2025)

### ✅ COMPLETED WORK

#### Phase 1: Database Query Fix
- **Problem**: Query referenced non-existent columns `p.time_played` and `p.xp`
- **Solution**: Removed those columns, added playtime calculation from `sessions.actual_time`
- **Status**: ✅ FIXED - Bot starts successfully
- **Files Modified**:
  - `bot/ultimate_bot.py` (lines 758-780): Updated query to remove non-existent columns
  - `bot/ultimate_bot.py` (lines 995-1017): Fixed data unpacking for 9 values instead of 10
  - `bot/image_generator.py` (lines 115-119): Removed XP from image display

#### Phase 2: Stats Display Format
- **Format**: Two-line player stats display
  - Line 1: `1222K/865D (1.41) • 287 DPM • 39.3% ACC (1814/4610)`
  - Line 2: `1456 HSK (58.2%) • 891 HS (49.1%) • 125m`
- **Metrics**:
  - HSK = Headshot Kills (from player table, % of total kills)
  - HS = Headshots (from weapon table, % of hits)
  - Playtime calculated from sessions.actual_time (MM:SS format)
- **Status**: ✅ IMPLEMENTED (untested in Discord)

#### Phase 3: Image Generation
- **Module**: `bot/image_generator.py` created
- **Features**:
  - Discord dark theme colors
  - Session overview: 1400x900px PNG
  - Top 5 players with 2-line stats
  - Team analytics with MVPs
  - PIL/Pillow based rendering
- **Status**: ✅ IMPLEMENTED (untested - bot crashes before reaching it due to other error)

### 🔧 CURRENT ISSUE

**Bot Error**: `no such column: session_date` in !last_session command (line 719)
- Query tries: `SELECT DISTINCT DATE(session_date) as date FROM sessions`
- But column is already named `session_date` (not needing DATE() wrapper)
- **Action Required**: Fix this query before testing other features

### 🎯 IMMEDIATE TODO (Before New Feature Work)

1. ✅ **Fix session_date query error** (urgent - blocking all testing)
2. 🔄 **Test !last_session command** in Discord
3. 🔄 **Verify image generation** displays correctly
4. 🔄 **Test weapon mastery embed** appearance

### 🚀 MAJOR DISCOVERY - NEW WORK PENDING

#### Found: Complete Objective Stats Available!

The `c0rnp0rn3.lua` script **ALREADY TRACKS** all objective/support stats that were thought missing:

**Available in Lua Output** (37+ fields per player):
- ✅ XP/Experience points (field 10)
- ✅ Kill assists (field 13)
- ✅ Objectives stolen (field 16)
- ✅ Objectives returned (field 17)
- ✅ Dynamites planted (field 18)
- ✅ Dynamites defused (field 19)
- ✅ Times revived (field 20)
- ✅ Bullets fired (field 21)
- ✅ Time played minutes per player (field 23)
- ✅ Multikills 2x-6x (fields 30-34)
- ✅ Repairs/constructions (field 37)
- ✅ Killing sprees (field 11)
- ✅ Death sprees (field 12)
- ✅ Tank/meatshield score (field 24)
- ✅ Time dead ratio (field 25)
- ✅ Most useful kills (field 28)
- ✅ Denied playtime (field 29)

**Current State**: Parser only reads ~12 fields, ignoring 25+ objective stats fields

**Next Phase**: Enhance parser to extract ALL 37 fields and populate `player_stats` table

---

## 🗂️ Database Schema

### Current Tables (etlegacy_production.db)

#### `sessions` (1,459 records)
```sql
id INTEGER PRIMARY KEY
session_date DATE NOT NULL           -- Format: 2025-01-01
map_name TEXT NOT NULL               -- e.g., "etl_adlernest"
round_number INTEGER NOT NULL        -- 1 or 2
time_limit TEXT                      -- MM:SS (e.g., "10:00")
actual_time TEXT                     -- MM:SS (e.g., "11:26")
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

#### `player_comprehensive_stats` (12,444 records) ✅ ACTIVE
```sql
id INTEGER PRIMARY KEY
session_id INTEGER NOT NULL
player_guid TEXT NOT NULL            -- 8-char hex ID
player_name TEXT NOT NULL
clean_name TEXT NOT NULL
team INTEGER NOT NULL                -- 1=Axis, 2=Allies
kills INTEGER DEFAULT 0
deaths INTEGER DEFAULT 0
damage_given INTEGER DEFAULT 0
damage_received INTEGER DEFAULT 0
headshot_kills INTEGER DEFAULT 0
kd_ratio REAL DEFAULT 0.0
dpm REAL DEFAULT 0.0
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

#### `weapon_comprehensive_stats` ✅ ACTIVE
```sql
id INTEGER PRIMARY KEY
session_id INTEGER NOT NULL
player_guid TEXT NOT NULL
weapon_id INTEGER
weapon_name TEXT NOT NULL            -- WS_MP40, WS_THOMPSON, etc.
kills INTEGER DEFAULT 0
deaths INTEGER DEFAULT 0
hits INTEGER DEFAULT 0               -- Shots that hit
shots INTEGER DEFAULT 0              -- Total shots fired
headshots INTEGER DEFAULT 0          -- Headshots landed
accuracy REAL DEFAULT 0.0
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

#### `player_stats` (0 records) ⚠️ EMPTY BUT AVAILABLE
```sql
id INTEGER PRIMARY KEY
session_id INTEGER
player_name TEXT NOT NULL
discord_id TEXT
round_type TEXT
team TEXT
kills INTEGER DEFAULT 0
deaths INTEGER DEFAULT 0
damage INTEGER DEFAULT 0
time_played TEXT DEFAULT '0:00'
time_minutes REAL DEFAULT 0
dpm REAL DEFAULT 0
kd_ratio REAL DEFAULT 0
mvp_points INTEGER DEFAULT 0
weapon_stats TEXT
achievements TEXT
awards TEXT                          -- For objective stats (JSON)
```

**PLAN**: Populate `player_stats.awards` with JSON containing:
```json
{
  "xp": 45230,
  "kill_assists": 12,
  "objectives_stolen": 3,
  "objectives_returned": 5,
  "dynamites_planted": 2,
  "dynamites_defused": 1,
  "times_revived": 8,
  "bullets_fired": 1234,
  "multikills_2x": 5,
  "multikills_3x": 2,
  "multikills_4x": 1,
  "multikills_5x": 0,
  "multikills_6x": 0,
  "repairs_constructions": 7,
  "killing_spree_best": 10,
  "death_spree_worst": 5,
  "tank_meatshield_score": 2.3,
  "time_dead_ratio": 15.2,
  "useful_kills": 45,
  "denied_playtime_seconds": 180
}
```

---

## 📦 File Structure

```
bot/
├── ultimate_bot.py              # Main Discord bot (1846 lines)
├── community_stats_parser.py    # Stats parser (724 lines) - NEEDS ENHANCEMENT
├── image_generator.py           # PIL-based image generation (313 lines)
├── etlegacy_production.db       # SQLite database
└── logs/
    └── ultimate_bot.log
```

---

## 🛠️ Key Functions in ultimate_bot.py

### `!last_session` Command (line 702-1400)
**Purpose**: Display comprehensive stats for most recent session

**Current Error**: Line 719 - `no such column: session_date`
```python
# BROKEN:
SELECT DISTINCT DATE(session_date) as date FROM sessions

# SHOULD BE:
SELECT DISTINCT session_date as date FROM sessions
```

**Flow**:
1. Get latest session date
2. Get all session IDs for that date
3. Query top 5 players (aggregated)
4. Query team stats
5. Query weapon details
6. Query per-player weapon mastery
7. Generate 5 embeds + 1 image

**Embeds**:
- Embed 1: Session info + Top 5 players (with 2-line stats)
- Embed 2: Team comparison + MVPs
- Embed 3: DPM leaderboard
- Embed 4: Team composition
- Embed 5: Weapon mastery (top 6 players, top 2 weapons each)
- Image: Beautiful session overview card

---

## 🎨 Discord Bot Features

### Commands Available
- `!ping` - Test bot responsiveness
- `!session` - Manage sessions
- `!session_start` - Start new session
- `!session_end` - End current session
- `!last_session` - Show stats for latest session ⭐ MAIN COMMAND
- `!stats <player>` - Show player stats
- `!leaderboard` - Show top players
- `!link <discord_mention>` - Link Discord user to game GUID
- `!unlink` - Unlink Discord account
- `!help` - Show help message

### Color Scheme (Discord Dark Theme)
```python
bg_dark = '#2b2d31'
bg_medium = '#1e1f22'
bg_light = '#313338'
text_white = '#f2f3f5'
text_gray = '#b5bac1'
text_dim = '#80848e'
accent_blue = '#5865f2'
accent_green = '#57f287'
accent_red = '#ed4245'
accent_yellow = '#fee75c'
accent_pink = '#eb459e'
```

---

## 🔄 Parser Enhancement Required

### Current Parser (community_stats_parser.py)
**Reads**: ~12 fields after weapon stats
- damage_given, damage_received
- Basic combat stats

**Missing**: 25+ objective/support fields

### Enhanced Parser (TO BE CREATED)
**Must Read**: All 37 fields from c0rnp0rn3.lua output

**Field Mapping** (after weapon stats):
```python
FIELD_MAPPING = {
    0: 'damage_given',
    1: 'damage_received',
    2: 'team_damage_given',
    3: 'team_damage_received',
    4: 'gibs',
    5: 'selfkills',
    6: 'teamkills',
    7: 'teamgibs',
    8: 'time_played_percent',
    9: 'xp',                      # ⭐
    10: 'killing_spree',
    11: 'death_spree',
    12: 'kill_assists',           # ⭐
    13: 'kill_steals',
    14: 'headshot_kills',
    15: 'objectives_stolen',      # ⭐
    16: 'objectives_returned',    # ⭐
    17: 'dynamites_planted',      # ⭐
    18: 'dynamites_defused',      # ⭐
    19: 'times_revived',          # ⭐
    20: 'bullets_fired',          # ⭐
    21: 'dpm',
    22: 'time_played_minutes',    # ⭐
    23: 'tank_meatshield',
    24: 'time_dead_ratio',
    25: 'time_dead_minutes',
    26: 'kd_ratio',
    27: 'useful_kills',
    28: 'denied_playtime',
    29: 'multikill_2x',           # ⭐
    30: 'multikill_3x',           # ⭐
    31: 'multikill_4x',           # ⭐
    32: 'multikill_5x',           # ⭐
    33: 'multikill_6x',           # ⭐
    34: 'useless_kills',
    35: 'full_selfkills',
    36: 'repairs_constructions'   # ⭐
}
```

---

## 🎯 MVP Calculation Enhancement

### Current MVP (combat-only)
```python
mvp_score = (
    kills * 10 +
    (damage_given / 100) +
    (kd_ratio * 50) -
    deaths * 5
)
```

### Enhanced MVP (with objectives) - TO BE IMPLEMENTED
```python
combat_score = (
    kills * 10 +
    headshot_kills * 3 +
    (damage_given / 100) +
    (kd_ratio * 50) -
    deaths * 5
)

objective_score = (
    objectives_returned * 50 +
    objectives_stolen * 30 +
    dynamites_planted * 25 +
    dynamites_defused * 20
)

support_score = (
    times_revived * 10 +
    repairs_constructions * 15 +
    kill_assists * 5
)

performance_score = (
    (accuracy * 2) +
    useful_kills * 5 -
    useless_kills * 2 +
    (multikill_3x * 10) +
    (multikill_4x * 20) +
    (multikill_5x * 40) +
    (multikill_6x * 80)
)

mvp_score = combat_score + objective_score + support_score + performance_score
```

---

## 🚨 Known Issues

1. ❌ **session_date query error** (line 719) - BLOCKING
2. 🔄 **Image generation untested** - Need Discord test
3. 🔄 **Weapon mastery readability** - User feedback: "hard to look at"
4. ❌ **Parser missing 25+ fields** - Next major work

---

## 📝 User Requests Queue

### HIGH PRIORITY
1. ✅ Fix database column errors → DONE
2. 🔄 Test !last_session command → PENDING (blocked by session_date error)
3. 🔄 Verify image generation → PENDING
4. 📋 **NEW**: Extract all 37 fields from Lua stats
5. 📋 **NEW**: Populate player_stats table with objective data
6. 📋 Improve weapon mastery display (colors, complete stats)

### MEDIUM PRIORITY
7. 📋 Implement comprehensive MVP scoring with objectives
8. 📋 Add multikill badges/displays
9. 📋 Show killing sprees in stats
10. 📋 Display time dead ratio analysis

### LOW PRIORITY
11. 📋 Add achievement badges
12. 📋 Create player career stats
13. 📋 Historical trend graphs

---

## 🔧 Development Environment

- **Python**: 3.13
- **OS**: Windows (PowerShell)
- **Libraries**: discord.py 2.3+, aiosqlite, matplotlib, Pillow
- **Database**: SQLite (etlegacy_production.db)
- **Working Directory**: `g:\VisualStudio\Python\stats\bot\`

---

## 💡 Quick Reference

### Run Bot
```powershell
cd g:\VisualStudio\Python\stats
python bot\ultimate_bot.py
```

### Check Database
```powershell
python -c "import sqlite3; conn = sqlite3.connect('etlegacy_production.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM player_comprehensive_stats'); print(cursor.fetchone()[0])"
```

### Test Parser
```python
from bot.community_stats_parser import CommunityStatsParser
parser = CommunityStatsParser()
result = parser.parse_stats_file('path/to/stats.txt')
```

---

## 🎓 Learning Notes

### ET:Legacy Team System
- Team 0: Spectators
- Team 1: Axis (Red) 🔴
- Team 2: Allies (Blue) 🔵
- Team 3: Intermission/Limbo

### Round System
- Round 1: Team A attacks, Team B defends
- Round 2: Teams switch sides
- `round_number`: 1 or 2
- Stats tracked per round

### Time Format
- `time_limit`: Map time limit (MM:SS)
- `actual_time`: Actual round duration (MM:SS)
- Early finish: actual_time < time_limit (objective completed)
- Full time: actual_time ≈ time_limit (defenders held)

---

## 📌 Important Patterns

### Error Handling
```python
try:
    # Operation
except Exception as e:
    self.logger.error(f"Error: {e}", exc_info=True)
    await ctx.send(f"❌ Error: {str(e)}")
```

### Database Queries
```python
async with aiosqlite.connect(self.db_path) as db:
    async with db.execute(query, params) as cursor:
        results = await cursor.fetchall()
```

### Embed Creation
```python
embed = discord.Embed(
    title="Title",
    color=discord.Color.blue(),
    description="Description"
)
embed.add_field(name="Field", value="Value", inline=False)
await ctx.send(embed=embed)
```

---

## 🎯 Success Criteria

### Phase 1 (Current) - ALMOST COMPLETE
- [x] Bot starts without errors
- [x] Database queries work
- [ ] !last_session displays correctly (blocked)
- [ ] Images generate successfully

### Phase 2 (Next) - PLANNED
- [ ] Parser extracts all 37 fields
- [ ] player_stats table populated
- [ ] Objective stats displayed in bot
- [ ] Enhanced MVP calculation

### Phase 3 (Future)
- [ ] Weapon mastery improved with colors
- [ ] Multikill badges
- [ ] Achievement system
- [ ] Career statistics

---

**Last Updated**: October 3, 2025 03:40 AM
**Status**: Ready for session_date fix → Full parser enhancement
**Next Step**: Fix line 719 query error, then implement enhanced parser
