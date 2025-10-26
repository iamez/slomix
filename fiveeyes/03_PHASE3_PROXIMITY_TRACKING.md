# 📍 Phase 3: Proximity Tracking System (OPTIONAL)

**Duration:** Weeks 6-8  
**Complexity:** ⭐⭐⭐⭐ High  
**Risk Level:** 🔴 High (server performance, Lua expertise required)  
**Dependencies:** Phase 1 + 2 complete, Lua scripting experience

---

## ⚠️ IMPORTANT: Read This First

**This phase is OPTIONAL.** Only proceed if:
- ✅ Phase 1 & 2 successfully deployed
- ✅ Community wants more advanced analytics
- ✅ You have Lua scripting expertise
- ✅ Server can handle additional processing
- ✅ You're willing to iterate on performance tuning

**Consider stopping at Phase 2** if:
- ❌ Existing synergy/normalized scores satisfy your needs
- ❌ No Lua experience in your team
- ❌ Server already has performance issues
- ❌ Limited time/resources for complex implementation

---

## 🎯 Goal

Track player positions during matches to detect:
- **Crossfire setups**: Two teammates near each other during combat
- **Support positioning**: Medics staying close to teammates
- **Team cohesion**: How spread out or grouped teams play
- **Objective support**: Who's near engineers during plants/defuses

---

## 📋 Implementation Approach

### **Strategy: Minimal-Impact Tracking**

❌ **DON'T:** Track all player positions every frame (too expensive)  
✅ **DO:** Track proximity only during significant events

```lua
-- Track proximity when it matters:
-- 1. When player takes damage (check for nearby teammates)
-- 2. When revive occurs (log medic position)
-- 3. When objective action happens (check support players)
-- 4. Every 5 seconds during active combat (not constantly)
```

---

## 📋 Week-by-Week Breakdown

### **Week 6: Lua Script Development**

#### Day 1-2: Extend c0rnp0rn3.lua

**Add proximity tracking module to your existing `c0rnp0rn3.lua`:**

```lua
-- ============================================================================
-- PROXIMITY TRACKING MODULE
-- Add to c0rnp0rn3.lua (do NOT create separate script)
-- ============================================================================

-- Configuration
local PROXIMITY_THRESHOLD = 256  -- Quake units (~6-8 meters ingame)
local PROXIMITY_CHECK_INTERVAL = 5000  -- Check every 5 seconds
local TRACK_COMBAT_PROXIMITY = true

-- State tracking
local proximityData = {}  -- Cumulative proximity time per player pair
local lastProximityCheck = 0
local combatProximityEvents = {}

-- ============================================================================
-- Helper: Calculate 3D distance between positions
-- ============================================================================
function distance3D(pos1, pos2)
    if not pos1 or not pos2 then
        return 999999
    end
    
    local dx = pos1[1] - pos2[1]
    local dy = pos1[2] - pos2[2]
    local dz = pos1[3] - pos2[3]
    
    return math.sqrt(dx*dx + dy*dy + dz*dz)
end

-- ============================================================================
-- Helper: Fast 2D distance check (optimization)
-- ============================================================================
function fastProximityCheck(pos1, pos2, threshold)
    if not pos1 or not pos2 then
        return false, 999999
    end
    
    -- Quick 2D check first (cheaper than 3D)
    local dx = pos1[1] - pos2[1]
    local dy = pos1[2] - pos2[2]
    local dist2D = math.sqrt(dx*dx + dy*dy)
    
    if dist2D > threshold then
        return false, dist2D
    end
    
    -- Only do 3D if 2D is close enough
    local dz = pos1[3] - pos2[3]
    local dist3D = math.sqrt(dx*dx + dy*dy + dz*dz)
    
    return dist3D <= threshold, dist3D
end

-- ============================================================================
-- Initialize proximity data for session
-- ============================================================================
function initializeProximityTracking()
    proximityData = {}
    lastProximityCheck = 0
    combatProximityEvents = {}
    et.G_LogPrint("Proximity tracking initialized\n")
end

-- ============================================================================
-- Check proximity between all teammates (called periodically)
-- ============================================================================
function checkTeammateProximity(levelTime)
    local maxClients = tonumber(et.trap_Cvar_Get("sv_maxClients"))
    
    -- Only check every N milliseconds
    if levelTime - lastProximityCheck < PROXIMITY_CHECK_INTERVAL then
        return
    end
    
    lastProximityCheck = levelTime
    
    -- Check all player pairs
    for i = 0, maxClients - 1 do
        if et.gentity_get(i, "pers.connected") == 2 then
            local team_i = et.gentity_get(i, "sess.sessionTeam")
            
            -- Only track players on actual teams
            if team_i == 1 or team_i == 2 then
                local pos_i = et.gentity_get(i, "r.currentOrigin")
                local guid_i = getGUID(i)
                
                for j = i + 1, maxClients - 1 do
                    if et.gentity_get(j, "pers.connected") == 2 then
                        local team_j = et.gentity_get(j, "sess.sessionTeam")
                        
                        -- Only track teammates (same team)
                        if team_i == team_j then
                            local pos_j = et.gentity_get(j, "r.currentOrigin")
                            local guid_j = getGUID(j)
                            
                            local isNear, dist = fastProximityCheck(
                                pos_i, pos_j, PROXIMITY_THRESHOLD
                            )
                            
                            if isNear then
                                -- Track cumulative time near each other
                                local pair_key = getPairKey(guid_i, guid_j)
                                
                                if not proximityData[pair_key] then
                                    proximityData[pair_key] = {
                                        player_a = guid_i,
                                        player_b = guid_j,
                                        time_near = 0,
                                        shared_events = 0
                                    }
                                end
                                
                                -- Add time (check interval in seconds)
                                proximityData[pair_key].time_near = 
                                    proximityData[pair_key].time_near + 
                                    (PROXIMITY_CHECK_INTERVAL / 1000)
                            end
                        end
                    end
                end
            end
        end
    end
end

-- ============================================================================
-- Track proximity during combat events (called from et_Damage)
-- ============================================================================
function trackCombatProximity(victim, attacker, damage)
    if not TRACK_COMBAT_PROXIMITY then
        return
    end
    
    if victim == attacker then
        return
    end
    
    local victim_team = et.gentity_get(victim, "sess.sessionTeam")
    local victim_pos = et.gentity_get(victim, "r.currentOrigin")
    local victim_guid = getGUID(victim)
    
    -- Find nearby teammates when damage occurs
    local maxClients = tonumber(et.trap_Cvar_Get("sv_maxClients"))
    
    for i = 0, maxClients - 1 do
        if i ~= victim and et.gentity_get(i, "pers.connected") == 2 then
            local teammate_team = et.gentity_get(i, "sess.sessionTeam")
            
            if teammate_team == victim_team then
                local teammate_pos = et.gentity_get(i, "r.currentOrigin")
                local teammate_guid = getGUID(i)
                
                local isNear, dist = fastProximityCheck(
                    victim_pos, teammate_pos, PROXIMITY_THRESHOLD
                )
                
                if isNear then
                    -- Log combat proximity event
                    local pair_key = getPairKey(victim_guid, teammate_guid)
                    
                    if not proximityData[pair_key] then
                        proximityData[pair_key] = {
                            player_a = victim_guid,
                            player_b = teammate_guid,
                            time_near = 0,
                            shared_events = 0
                        }
                    end
                    
                    -- Increment shared combat events (crossfire indicator)
                    proximityData[pair_key].shared_events = 
                        proximityData[pair_key].shared_events + 1
                end
            end
        end
    end
end

-- ============================================================================
-- Get consistent pair key (alphabetically sorted)
-- ============================================================================
function getPairKey(guid_a, guid_b)
    if guid_a < guid_b then
        return guid_a .. "|" .. guid_b
    else
        return guid_b .. "|" .. guid_a
    end
end

-- ============================================================================
-- Export proximity data to stats file
-- ============================================================================
function exportProximityData(fileHandle)
    if not fileHandle then
        return
    end
    
    -- Write header
    fileHandle:write("\\nPROXIMITY_DATA\\n")
    
    -- Write each player pair's proximity data
    for pair_key, data in pairs(proximityData) do
        if data.time_near > 0 or data.shared_events > 0 then
            fileHandle:write(string.format(
                "%s\\t%s\\t%.1f\\t%d\\n",
                data.player_a,
                data.player_b,
                data.time_near,
                data.shared_events
            ))
        end
    end
    
    et.G_LogPrint(string.format(
        "Exported proximity data for %d player pairs\n",
        tableLength(proximityData)
    ))
end

-- ============================================================================
-- Hook: Initialize on game start
-- ============================================================================
function et_InitGame(levelTime, randomSeed, restart)
    -- ... your existing initialization ...
    
    initializeProximityTracking()
end

-- ============================================================================
-- Hook: Check proximity periodically
-- ============================================================================
function et_RunFrame(levelTime)
    -- ... your existing frame logic ...
    
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate"))
    
    -- Only track during active gameplay (not warmup/intermission)
    if gamestate == 0 then  -- GS_PLAYING
        checkTeammateProximity(levelTime)
    end
end

-- ============================================================================
-- Hook: Track combat proximity on damage
-- ============================================================================
function et_Damage(target, attacker, damage, dflags, mod)
    -- ... your existing damage logic ...
    
    if TRACK_COMBAT_PROXIMITY then
        trackCombatProximity(target, attacker, damage)
    end
end

-- ============================================================================
-- Hook: Export proximity data at session end
-- ============================================================================
function et_ShutdownGame(restart)
    -- ... your existing shutdown logic ...
    
    -- Export proximity data to stats file
    local statsFile = io.open(getStatsFilename(), "a")
    if statsFile then
        exportProximityData(statsFile)
        statsFile:close()
    end
end
```

#### Day 3-4: Test Lua Script Locally

**Testing steps:**

1. **Backup your current `c0rnp0rn3.lua`:**
```bash
cp c0rnp0rn3.lua c0rnp0rn3.lua.backup
```

2. **Add proximity module** to `c0rnp0rn3.lua`

3. **Start local test server:**
```bash
# Start ET:Legacy server with your modified script
etlded +set fs_game legacy +exec server.cfg
```

4. **Connect with 2+ players** (or bots)

5. **Play a round** and check for:
   - No server lag
   - Console logs: "Proximity tracking initialized"
   - Stats file includes `PROXIMITY_DATA` section

6. **Check stats file output:**
```
PROXIMITY_DATA
5C3D0BC7	D8423F90	45.2	3
D8423F90	E16F9C0A	38.7	5
```

#### Day 5: Performance Testing & Optimization

**Measure performance impact:**

```lua
-- Add benchmarking
function checkTeammateProximity(levelTime)
    local startTime = et.trap_Milliseconds()
    
    -- ... proximity checking code ...
    
    local endTime = et.trap_Milliseconds()
    local duration = endTime - startTime
    
    if duration > 50 then  -- More than 50ms is concerning
        et.G_LogPrint(string.format(
            "⚠️  Proximity check took %dms (too slow!)\n", 
            duration
        ))
    end
end
```

**Optimization strategies if too slow:**

1. **Increase check interval** (5s → 10s)
2. **Spatial partitioning** (divide map into sectors)
3. **Only check active players** (not spectators)
4. **Disable during non-competitive matches**

---

### **Week 7: Parser & Database Integration**

#### Day 6-7: Update Stats Parser

**Update `bot/community_stats_parser.py`:**

```python
class CommunityStatsParser:
    # ... existing methods ...
    
    def parse_proximity_data(self, content: str) -> List[Dict]:
        """
        Parse PROXIMITY_DATA section from stats file
        
        Format:
        PROXIMITY_DATA
        player_a_guid	player_b_guid	time_near	shared_events
        """
        
        proximity_section = self._extract_section(content, 'PROXIMITY_DATA')
        
        if not proximity_section:
            logger.debug("No proximity data in stats file")
            return []
        
        proximity_events = []
        
        for line in proximity_section.split('\n'):
            if not line.strip() or line.startswith('PROXIMITY_DATA'):
                continue
            
            parts = line.split('\t')
            
            if len(parts) >= 4:
                try:
                    proximity_events.append({
                        'player_a_guid': parts[0].strip(),
                        'player_b_guid': parts[1].strip(),
                        'time_near_seconds': float(parts[2]),
                        'shared_events': int(parts[3])
                    })
                except ValueError as e:
                    logger.warning(f"Error parsing proximity line: {line} - {e}")
        
        logger.info(f"Parsed {len(proximity_events)} proximity events")
        return proximity_events
```

#### Day 8-9: Database Storage

**Create migration for proximity table:**

```python
# tools/migrations/003_create_proximity_events.py

import sqlite3

def create_proximity_table():
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proximity_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            player_a_guid TEXT NOT NULL,
            player_b_guid TEXT NOT NULL,
            time_near_seconds REAL DEFAULT 0,
            shared_events INTEGER DEFAULT 0,
            combat_proximity_score REAL DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            UNIQUE(session_id, player_a_guid, player_b_guid)
        )
    ''')
    
    # Index for fast queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_proximity_players
        ON proximity_events(player_a_guid, player_b_guid)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_proximity_session
        ON proximity_events(session_id)
    ''')
    
    conn.commit()
    conn.close()
    print("✅ proximity_events table created")

if __name__ == '__main__':
    create_proximity_table()
```

**Update importer to save proximity data:**

```python
# In tools/simple_bulk_import.py or bot/ultimate_bot.py

async def import_proximity_events(
    session_id: int,
    proximity_data: List[Dict],
    db_path: str
):
    """Save proximity events to database"""
    
    if not proximity_data:
        return
    
    async with aiosqlite.connect(db_path) as db:
        for event in proximity_data:
            # Calculate combat proximity score
            # (time_near + shared_events weighted)
            combat_score = (
                event['time_near_seconds'] * 0.5 +
                event['shared_events'] * 2.0
            )
            
            await db.execute('''
                INSERT OR REPLACE INTO proximity_events (
                    session_id, player_a_guid, player_b_guid,
                    time_near_seconds, shared_events, combat_proximity_score
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                event['player_a_guid'],
                event['player_b_guid'],
                event['time_near_seconds'],
                event['shared_events'],
                combat_score
            ))
        
        await db.commit()
    
    logger.info(f"✅ Imported {len(proximity_data)} proximity events")
```

---

### **Week 8: Analytics & Bot Commands**

#### Day 10-11: Proximity Analytics

**Create `analytics/proximity_analyzer.py`:**

```python
"""Analyze proximity data for teamwork insights"""

import sqlite3
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class TeamworkMetrics:
    """Teamwork metrics based on proximity"""
    time_together: float
    combat_events: int
    teamwork_score: float
    crossfire_setups: int

class ProximityAnalyzer:
    """Analyze proximity data for teamwork patterns"""
    
    def __init__(self, db_path: str = 'etlegacy_production.db'):
        self.db_path = db_path
    
    async def calculate_teamwork_score(
        self,
        player_a_guid: str,
        player_b_guid: str
    ) -> Optional[TeamworkMetrics]:
        """
        Calculate teamwork score based on proximity data
        """
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all proximity events for this pair
        query = '''
            SELECT 
                SUM(time_near_seconds) as total_time,
                SUM(shared_events) as total_events,
                AVG(combat_proximity_score) as avg_score,
                COUNT(*) as sessions_together
            FROM proximity_events
            WHERE (player_a_guid = ? AND player_b_guid = ?)
               OR (player_a_guid = ? AND player_b_guid = ?)
        '''
        
        cursor.execute(query, (
            player_a_guid, player_b_guid,
            player_b_guid, player_a_guid
        ))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row or row['sessions_together'] == 0:
            return None
        
        return TeamworkMetrics(
            time_together=row['total_time'] or 0,
            combat_events=row['total_events'] or 0,
            teamwork_score=row['avg_score'] or 0,
            crossfire_setups=row['total_events'] or 0  # Estimate
        )
```

#### Day 12-14: Add Bot Commands

```python
# Add to SynergyAnalytics Cog in bot/ultimate_bot.py

@commands.command(name='teamwork', aliases=['proximity', 'crossfire'])
async def teamwork_command(
    self,
    ctx,
    player1: str = None,
    player2: str = None
):
    """
    Show teamwork analysis based on proximity tracking
    
    Usage:
        !teamwork @Player1 @Player2
    """
    
    from analytics.proximity_analyzer import ProximityAnalyzer
    
    # Get player GUIDs
    guid1 = await self._resolve_player(ctx, player1)
    guid2 = await self._resolve_player(ctx, player2)
    
    if not guid1 or not guid2:
        await ctx.send("❌ Could not find players")
        return
    
    analyzer = ProximityAnalyzer(self.bot.db_path)
    metrics = await analyzer.calculate_teamwork_score(guid1, guid2)
    
    if not metrics:
        await ctx.send("❌ No proximity data available")
        return
    
    # Create embed
    name1 = await self._get_player_name(guid1)
    name2 = await self._get_player_name(guid2)
    
    embed = discord.Embed(
        title=f"🤝 Teamwork Analysis: {name1} + {name2}",
        color=0x00BFFF
    )
    
    embed.add_field(
        name="⏱️ Time Together",
        value=f"{metrics.time_together:.0f} seconds",
        inline=True
    )
    
    embed.add_field(
        name="🎯 Combat Events",
        value=f"{metrics.combat_events} crossfire setups",
        inline=True
    )
    
    embed.add_field(
        name="💯 Teamwork Score",
        value=f"{metrics.teamwork_score:.1f}",
        inline=True
    )
    
    # Interpretation
    if metrics.teamwork_score > 50:
        interpretation = "🔥 Excellent teamwork! Stick together."
    elif metrics.teamwork_score > 20:
        interpretation = "✅ Good coordination"
    else:
        interpretation = "➖ Limited teamwork detected"
    
    embed.add_field(
        name="📝 Analysis",
        value=interpretation,
        inline=False
    )
    
    await ctx.send(embed=embed)
```

---

## 📊 Testing Checklist

### Lua Script Tests

- [ ] No server lag during matches
- [ ] Proximity data appears in stats files
- [ ] Console shows no errors
- [ ] Performance <50ms per check

### Parser Tests

- [ ] Proximity section parsed correctly
- [ ] Data imported to database
- [ ] No parsing errors

### Bot Tests

- [ ] `!teamwork` command works
- [ ] Data correlates with actual gameplay
- [ ] Community validation

---

## 🎯 Success Criteria

✅ **Phase 3 Complete When:**

1. Lua script runs without lag
2. Proximity data collected accurately
3. Bot commands display teamwork metrics
4. Community finds insights valuable

---

## ⚠️ Troubleshooting

### "Server lag during matches"

- Increase `PROXIMITY_CHECK_INTERVAL` (5s → 10s)
- Disable `TRACK_COMBAT_PROXIMITY`
- Only check during non-critical moments

### "No proximity data in stats files"

- Check console for Lua errors
- Verify `exportProximityData()` is called
- Check file permissions

### "Inaccurate proximity detection"

- Adjust `PROXIMITY_THRESHOLD` (256 → 300)
- Use 2D distance only (ignore Z axis)
- Validate with spectator mode

---

## 🚀 Next Steps

After Phase 3:

1. **Combine all three phases** into unified analytics
2. **Advanced visualizations** (heatmaps, network graphs)
3. **Machine learning** (predict match outcomes)
4. **Historical trends** (how has synergy changed over time?)

---

**Status:** Optional - Implement only if needed  
**Start Date:** November 10, 2025 (after Phase 2)  
**Target Completion:** December 1, 2025
