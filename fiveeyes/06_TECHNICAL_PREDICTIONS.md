# ⚡ Technical Predictions & Performance Analysis

**Last Updated:** October 6, 2025  
**Purpose:** Performance estimates, bottlenecks, and optimization strategies

---

## 🎯 Executive Summary

This document provides:
- **Performance predictions** for each phase
- **Bottleneck identification** and mitigation
- **Resource requirements** (CPU, memory, disk)
- **Scalability analysis** (10 vs 50 players)
- **Optimization strategies**

---

## 📊 Phase 1: Synergy Detection

### Performance Targets

| Operation | Target | Acceptable | Unacceptable |
|-----------|--------|------------|--------------|
| `!synergy` command | <1s | <2s | >3s |
| `!best_duos` | <2s | <3s | >5s |
| `!team_builder` (6 players) | <3s | <5s | >10s |
| Background recalculation (all pairs) | <5min | <15min | >30min |

### Algorithm Complexity

**Synergy Calculation (per pair):**
```
O(n) where n = number of sessions
- Query sessions with both players: O(log n) with index
- Calculate averages: O(n)
- Compare to solo performance: O(n)

Total: O(n) per pair
```

**All Pairs Calculation:**
```
For P players:
- Number of pairs: P * (P-1) / 2
- 30 players = 435 pairs
- 50 players = 1,225 pairs

Total time = pairs * avg_time_per_pair
```

### Performance Predictions

#### Community Size: 20-30 Active Players

**Initial calculation (all pairs):**
- Pairs to calculate: ~400-435
- Avg sessions per pair: ~10-50
- Time per pair: ~0.5-2 seconds
- **Total time: 3-15 minutes**

**Daily recalculation:**
- Only update pairs that played today
- Typically 5-10 pairs per day
- **Time: <30 seconds**

**Command response times:**
- `!synergy`: Database query only (already calculated)
  - Expected: **200-500ms**
- `!best_duos`: Simple sorted query
  - Expected: **300-800ms**
- `!team_builder` (6 players):
  - Combinations to check: C(6,3) = 20
  - Synergy lookups: 20 * 6 = 120 queries
  - Expected: **1-2 seconds**

#### Community Size: 50+ Active Players

**Initial calculation:**
- Pairs: ~1,225
- Time per pair: ~0.5-2 seconds
- **Total time: 10-40 minutes**

**Command responses:**
- Similar to smaller community (database indexed)
- `!synergy`: **300-700ms**
- `!best_duos`: **500ms-1s**
- `!team_builder`: **2-4 seconds**

### Bottlenecks & Solutions

#### Bottleneck 1: Initial Synergy Calculation

**Problem:** First-time calculation takes 10-40 minutes for all pairs

**Solutions:**
```python
# 1. Parallelize with asyncio (already using)
# 2. Add progress bar for user feedback
# 3. Run during low-traffic hours
# 4. Cache intermediate results

# Optimization: Batch queries
async def calculate_batch_synergies(pairs: List[Tuple[str, str]]):
    """Calculate multiple pairs in parallel"""
    tasks = [
        calculate_synergy(pair[0], pair[1])
        for pair in pairs
    ]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

#### Bottleneck 2: Team Builder Combinations

**Problem:** For 8 players, C(8,4) = 70 combinations to check

**Solution:**
```python
# Use greedy algorithm instead of brute force
def optimized_team_builder(players: List[str]) -> Dict:
    """
    Greedy approach:
    1. Sort players by rating
    2. Alternate picks (snake draft)
    3. Fine-tune with local swaps
    
    Complexity: O(n log n) instead of O(2^n)
    """
```

#### Bottleneck 3: Database Lock Contention

**Problem:** Multiple commands querying database simultaneously

**Solution:**
```python
# Use connection pooling
import aiosqlite

class DatabasePool:
    def __init__(self, db_path, pool_size=5):
        self.pool = [aiosqlite.connect(db_path) for _ in range(pool_size)]
    
    async def execute(self, query, params):
        # Round-robin connection usage
        conn = await self.pool[self.current_idx]
        self.current_idx = (self.current_idx + 1) % len(self.pool)
        return await conn.execute(query, params)
```

### Memory Usage

**Baseline (existing bot):** ~50-80 MB

**Phase 1 additions:**
- In-memory synergy cache: ~5-10 MB (for 400-1000 pairs)
- Additional Python objects: ~5-10 MB
- **Total Phase 1: ~60-100 MB**

**Optimization:**
```python
# Don't cache all synergies in memory
# Only cache recently accessed (LRU cache)

from functools import lru_cache

@lru_cache(maxsize=100)
async def get_synergy(player_a, player_b):
    # Cache only last 100 pairs accessed
    return await fetch_from_database(player_a, player_b)
```

---

## ⚖️ Phase 2: Role Normalization

### Performance Targets

| Operation | Target | Acceptable | Unacceptable |
|-----------|--------|------------|--------------|
| `!leaderboard normalized` | <2s | <3s | >5s |
| `!class_stats` | <1s | <2s | >3s |
| `!compare` | <1s | <2s | >3s |
| Daily rating recalculation | <10min | <30min | >60min |

### Algorithm Complexity

**Performance Score Calculation:**
```python
def calculate_performance_score(stats, player_class):
    # O(1) - just arithmetic
    # No database queries, pure math
    return weighted_sum / time_played
```

**Complexity: O(1) per player**

### Performance Predictions

#### Leaderboard Generation

**Process:**
1. Query all player stats: O(n) where n = players
2. Calculate normalized score for each: O(n) * O(1) = O(n)
3. Sort by score: O(n log n)

**For 30 players:**
- Query time: ~200ms
- Calculation: ~50ms (30 * 2ms)
- Sorting: ~5ms
- **Total: ~250-300ms** ✅

**For 100 players:**
- Query time: ~500ms
- Calculation: ~200ms
- Sorting: ~10ms
- **Total: ~700-800ms** ✅

#### Daily Rating Recalculation

**Process:**
1. Get all player GUIDs: O(1)
2. For each player:
   - Query all sessions: O(log n)
   - Calculate avg stats per class: O(sessions)
   - Update rating: O(1)

**For 30 players, ~200 sessions each:**
- 30 * 200ms = **6 seconds** ✅

**For 100 players:**
- 100 * 300ms = **30 seconds** ✅

### Bottlenecks & Solutions

#### Bottleneck 1: Leaderboard Query Performance

**Problem:** Aggregating stats for many players can be slow

**Solution:**
```sql
-- Create materialized view (updated daily)
CREATE TABLE IF NOT EXISTS player_stats_summary AS
SELECT 
    player_guid,
    player_class,
    AVG(kills) as avg_kills,
    AVG(deaths) as avg_deaths,
    -- ... other stats
FROM player_comprehensive_stats
GROUP BY player_guid, player_class;

-- Query from summary table (much faster)
SELECT * FROM player_stats_summary ORDER BY normalized_score DESC;
```

#### Bottleneck 2: Weight Tuning Updates

**Problem:** Changing weights requires recalculating all scores

**Solution:**
```python
# Store raw aggregated stats, recalculate scores on-the-fly
# Only ~30 calculations (one per player) = instant

# Or: Use background task to recalculate overnight
@tasks.loop(hours=24)
async def recalculate_normalized_scores():
    # Runs at 02:00 UTC when bot idle
    pass
```

### Memory Usage

**Phase 2 additions:**
- Role weights config: <1 MB
- Player ratings cache: ~2-5 MB
- **Total Phase 2: ~65-105 MB**

---

## 📍 Phase 3: Proximity Tracking (OPTIONAL)

### Performance Targets

| Operation | Target | Acceptable | Unacceptable |
|-----------|--------|------------|--------------|
| Lua proximity check (per frame) | <10ms | <50ms | >100ms |
| Stats file parsing (with proximity) | +10% | +25% | +50% |
| `!teamwork` command | <2s | <3s | >5s |

### Server-Side Performance

**Critical Concern:** Lua script runs ON GAME SERVER

#### Proximity Check Overhead

**Every 5 seconds for 6v6 match:**
```
Players: 12
Pairs to check: 12 * 11 / 2 = 66 pairs
Operations per check:
- Get positions: 12 * 3 = 36 lookups
- Distance calculations: 66 * 1 = 66 calculations
- Update tracking: ~10-20 writes

Total operations: ~100-120
Estimated time: 5-20ms per check
```

**For 3v3 match:**
```
Players: 6
Pairs: 15
Operations: ~30-40
Estimated time: 2-5ms per check ✅
```

**Verdict:** Acceptable overhead for 5-second intervals

#### Worst Case: Every Frame Check

**If checking every frame (60 FPS):**
```
60 checks per second * 20ms = 1200ms of overhead
= Server lag, unplayable ❌
```

**Mitigation:** NEVER check every frame, use intervals

### Lua Script Optimization

```lua
-- Optimization 1: 2D distance first
function fastProximityCheck(pos1, pos2, threshold)
    -- 2D check (cheap)
    local dx = pos1[1] - pos2[1]
    local dy = pos1[2] - pos2[2]
    local dist2D = math.sqrt(dx*dx + dy*dy)
    
    if dist2D > threshold then
        return false  -- No need for 3D check
    end
    
    -- 3D only if close
    local dz = pos1[3] - pos2[3]
    local dist3D = math.sqrt(dx*dx + dy*dy + dz*dz)
    return dist3D <= threshold
end

-- Optimization 2: Skip spectators
if et.gentity_get(i, "sess.sessionTeam") < 1 then
    goto continue  -- Skip spectators/intermission
end

-- Optimization 3: Spatial partitioning (advanced)
-- Divide map into sectors, only check nearby sectors
```

### Parser Performance

**Stats file growth:**
- Without proximity: ~5-10 KB
- With proximity: ~7-15 KB (+40% size)

**Parsing time:**
- Without proximity: ~50-100ms
- With proximity: ~60-125ms (+20% time)

**Verdict:** Acceptable increase

### Database Impact

**Proximity events per session:**
- 3v3, 15 min match: ~180 proximity checks (5s intervals)
- Pairs near each other: ~10-30 per session
- Database rows: +10-30 per session

**Growth over time:**
- 100 sessions: ~1,000-3,000 rows
- 1,000 sessions: ~10,000-30,000 rows
- **Database growth: ~5-15 MB per year**

### Bottlenecks & Solutions

#### Bottleneck 1: Lua Performance Impact

**Problem:** Server lag during proximity checks

**Solutions:**
1. **Increase interval** (5s → 10s)
2. **Disable during warmup/intermission**
3. **Only track during objective actions**
4. **Skip if server load high**

```lua
-- Dynamic interval based on server load
local CHECK_INTERVAL = 5000  -- Default 5s

function adjustCheckInterval()
    local serverFPS = et.trap_Cvar_Get("com_fps")
    
    if serverFPS < 20 then
        CHECK_INTERVAL = 10000  -- Slow down if lagging
    else
        CHECK_INTERVAL = 5000   -- Normal speed
    end
end
```

#### Bottleneck 2: Stats File Size Growth

**Problem:** Proximity data makes files larger

**Solution:**
```lua
-- Compress proximity data (only store significant pairs)
function exportProximityData(fileHandle)
    for pair_key, data in pairs(proximityData) do
        -- Only export if meaningful proximity
        if data.time_near > 10 or data.shared_events > 2 then
            fileHandle:write(formatProximityLine(data))
        end
    end
end
```

#### Bottleneck 3: Database Query Performance

**Problem:** Querying proximity events across many sessions

**Solution:**
```sql
-- Index on player pairs
CREATE INDEX idx_proximity_players 
ON proximity_events(player_a_guid, player_b_guid);

-- Aggregate query (fast)
SELECT 
    SUM(time_near_seconds) as total_time,
    SUM(shared_combat_events) as total_events
FROM proximity_events
WHERE (player_a_guid = ? AND player_b_guid = ?)
   OR (player_a_guid = ? AND player_b_guid = ?);
```

### Memory Usage (Server)

**Game server (Lua):**
- Proximity tracking state: ~500 KB - 2 MB
- Position caching: ~100-500 KB
- **Server RAM increase: ~1-3 MB** ✅

**Bot (Python):**
- Proximity analytics: ~5-10 MB
- **Total Phase 3: ~75-115 MB**

---

## 🔄 Scalability Analysis

### Current State (Baseline)

- **Players:** 20-30 active
- **Sessions per week:** 15-20
- **Database size:** ~15 MB
- **Bot memory:** ~50-80 MB

### After Phase 1+2 (No Proximity)

- **Players:** 30 → 50 (growth)
- **Synergy pairs:** 435 → 1,225 (+180%)
- **Database size:** ~16 MB (+7%)
- **Bot memory:** ~65-105 MB (+30%)

**Performance impact:**
- Initial calculation: 15min → 40min
- Command responses: +50-100ms
- **Verdict:** Scales well ✅

### After Phase 3 (With Proximity)

- **Database size:** ~25-30 MB (+66%)
- **Server CPU:** +5-10%
- **Bot memory:** ~75-115 MB (+50%)

**Performance impact:**
- Server lag: minimal (<5ms per check)
- Stats file size: +40%
- Parse time: +20%
- **Verdict:** Acceptable for 3v3/6v6 ✅

### Breaking Points

**Bot will struggle if:**
- ❌ 100+ active players (10,000+ pairs)
- ❌ 100+ sessions per day
- ❌ Real-time proximity tracking (every frame)

**Solutions for scale:**
- Use PostgreSQL instead of SQLite
- Implement caching layer (Redis)
- Horizontal scaling (multiple bot instances)
- Optimize Lua with C extensions

---

## 🎯 Optimization Strategies

### Database Optimizations

```sql
-- 1. Vacuum regularly
VACUUM;

-- 2. Analyze for query optimizer
ANALYZE;

-- 3. Create covering indexes
CREATE INDEX idx_synergy_lookup 
ON player_synergies(player_a_guid, player_b_guid, synergy_score);

-- 4. Use partial indexes
CREATE INDEX idx_high_synergy 
ON player_synergies(synergy_score) 
WHERE synergy_score > 0.5;
```

### Python Optimizations

```python
# 1. Use connection pooling
# 2. Batch database operations
# 3. Cache frequently accessed data
# 4. Use asyncio properly (no blocking calls)

# Example: Batch synergy calculation
async def calculate_synergies_batch(pairs: List[Tuple]):
    async with aiosqlite.connect(db_path) as db:
        for batch in chunks(pairs, 50):  # Process 50 at a time
            await asyncio.gather(*[
                calculate_synergy(db, p[0], p[1]) 
                for p in batch
            ])
```

### Lua Optimizations

```lua
-- 1. Use local variables (faster in Lua)
local proximityData = {}

-- 2. Avoid string concatenation in loops
-- Bad: str = str .. "data"
-- Good: table.insert(parts, "data"); str = table.concat(parts)

-- 3. Cache function results
local cachedPositions = {}

-- 4. Early exit conditions
if not isGameActive() then return end
```

---

## 📈 Monitoring & Metrics

### Key Metrics to Track

```python
# Bot metrics
metrics = {
    'command_response_time': {},  # Track per command
    'database_query_time': {},
    'synergy_calculation_time': {},
    'cache_hit_rate': 0.0,
    'active_connections': 0,
    'memory_usage_mb': 0,
}

# Server metrics (Phase 3)
server_metrics = {
    'proximity_check_time_ms': 0,
    'lua_memory_usage_kb': 0,
    'server_fps': 0,
    'player_count': 0,
}
```

### Performance Alerts

```python
# Alert if response times exceed thresholds
if response_time > 5000:  # 5 seconds
    logger.warning(f"Slow command response: {command_name} took {response_time}ms")
    # Send Discord notification to admin

if server_fps < 20:  # Game server lagging
    logger.critical("Server performance degraded, disabling proximity tracking")
    disable_proximity_tracking()
```

---

## 🎯 Summary

### Phase 1: Low Risk ✅
- **Performance:** Excellent (<2s responses)
- **Scalability:** Good (handles 50+ players)
- **Memory:** Low (~65-105 MB)
- **Recommendation:** Proceed confidently

### Phase 2: Low Risk ✅
- **Performance:** Excellent (<1s responses)
- **Scalability:** Excellent (O(n) complexity)
- **Memory:** Minimal (+5 MB)
- **Recommendation:** Proceed confidently

### Phase 3: Medium Risk ⚠️
- **Performance:** Good (5-20ms overhead)
- **Scalability:** Moderate (CPU-bound on server)
- **Memory:** Low (+10 MB)
- **Recommendation:** Proceed cautiously, test thoroughly

---

## 🔮 Future Optimizations

If you hit performance limits:

1. **Migrate to PostgreSQL** (better than SQLite for concurrent access)
2. **Add Redis caching layer** (instant command responses)
3. **Use Celery for background tasks** (offload heavy calculations)
4. **Implement API rate limiting** (prevent abuse)
5. **Add CDN for static assets** (if adding web dashboard)

---

**Conclusion:** All phases are performant for your community size. Phase 3 requires testing, but should work well for 3v3/6v6 competitive play.
