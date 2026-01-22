# Proximity Tracker v4 - Session Notes

## January 8-9, 2026

### Session Goal

Upgrade Proximity Tracker from v3 (engagement-centric) to v4 (full player tracking).

### Final Status: READY FOR LIVE TEST

| Component | Status | Notes |
|-----------|--------|-------|
| Lua v4.0 | ✅ Deployed | 500ms sampling, bitwise fix applied |
| Parser v4 | ✅ Ready | Handles PLAYER_TRACKS section |
| Database | ✅ Ready | `player_track` table created, 0 rows |
| Isolation | ✅ Complete | Separate folder, disabled in bot |
| Test script | ✅ Working | `test_standalone.py` verified |

### Next Session: Play a round and verify output

---

## What Changed: v3 → v4

### The Problem with v3

v3 only tracked players **during combat engagements** (from first damage to death/escape). This missed:

- Where players spawned
- How long before they started moving
- Their full path from spawn to first combat
- Movement patterns outside of combat
- Sprint/stance behavior

### The v4 Vision

Track **ALL players** from **spawn to death**, every 1 second, with:

- Position (x, y, z)
- Health
- Speed (from velocity)
- Current weapon
- Stance (standing/crouching/prone)
- Sprint status
- First movement time after spawn

This enables:

- Full path visualization on map images
- Heatmaps of where players go (not just where they fight)
- Spawn exit analysis
- Movement efficiency metrics
- "Replay" data for tactical review

---

## Database Changes

### BEFORE (v3 Schema)

Tables that existed:

```sql
combat_engagement      - Per-engagement data (when player takes damage)
player_teamplay_stats  - Aggregated stats per player
crossfire_pairs        - Duo coordination stats
map_kill_heatmap       - Where kills happen
map_movement_heatmap   - Where combat/escapes happen
```text

### AFTER (v4 Schema)

**NEW TABLE: `player_track`**

```sql
CREATE TABLE IF NOT EXISTS player_track (
    id SERIAL PRIMARY KEY,

    -- Session context
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    map_name VARCHAR(64) NOT NULL,

    -- Player info
    player_guid VARCHAR(32) NOT NULL,
    player_name VARCHAR(64) NOT NULL,
    team VARCHAR(10) NOT NULL,
    player_class VARCHAR(16) NOT NULL,  -- SOLDIER, MEDIC, ENGINEER, FIELDOPS, COVERTOPS

    -- Timing
    spawn_time_ms INTEGER NOT NULL,
    death_time_ms INTEGER,              -- NULL if round ended before death
    duration_ms INTEGER,                -- total time alive
    first_move_time_ms INTEGER,         -- when player first moved after spawn
    time_to_first_move_ms INTEGER,      -- spawn_time to first_move (reaction time)

    -- Movement data
    sample_count INTEGER NOT NULL,
    path JSONB NOT NULL DEFAULT '[]',
    -- Path format: [{time, x, y, z, health, speed, weapon, stance, sprint, event}, ...]
    -- stance: 0=standing, 1=crouching, 2=prone
    -- sprint: 0=not sprinting, 1=sprinting
    -- event: spawn, sample, death, round_end

    -- Derived stats (calculated at import time)
    total_distance REAL,                -- total distance traveled
    avg_speed REAL,                     -- average movement speed
    sprint_percentage REAL,             -- % of time sprinting

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(session_date, round_number, player_guid, spawn_time_ms)
);
```text

**NEW INDEXES:**

```sql
CREATE INDEX idx_track_session ON player_track(session_date, round_number);
CREATE INDEX idx_track_player ON player_track(player_guid);
CREATE INDEX idx_track_map ON player_track(map_name);
CREATE INDEX idx_track_class ON player_track(player_class);
```python

### Why These Columns?

| Column | Why |
|--------|-----|
| `spawn_time_ms` | Unique identifier (player can spawn multiple times per round) |
| `death_time_ms` | NULL if round ended before death (survived) |
| `first_move_time_ms` | Detect AFK players, measure spawn reaction time |
| `time_to_first_move_ms` | Pre-calculated for quick queries |
| `path` | JSONB array of all position samples - enables visualization |
| `total_distance` | Pre-calculated at import - avoids re-parsing JSON |
| `avg_speed` | Pre-calculated - player efficiency metric |
| `sprint_percentage` | Pre-calculated - aggressive vs cautious playstyle |

### Data Volume Estimate

```text

player_track: ~20 tracks/round × 10 rounds/day × 365 days = 73,000 rows/year
Each track: ~1KB average (with path JSON)
Total: ~73MB/year additional storage

```yaml

---

## File Changes

### 1. Lua Script: `proximity/lua/proximity_tracker.lua`

**Version:** 3.0 → 4.0
**Lines:** ~640 → 1004

**New Constants:**

```lua
local PMF_DUCKED = 1        -- Crouching bit flag
local PMF_PRONE = 512       -- Prone bit flag
local PMF_SPRINT = 16384    -- Sprinting bit flag
```text

**New Tracker State:**

```lua
tracker.player_tracks = {}      -- clientnum -> active track
tracker.completed_tracks = {}   -- finished tracks for output
tracker.last_sample_time = 0    -- throttle sampling
```text

**New Functions:**

```lua
getPlayerVelocity(clientnum)      -- Get velocity vector
getPlayerSpeed(clientnum)         -- Calculate speed magnitude
getPlayerMovementState(clientnum) -- Get stance + sprint
getPlayerClass(clientnum)         -- Get class name
createPlayerTrack(clientnum)      -- Start tracking on spawn
samplePlayer(clientnum, track)    -- Record one sample
endPlayerTrack(clientnum, pos)    -- End on death/disconnect
sampleAllPlayers()                -- Called from et_RunFrame
serializeTrackPath(path)          -- Format path for output
```text

**New Callbacks:**

```lua
et_ClientSpawn(clientNum, revived, teamChange, restoreHealth)
  -- Only tracks fresh spawns (revived == 0), not medic revives

et_ClientDisconnect(clientNum)
  -- Ends track if player disconnects mid-round
```text

**Output Format Change:**

Added new section to output file:

```text

# PLAYER_TRACKS

# guid;name;team;class;spawn_time;death_time;first_move_time;samples;path

# path format: time,x,y,z,health,speed,weapon,stance,sprint,event separated by |

```python

### 2. Python Parser: `proximity/parser/parser.py`

**Class Rename:** `ProximityParserV3` → `ProximityParserV4`
(with backwards compatibility alias)

**New Dataclasses:**

```python
@dataclass
class PathPoint:
    time: int
    x: float
    y: float
    z: float
    health: int
    speed: float
    weapon: int
    stance: int      # 0=standing, 1=crouching, 2=prone
    sprint: int      # 0=no, 1=yes
    event: str

@dataclass
class PlayerTrack:
    guid: str
    name: str
    team: str
    player_class: str
    spawn_time: int
    death_time: Optional[int]
    first_move_time: Optional[int]
    sample_count: int
    path: List[PathPoint]

    # Computed properties:
    duration_ms, time_to_first_move_ms, total_distance, avg_speed, sprint_percentage
```text

**New Methods:**

```python
_parse_player_track_line(line)   # Parse PLAYER_TRACKS section
_import_player_tracks(session_date)  # Insert into database
```text

**Updated Methods:**

```python
parse_file()   # Now handles PLAYER_TRACKS section
import_file()  # Calls _import_player_tracks()
get_stats()    # Includes track statistics
```yaml

### 3. Schema File: `proximity/schema/schema.sql`

- Added `player_track` table definition
- Added 4 indexes for the new table
- Updated header comment (v3 → v4)
- Updated data volume estimates

---

## Deployment

### Game Server (puran.hehe.si)

```bash
# Deployed Lua script
scp -P 48101 -i ~/.ssh/etlegacy_bot \
  proximity/lua/proximity_tracker.lua \
  et@puran.hehe.si:/home/et/etlegacy-v2.83.1-x86_64/legacy/

# Config already includes proximity_tracker.lua in lua_modules
```text

### Database Server (192.168.64.116)

```bash
# Created player_track table
PGPASSWORD='etlegacy_secure_2025' psql -h 192.168.64.116 -U etlegacy_user -d etlegacy

# Ran CREATE TABLE and CREATE INDEX statements
```sql

---

## ET:Legacy Lua API Notes

### Critical Discoveries (from etlegacy-lua-docs.readthedocs.io)

1. **`et_ClientSpawn` has 4 parameters:**

   ```lua
   et_ClientSpawn(clientNum, revived, teamChange, restoreHealth)
   -- revived=0: fresh spawn
   -- revived=1: medic revive (don't create new track!)
   ```text

2. **Movement state via bit flags:**

   ```lua
   local pm_flags = et.gentity_get(clientnum, "ps.pm_flags")
   -- PMF_DUCKED = 1
   -- PMF_PRONE = 512
   -- PMF_SPRINT = 16384
   ```text

3. **Velocity available:**

   ```lua
   local vel = et.gentity_get(clientnum, "ps.velocity")
   -- Returns table: vel[1]=x, vel[2]=y, vel[3]=z (1-indexed!)
   ```sql

4. **GUID from userinfo, not entity:**

   ```lua
   local userinfo = et.trap_GetUserinfo(clientnum)
   local guid = et.Info_ValueForKey(userinfo, "cl_guid")
   ```text

5. **File write mode:**

   ```lua
   -- et.FS_WRITE doesn't exist as constant, use numeric: 1
   local fd, len = et.trap_FS_FOpenFile(filename, 1)
   ```python

---

## Development Isolation

### Why Isolated?

The proximity tracker is developed **separately** from the main bot to avoid breaking:

- Discord bot functionality
- Website backend
- Existing stats collection (c0rnp0rn)

### Isolation Layers

| Layer | How It's Isolated |
|-------|-------------------|
| **Bot config** | `PROXIMITY_ENABLED=false` - cog won't run |
| **Discord** | `PROXIMITY_DISCORD_COMMANDS=false` - commands hidden |
| **Output folder** | `proximity/` on game server (not `gamestats/`) |
| **Tables** | Separate tables, no FK to existing tables |
| **Testing** | `test_standalone.py` - doesn't touch bot |

### Standalone Test Script

Created `proximity/test_standalone.py` for isolated testing:

```bash
# Create sample test file
python3 test_standalone.py --create-sample test.txt

# Test parser only (no database)
python3 test_standalone.py --parse-only test.txt

# Test full import to database
python3 test_standalone.py --full-test test.txt

# Check database status
python3 test_standalone.py --status

# Clean up today's test data
python3 test_standalone.py --cleanup

# Clean up specific date
python3 test_standalone.py --cleanup-date 2026-01-08
```text

### File Paths on Game Server

```sql

/home/et/etlegacy-v2.83.1-x86_64/
├── legacy/
│   ├── proximity_tracker.lua     # Our Lua module
│   └── proximity/                # Output folder (NEW - separate from gamestats)
│       └── *_engagements.txt     # Proximity output files
├── gamestats/                    # c0rnp0rn stats (untouched)
│   └──*.txt                     # Existing stats files

```yaml

---

## Bugs Found During Code Review

### Bug #1: Wrong Bitwise Operator (FIXED)

**Problem:** Code used `bit.band()` which doesn't exist in Lua 5.4

```lua
-- WRONG (Lua 5.1 style)
if bit and bit.band then
    if bit.band(pm_flags, PMF_PRONE) ~= 0 then

-- CORRECT (Lua 5.4 native)
if (pm_flags & PMF_PRONE) ~= 0 then
```sql

**Impact:** Would have fallen back to broken subtraction logic.
**Fix:** Changed to native `&` operator.

### Change #2: Sampling Rate (500ms)

Changed from 1000ms to 500ms for better movement capture:

- 2 samples per second per player
- Captures strafe/dodge patterns
- ~24,000 samples per 10-min round with 20 players

### Verified Working

| Component | Status |
|-----------|--------|
| `ps.velocity` field | ✅ Confirmed in docs |
| `ps.pm_flags` field | ✅ Confirmed in docs |
| Nil handling | ✅ All paths check for nil |
| Name sanitization | ✅ Removes `;|,\n\r` |
| GUID fallback | ✅ Uses `SLOT{N}` if no GUID |
| Empty path handling | ✅ Returns empty string |

---

## Testing Checklist

- [ ] Wait for map change on game server
- [ ] Play a test round (spawn, move around, die)
- [ ] Check for output file: `proximity/*_engagements.txt` (NOT gamestats!)
- [ ] Verify PLAYER_TRACKS section exists in output
- [ ] Run parser on output file manually
- [ ] Check `player_track` table has data
- [ ] Verify path JSON is valid

---

## Sample Queries

```sql
-- All tracks from today
SELECT player_name, player_class, duration_ms, total_distance, sprint_percentage
FROM player_track
WHERE session_date = CURRENT_DATE
ORDER BY total_distance DESC;

-- Average reaction time by class
SELECT player_class,
       AVG(time_to_first_move_ms) as avg_reaction_ms,
       COUNT(*) as tracks
FROM player_track
WHERE time_to_first_move_ms IS NOT NULL
GROUP BY player_class;

-- Fastest players (by avg speed)
SELECT player_name, player_class, AVG(avg_speed) as speed
FROM player_track
GROUP BY player_guid, player_name, player_class
HAVING COUNT(*) > 5
ORDER BY speed DESC
LIMIT 10;

-- Sprint usage by class
SELECT player_class,
       AVG(sprint_percentage) as avg_sprint_pct
FROM player_track
GROUP BY player_class
ORDER BY avg_sprint_pct DESC;
```yaml

---

## Rollback Plan

If v4 causes issues:

1. **Revert Lua script:**

   ```bash
   # If we had saved v3, restore it. Otherwise disable tracking:
   ssh et@puran.hehe.si "sed -i 's/proximity_tracker.lua//' /home/et/etlegacy-v2.83.1-x86_64/etmain/legacy.cfg"
   ```text

2. **Drop new table (if needed):**

   ```sql
   DROP TABLE IF EXISTS player_track;
   ```python

3. **Parser is backwards compatible:**
   - `ProximityParserV3` alias still works
   - Files without PLAYER_TRACKS section parse fine

---

## Files Modified This Session

| File | Action | Lines Changed |
|------|--------|---------------|
| `proximity/lua/proximity_tracker.lua` | Major rewrite | ~400 new lines |
| `proximity/parser/parser.py` | Extended | ~150 new lines |
| `proximity/schema/schema.sql` | Extended | ~50 new lines |
| `proximity/SESSION_NOTES_2026-01-08.md` | Created | This file |

---

## Next Session Goals

1. Verify data collection works in live game
2. Create visualization tool for paths on map images
3. Add Discord commands for track stats
4. Consider aggregated player movement stats table

---

## Session Duration

~2.5 hours

## Key Decisions Made

1. **500ms sampling rate** - captures strafe/dodge patterns without excessive data
2. **Track ALL players** (not just those in combat) - enables full journey analysis
3. **Store full path in JSONB** - flexibility for future visualization
4. **Pre-calculate derived stats** - faster queries, avoid JSON parsing
5. **Separate table for tracks** - don't bloat combat_engagement table
6. **Separate output folder** (`proximity/` not `gamestats/`) - isolation from existing stats
7. **Standalone test script** - test without touching bot

---

## RESUME NEXT SESSION

### Quick Commands to Test

```bash
# 1. Check if Lua loaded (look for proximity output after map change)
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \
  "ls -la /home/et/etlegacy-v2.83.1-x86_64/legacy/proximity/"

# 2. Download output file after playing a round
scp -P 48101 -i ~/.ssh/etlegacy_bot \
  et@puran.hehe.si:/home/et/etlegacy-v2.83.1-x86_64/legacy/proximity/*.txt \
  /home/samba/share/slomix_discord/proximity/

# 3. Test parse the file
cd /home/samba/share/slomix_discord/proximity
python3 test_standalone.py --parse-only <downloaded_file.txt>

# 4. Test full import
python3 test_standalone.py --full-test <downloaded_file.txt>

# 5. Check database
python3 test_standalone.py --status
```

### Files to Know

| File | Purpose |
|------|---------|
| `proximity/lua/proximity_tracker.lua` | Game server Lua module |
| `proximity/parser/parser.py` | Python parser (ProximityParserV4) |
| `proximity/test_standalone.py` | Standalone test script |
| `proximity/schema/schema.sql` | Database schema |
| `proximity/SESSION_NOTES_2026-01-08.md` | This documentation |

### Current Config

| Setting | Value |
|---------|-------|
| Sample rate | 500ms |
| Output folder | `proximity/` (on game server) |
| Bot enabled | `false` (PROXIMITY_ENABLED=false) |
| Database | `player_track` table ready, 0 rows |
