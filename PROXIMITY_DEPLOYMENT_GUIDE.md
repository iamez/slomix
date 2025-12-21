"""
PROXIMITY TRACKER DEPLOYMENT GUIDE
ET:Legacy Multi-Script Setup for Position & Combat Analytics

This guide covers deploying the proximity_tracker.lua alongside c0rnp0rn.lua
"""

# ============================================================
# PART 1: GAME SERVER CONFIGURATION
# ============================================================

## Step 1.1: Place Lua Scripts

Copy scripts to ET:Legacy game server:

```bash
# Copy to legacy/ directory (same location as c0rnp0rn.lua)
cp c0rnp0rn.lua /path/to/et_legacy/legacy/
cp proximity_tracker.lua /path/to/et_legacy/legacy/
```

## Step 1.2: Update Server Configuration

Edit your server.cfg to load both scripts:

```cfg
# server.cfg

# CRITICAL: Load c0rnp0rn.lua FIRST, then proximity_tracker.lua
# Order matters - c0rnp0rn loads in VM slot 1, proximity_tracker in VM slot 2
seta lua_modules "c0rnp0rn.lua proximity_tracker.lua"

# Optional: Enable Lua module signatures (security check)
seta lua_allowedmodules ""  # Empty = allow all unsigned modules

# Rest of your server config...
seta sv_hostname "Your Server Name"
seta sv_maxclients "32"
# ... other settings ...
```

## Step 1.3: Restart Server

Restart ET:Legacy server or issue command:

```
// Server console
map_restart
```

## Step 1.4: Verify Loading

Check server console for:

```
>>> Proximity Tracker v1.0 initialized
>>> Proximity Tracker v1.0 loaded successfully
```

If you see these messages, the script is loaded correctly.

To debug, check the game log file for any errors related to "Lua module" or "proximity_tracker".

# ============================================================
# PART 2: DATABASE SCHEMA SETUP
# ============================================================

## Step 2.1: Apply PostgreSQL Schema

Load proximity_tracker tables into your PostgreSQL database:

```bash
# Connect to your PostgreSQL database
psql -U et_bot -d et_stats < bot/proximity_schema.sql

# Or paste contents of proximity_schema.sql into pgAdmin
```

## Step 2.2: Verify Table Creation

Verify tables were created:

```sql
-- In PostgreSQL
\dt player_positions
\dt combat_events
\dt engagement_analysis
\dt proximity_heatmap
```

You should see these tables listed.

# ============================================================
# PART 3: PYTHON PARSER INTEGRATION
# ============================================================

## Step 3.1: Place Parser Module

Copy proximity_parser.py to bot directory:

```bash
cp bot/proximity_parser.py /path/to/discord_bot/bot/
```

## Step 3.2: Update Bot Stats Parser

Modify bot/community_stats_parser.py to integrate proximity parser:

```python
# In community_stats_parser.py, add to imports:
from bot.proximity_parser import ProximityDataParser

# In the stats import function, after importing c0rnp0rn data:
async def process_stats_files(self, session_date: str, round_num: int):
    # ... existing c0rnp0rn parsing ...
    
    # NEW: Import proximity tracker data
    prox_parser = ProximityDataParser(self.db_adapter)
    await prox_parser.import_proximity_data(session_date, round_num)
```

## Step 3.3: Test Parser

Test the parser with existing proximity_tracker output:

```bash
# Python
python -c "
from bot.proximity_parser import ProximityDataParser

parser = ProximityDataParser(output_dir='local_stats')
files = parser.find_proximity_files('2025-12-20', 1)
print('Found files:', files)

# Parse test file
if files['combat']:
    events = parser.parse_combat_file(files['combat'])
    print(f'Parsed {len(events)} combat events')
"
```

# ============================================================
# PART 4: VERIFICATION & TESTING
# ============================================================

## Step 4.1: Verify File Output

After running a map, check for proximity tracker output files in gamestats/:

```bash
# Should see files like:
# 2025-12-20-120000-supply-round-1_positions.txt
# 2025-12-20-120000-supply-round-1_combat.txt
# 2025-12-20-120000-supply-round-1_engagements.txt
# 2025-12-20-120000-supply-round-1_heatmap.txt

ls -la gamestats/*_positions.txt
ls -la gamestats/*_combat.txt
ls -la gamestats/*_engagements.txt
ls -la gamestats/*_heatmap.txt
```

## Step 4.2: Verify Data Format

Check file contents (first few lines):

```bash
head gamestats/2025-12-20-120000-supply-round-1_positions.txt
# Should show: # POSITION_TRACKER_DATA
#              # clientnum\ttime\tx\ty\tz\tyaw\tpitch\tspeed\tmoving

head gamestats/2025-12-20-120000-supply-round-1_combat.txt
# Should show: # COMBAT_EVENTS_DATA
#              # time\ttype\tattacker\ttarget\tdistance\tnearby_allies\tnearby_enemies\tdamage
```

## Step 4.3: Test Database Import

Run bot stats import with proximity data:

```python
# Test manual import
from bot.proximity_parser import ProximityDataParser

parser = ProximityDataParser(db_adapter=db_instance)
success = await parser.import_proximity_data('2025-12-20', 1)

if success:
    print("✓ Proximity data imported successfully")
    stats = parser.get_statistics()
    print(stats)
else:
    print("✗ Import failed - check logs")
```

## Step 4.4: Verify Database Records

Check PostgreSQL for imported data:

```sql
-- Should have position records
SELECT COUNT(*) FROM player_positions WHERE session_date = '2025-12-20';

-- Should have combat events
SELECT COUNT(*) FROM combat_events WHERE session_date = '2025-12-20';

-- Should have engagement analysis
SELECT COUNT(*) FROM engagement_analysis WHERE session_date = '2025-12-20';

-- Should have heatmap data
SELECT COUNT(*) FROM proximity_heatmap WHERE session_date = '2025-12-20';
```

# ============================================================
# PART 5: TROUBLESHOOTING
# ============================================================

## Problem: Lua module not loading

**Solution:**
1. Check server.cfg has correct lua_modules line
2. Verify proximity_tracker.lua is in legacy/ directory
3. Check game log for Lua errors
4. Make sure c0rnp0rn.lua loads successfully first

```bash
grep -i "proximity" /path/to/et_legacy.log
grep -i "lua" /path/to/et_legacy.log
```

## Problem: No output files generated

**Solution:**
1. Play a complete round (run warmup → play → round end)
2. Files only output at intermission (end of round)
3. Check permissions on gamestats/ directory
4. Enable debug mode in proximity_tracker.lua (config.debug = true)

## Problem: Parser fails to import

**Solution:**
1. Verify files exist in gamestats/
2. Check file format (head command above)
3. Run parser with debug logging enabled
4. Check database connection with: `await db_adapter.fetch_one("SELECT 1")`

## Problem: Database tables missing

**Solution:**
1. Re-run proximity_schema.sql
2. Check PostgreSQL permissions: `GRANT ALL ON DATABASE et_stats TO et_bot;`
3. Verify tables with: `\dt` in psql

# ============================================================
# PART 6: CONFIGURATION TUNING
# ============================================================

## Adjust Position Tracking Frequency

In proximity_tracker.lua, change:

```lua
position_update_interval = 1000,  -- Milliseconds between snapshots
-- 1000 = 1 snapshot per second
-- 500 = 2 snapshots per second (more detailed, larger files)
-- 2000 = 1 snapshot every 2 seconds (less detail, smaller files)
```

## Adjust Proximity Detection Distances

```lua
proximity_check_distance = 300,   -- Units to check for nearby players
crossfire_distance = 200,         -- Units for crossfire detection
engagement_min_damage = 10        -- Minimum damage to log
```

## Adjust Heatmap Grid Size

```lua
grid_size = 512  -- Units per grid cell
-- Smaller = more detail (512 = fine detail)
-- Larger = less detail (1024 = coarse overview)
```

# ============================================================
# PART 7: OPERATIONS
# ============================================================

## Regular Maintenance

```bash
# Archive old proximity files (after importing to DB)
cd gamestats/
mkdir -p archive
mv *_positions.txt *_combat.txt *_engagements.txt *_heatmap.txt archive/ 2>/dev/null

# Or with date filter
find . -name "*_positions.txt" -mtime +30 -move archive/

# Backup database
pg_dump et_stats > backup_et_stats_$(date +%Y%m%d).sql
```

## Monitor Performance

```bash
# Check database size
SELECT 
    pg_size_pretty(pg_total_relation_size('player_positions')) as positions_size,
    pg_size_pretty(pg_total_relation_size('combat_events')) as combat_size,
    pg_size_pretty(pg_total_relation_size('engagement_analysis')) as engagement_size;

# Count records by session
SELECT session_date, COUNT(*) as record_count 
FROM player_positions 
GROUP BY session_date 
ORDER BY session_date DESC;
```

# ============================================================
# PART 8: NEXT STEPS
# ============================================================

1. **Visualization** - Create Discord commands for:
   - `!heatmap` - Display kill density heatmap
   - `!proximity_stats` - Player proximity analytics
   - `!engagement_analysis` - Fight engagement statistics

2. **Advanced Analytics** - Build:
   - Crossfire detection (2+ allies vs 1 enemy)
   - Baiting patterns (retreat while ally engages)
   - Team clustering metrics
   - Support fire coordination

3. **Bot Integration** - Add new Cogs:
   - `proximity_analytics_cog.py` - New Discord commands
   - `proximity_visualization_cog.py` - Generate maps/charts

# ============================================================
# REFERENCE: FILE FORMATS
# ============================================================

## *_positions.txt Format
```
clientnum    - Player ID (0-63)
time         - Timestamp in milliseconds
x, y, z      - 3D coordinates
yaw, pitch   - View angles (degrees)
speed        - Movement speed (units/sec)
moving       - 1 if speed > threshold, 0 if stationary
```

## *_combat.txt Format
```
timestamp         - Event time
type              - 'fire', 'hit', or 'kill'
attacker          - Attacking player ID
target            - Target player ID (or 'NONE' for fire events)
distance          - Distance between players (units)
nearby_allies     - Count of allies within proximity_check_distance
nearby_enemies    - Count of enemies within proximity_check_distance
damage            - Damage dealt (0 for fire events)
```

## *_engagements.txt Format
```
engagement_type   - '1v1', '2v1', '1v2', '2v2', etc.
distance          - Distance at engagement start
killer            - Killer player name
victim            - Victim player name
```

## *_heatmap.txt Format
```
grid_x, grid_y    - Grid cell coordinates
axis_kills        - Kills by Axis team in this cell
allies_kills      - Kills by Allies team in this cell
```
