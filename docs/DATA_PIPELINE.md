# Data Pipeline: Game Server to Discord

Complete data flow documentation for the ET:Legacy Stats Bot.

---

## 📊 Pipeline Overview

```
ET Game Server
      ↓
Stats Files (.txt)
      ↓
Local Directory (local_stats/)
      ↓
Stats Parser (community_stats_parser.py)
      ↓
PostgreSQL Database
      ↓
Bot Query (database_adapter.py)
      ↓
Discord Commands (cogs)
      ↓
User Sees Stats
```

---

## 🔄 Stage 1: Stats File Generation

**Source:** ET:Legacy game server mod  
**Trigger:** Round completes  
**Output:** Plain text file with tab-separated values

### File Naming Convention
```
YYYY-MM-DD-HHMMSS-mapname-round-N.txt
Example: 2025-11-06-213045-supply-round-1.txt
```

### File Location
- Server writes to: `/path/to/etmain/stats/`
- Contains: All player stats for that round
- Format: Tab-separated fields (50+ per player)

### File Contents Example
```
Player Stats:
seareal    15  8  28.5  450  ...  (50+ fields)
carnage    12  10 25.0  380  ...
brewdog    18  6  32.1  520  ...
```

---

## 🔄 Stage 2: File Collection

### Method 1: Local Bot (Direct Access)
```
local_stats/
├── 2025-11-06-210000-supply-round-1.txt
├── 2025-11-06-213300-supply-round-2.txt
└── ...
```
- Bot reads directly from local directory
- No network overhead
- Fastest method

### Method 2: Remote Bot (SSH/SCP)
```python
# ssh_monitor.py downloads files
ssh.connect(server_ip, username, key_file)
scp.get('/path/to/stats/*.txt', 'bot/local_stats/')
```
- Downloads via SSH every 30 seconds
- Tracks processed files to avoid duplicates
- Requires SSH key authentication

---

## 🔄 Stage 3: Stats Parsing

**Parser:** `bot/community_stats_parser.py` (875 lines)  
**Class:** `C0RNP0RN3StatsParser`

### Parsing Process

```python
from bot.community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()
data = parser.parse_file('2025-11-06-210000-supply-round-1.txt')

# Returns structured dictionary:
{
    'round_info': {
        'map_name': 'supply',
        'timestamp': '2025-11-06 21:00:00',
        'axis_score': 0,
        'allies_score': 1,
        'winning_team': 'allies'
    },
    'players': [
        {
            'player_name': 'seareal',
            'team': 'axis',
            'kills': 15,
            'deaths': 8,
            'accuracy': 28.5,
            'damage_given': 450,
            'xp_total': 280,
            ... # 50+ more fields
            'weapons': [
                {'name': 'thompson', 'kills': 8, 'accuracy': 32.1},
                {'name': 'mp40', 'kills': 7, 'accuracy': 25.0}
            ]
        },
        ... # 11 more players
    ]
}
```

### Key Parser Functions

- **`parse_file(path)`** - Main entry point
- **`extract_player_stats()`** - Parse per-player data
- **`extract_weapon_stats()`** - Parse weapon-specific stats
- **`calculate_differential()`** - R2 cumulative stats calculation

### R2 Differential Calculation

**Problem:** ET shows cumulative stats in Round 2
- R1: kills=10, deaths=5
- R2: kills=25, deaths=12 (includes R1!)

**Solution:** Subtract R1 from R2
```python
r2_only_kills = r2_kills - r1_kills  # 25 - 10 = 15
r2_only_deaths = r2_deaths - r1_deaths  # 12 - 5 = 7
```

---

## 🔄 Stage 4: Database Import

**Manager:** `postgresql_database_manager.py`  
**Features:** Transaction safety, duplicate detection, rollback support

### Import Flow

```python
# 1. Calculate SHA256 hash of file
file_hash = sha256(file_contents)

# 2. Check if already processed
if file_hash in processed_files:
    print("Already imported, skipping")
    return

# 3. Begin transaction
async with db.transaction():
    # 4. Insert round metadata
    round_id = await db.insert_round(round_data)
    
    # 5. Insert player stats (12 players)
    for player in players:
        await db.insert_player_stats(round_id, player)
        
        # 6. Insert weapon stats (~8 weapons per player)
        for weapon in player['weapons']:
            await db.insert_weapon_stats(player_id, weapon)
    
    # 7. Mark file as processed
    await db.mark_processed(file_path, file_hash)
    
    # 8. Auto-assign to gaming session
    await db.assign_gaming_session(round_id)
    
    # 9. Commit transaction
    # If ANY step fails, entire import rolls back
```

### Database Tables Updated

1. **`rounds`** - Round metadata (map, scores, timestamp)
2. **`player_stats`** - Player performance (50+ fields)
3. **`weapon_stats`** - Weapon usage per player
4. **`processed_files`** - SHA256 tracking
5. **`gaming_sessions`** - Session grouping

### Duplicate Prevention

```python
# SHA256 ensures exact same file never imported twice
if calculate_hash(file) == existing_hash:
    raise DuplicateError("File already processed")
```

---

## 🔄 Stage 5: Bot Database Access

**Adapter:** `bot/core/database_adapter.py`  
**Supports:** PostgreSQL (primary), SQLite (fallback)  
**Mode:** Async queries (asyncpg/aiosqlite)

### Query Example

```python
from bot.core.database_adapter import create_adapter

# Bot creates adapter on startup
db = create_adapter(
    database_type='postgres',
    host='localhost',
    database='et_stats'
)

# Cogs query via adapter
async def get_player_stats(player_name):
    query = """
        SELECT 
            SUM(kills) as total_kills,
            SUM(deaths) as total_deaths,
            ROUND(AVG(accuracy_percent), 2) as avg_accuracy,
            COUNT(DISTINCT round_id) as rounds_played
        FROM player_stats
        WHERE player_name = $1
    """
    return await db.fetch_one(query, player_name)
```

### Performance Optimization

- **Stats Cache:** `bot/core/stats_cache.py` caches frequent queries
- **Connection Pooling:** asyncpg pool (10 connections)
- **Batch Queries:** Combine multiple stats in one query

---

## 🔄 Stage 6: Discord Commands

**Framework:** discord.py with cog architecture  
**Cogs:** 14 command modules  
**Commands:** 50+ total

### Command Flow Example: `!stats seareal`

```python
# In stats_cog.py
@commands.command()
async def stats(self, ctx, player_name: str):
    # 1. Query database
    stats = await self.get_player_stats(player_name)
    
    # 2. Format data
    embed = discord.Embed(title=f"Stats for {player_name}")
    embed.add_field(name="K/D", value=f"{stats['kd']}")
    embed.add_field(name="Accuracy", value=f"{stats['accuracy']}%")
    
    # 3. Send to Discord
    await ctx.send(embed=embed)
```

### Graph Generation Example: `!last_session`

```python
# In last_session_cog.py (111KB)
@commands.command()
async def last_session(self, ctx):
    # 1. Get last gaming session
    session = await self.get_latest_session()
    
    # 2. Generate 6 graphs with matplotlib
    graphs = [
        self.generate_kd_graph(session),
        self.generate_accuracy_graph(session),
        self.generate_weapon_graph(session),
        self.generate_map_graph(session),
        self.generate_team_graph(session),
        self.generate_time_graph(session)
    ]
    
    # 3. Combine into single image
    final_image = self.combine_graphs(graphs)
    
    # 4. Send to Discord
    await ctx.send(file=discord.File(final_image))
```

---

## 🔄 Stage 7: User Interaction

### Command Examples

**Basic Stats:**
```
User: !stats seareal
Bot: 📊 Stats for seareal
     🎯 K/D: 1.87 (450 kills, 240 deaths)
     🎲 Accuracy: 28.5%
     🕒 Rounds Played: 48
     ⏱️ Time Played: 12h 35m
```

**Last Session Analytics:**
```
User: !last_session
Bot: [Sends 6-graph image showing:]
     - Player performance comparison
     - Weapon usage distribution
     - Map breakdown
     - Kill metrics
     - Team analysis
     - Time-based trends
```

**Leaderboards:**
```
User: !top kills
Bot: 🏆 Top Players by Kills
     1. seareal - 450 kills
     2. carnage - 420 kills
     3. brewdog - 380 kills
```

---

## ⏱️ Timing & Automation

### Real-Time Flow

```
Round Ends (15:00)
     ↓ <1 second
Stats File Created (15:00:01)
     ↓ <30 seconds (SSH monitor checks every 30s)
File Downloaded (15:00:30)
     ↓ <2 seconds
File Parsed (15:00:32)
     ↓ <1 second
Database Import (15:00:33)
     ↓ instant
Bot Queries Updated (15:00:33)
     ↓ user triggers command
Discord Response (when user runs !stats)
```

### Automation Schedule

- **SSH Monitor:** Every 30 seconds
- **Database Maintenance:** Every 24 hours
- **Health Check:** Every 5 minutes
- **Metrics Log:** Every hour

---

## 🔒 Data Integrity

### Duplicate Prevention
```python
# SHA256 hash of entire file
hash = hashlib.sha256(file_contents).hexdigest()

# Stored in processed_files table
if hash already exists:
    skip import
```

### Transaction Safety
```python
# All imports wrapped in transaction
async with db.transaction():
    # If ANY step fails, entire import rolls back
    insert_round()
    insert_players()
    insert_weapons()
    mark_processed()
    # Commit only if all succeed
```

### Data Validation
- Player names sanitized (no SQL injection)
- Team values validated ('axis'/'allies' only)
- Numeric fields bounds checked
- Timestamp format verified
- Weapon names normalized

---

## 📊 Performance Metrics

### Typical Processing Times

- **File Parse:** 50-200ms (depends on player count)
- **Database Import:** 100-500ms (12 players)
- **Query Response:** 10-50ms (with cache)
- **Graph Generation:** 500-2000ms (6 graphs)
- **Discord Send:** 100-300ms

### Scalability

- **Files Processed:** 1000s without issue
- **Database Size:** 100k+ rounds supported
- **Concurrent Queries:** 10+ simultaneous users
- **Memory Usage:** ~200MB (bot + cache)

---

## 🔧 Error Handling

### Common Issues & Solutions

**Issue:** Corrupted stats file  
**Solution:** Parser validates format, skips bad lines, logs error

**Issue:** Database connection lost  
**Solution:** Connection pool auto-reconnects, transaction rolls back

**Issue:** Duplicate import attempt  
**Solution:** SHA256 check prevents, logs duplicate detection

**Issue:** Discord rate limit  
**Solution:** Command cooldowns, queue system for graphs

---

## 📝 Data Flow Summary

```
1. Game generates stats file (1 per round)
2. File collected (local/SSH)
3. Parser extracts 50+ fields per player
4. Database imports with transaction safety
5. Bot queries via database adapter
6. Commands process and format data
7. Discord displays to users
```

**Total Pipeline Time:** ~30-60 seconds from round end to stats availability

**Data Preserved:**
- ✅ Every kill, death, shot fired
- ✅ Weapon accuracy per weapon
- ✅ Team assignments
- ✅ XP earned per category
- ✅ Objectives completed
- ✅ Time played per team
- ✅ Historical trends

**Result:** Complete, accurate, real-time ET:Legacy statistics!
