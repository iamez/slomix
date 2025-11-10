# 🚀 ET:Legacy Discord Bot - Performance & Feature Upgrade Roadmap

**Created:** November 9, 2025  
**Status:** Implementation Guide  
**Priority:** Ordered by impact and effort

---

## 📊 Current State Analysis

### What We Have
- ✅ Working voice detection (6+ players → auto-monitoring)
- ✅ PostgreSQL database with unified schema
- ✅ SSH auto-import for stats files
- ✅ 14 Cogs handling different commands
- ✅ Basic 5-minute TTL cache
- ✅ Discord player linking system
- ✅ Added paging for stats commands (e.g., !lb 2, !lb dpm 2) to navigate through large result sets

### What We're Missing
- ❌ Voice activity tracking (who played when)
- ❌ Performance metrics/monitoring
- ❌ Advanced caching (Redis)
- ❌ Database query optimization
- ❌ Connection pooling tuning
- ❌ Event-driven processing
- ❌ Role-based permissions for dangerous commands
- ❌ Substitution/addition tracking via voice channels
- ❌ Command rate limiting
- ❌ Audit logging for admin actions

---

## 🎯 Implementation Priority (10 Phases)

---

## PHASE 1: Voice Activity Tracking (HIGH PRIORITY)
**Effort:** 1-2 hours  
**Impact:** HIGH - Provides valuable session attendance data

### What to Capture
```python
voice_session_data = {
    # User Identity
    'discord_id': member.id,
    'discord_name': str(member),  # username#1234
    'display_name': member.display_name,  # Server nickname
    'is_linked': bool,  # Linked to ET account?
    'et_guid': str,  # If linked, their game GUID
    'et_name': str,  # If linked, their game name
    
    # Voice Activity
    'join_time': datetime,
    'leave_time': datetime,
    'duration_minutes': float,
    'channel_id': int,
    'channel_name': str,
    'team_identifier': str,  # 🆕 TEAM DETECTION: "Team A" / "Team B" based on channel
    
    # Voice State
    'is_muted': member.voice.mute,
    'is_deafened': member.voice.deaf,
    'is_self_muted': member.voice.self_mute,
    'is_self_deafened': member.voice.self_deaf,
    'is_streaming': member.voice.self_stream,
    'is_video': member.voice.self_video,
    
    # Session Context
    'gaming_session_id': int,  # Links to rounds.gaming_session_id
    'total_participants': int,
    'peak_participants': int
}
```

### Database Schema
```sql
-- PostgreSQL table for voice activity tracking
CREATE TABLE voice_activity (
    id SERIAL PRIMARY KEY,
    discord_id TEXT NOT NULL,
    discord_name TEXT,
    display_name TEXT,
    et_guid TEXT,  -- From player_links table
    et_name TEXT,  -- From player_links table
    session_date DATE NOT NULL,
    join_time TIMESTAMP NOT NULL,
    leave_time TIMESTAMP,
    duration_minutes REAL,
    channel_id BIGINT,
    channel_name TEXT,
    was_muted BOOLEAN DEFAULT FALSE,
    was_deafened BOOLEAN DEFAULT FALSE,
    gaming_session_id INTEGER,  -- Links to rounds.gaming_session_id
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_voice_discord_id ON voice_activity(discord_id);
CREATE INDEX idx_voice_session_date ON voice_activity(session_date DESC);
CREATE INDEX idx_voice_gaming_session ON voice_activity(gaming_session_id);
CREATE INDEX idx_voice_et_guid ON voice_activity(et_guid);
```

### Implementation File: `bot/core/voice_tracker.py`
```python
#!/usr/bin/env python3
"""
Voice Activity Tracker - Monitor Discord voice channel participation

Tracks:
- Who joined/left voice channels
- Duration of voice sessions
- Links Discord users to ET accounts
- Associates voice activity with gaming sessions
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Set

logger = logging.getLogger(__name__)


class VoiceTracker:
    """Tracks voice channel activity and links to gaming sessions"""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions: Dict[int, Dict] = {}  # discord_id -> session_data
        self.gaming_session_id: Optional[int] = None
        logger.info("✅ VoiceTracker initialized")
    
    async def on_voice_join(self, member, channel):
        """
        Track when someone joins a gaming voice channel
        
        Args:
            member: Discord Member object
            channel: Discord VoiceChannel object
        """
        if member.bot:
            return  # Ignore bots
        
        # Check if in monitored gaming channel
        if channel.id not in self.bot.gaming_voice_channels:
            return
        
        # Create session data
        session_data = {
            'join_time': datetime.utcnow(),
            'discord_name': str(member),  # username#1234
            'display_name': member.display_name,
            'channel_id': channel.id,
            'channel_name': channel.name,
            'was_muted': member.voice.mute if member.voice else False,
            'was_deafened': member.voice.deaf if member.voice else False
        }
        
        # Check if linked to ET account
        query = """
            SELECT player_guid, player_name 
            FROM player_links 
            WHERE discord_id = $1
        """
        result = await self.bot.db_adapter.fetch_one(query, (str(member.id),))
        
        if result:
            session_data['et_guid'] = result[0]
            session_data['et_name'] = result[1]
            logger.info(f"🎮 Linked player {result[1]} ({member.display_name}) joined voice")
        else:
            session_data['et_guid'] = None
            session_data['et_name'] = None
            logger.info(f"🎙️ {member.display_name} joined voice (not linked to ET account)")
        
        self.active_sessions[member.id] = session_data
    
    async def on_voice_leave(self, member, channel):
        """
        Track when someone leaves a gaming voice channel
        
        Args:
            member: Discord Member object
            channel: Discord VoiceChannel object
        """
        if member.bot or member.id not in self.active_sessions:
            return
        
        session = self.active_sessions[member.id]
        leave_time = datetime.utcnow()
        duration = (leave_time - session['join_time']).total_seconds() / 60.0
        
        # Save to database
        await self.save_voice_activity(
            discord_id=member.id,
            session=session,
            leave_time=leave_time,
            duration=duration
        )
        
        # Clean up
        del self.active_sessions[member.id]
        logger.info(f"👋 {member.display_name} left voice (duration: {duration:.1f} min)")
    
    async def on_voice_update(self, member, before, after):
        """
        Track voice state changes (mute, deafen, etc.)
        
        Args:
            member: Discord Member object
            before: VoiceState before update
            after: VoiceState after update
        """
        # Handle join
        if before.channel is None and after.channel is not None:
            await self.on_voice_join(member, after.channel)
        
        # Handle leave
        elif before.channel is not None and after.channel is None:
            await self.on_voice_leave(member, before.channel)
        
        # Handle channel switch
        elif before.channel != after.channel:
            if before.channel:
                await self.on_voice_leave(member, before.channel)
            if after.channel:
                await self.on_voice_join(member, after.channel)
        
        # Update mute/deafen state
        elif member.id in self.active_sessions:
            if after.mute != before.mute:
                self.active_sessions[member.id]['was_muted'] = after.mute
            if after.deaf != before.deaf:
                self.active_sessions[member.id]['was_deafened'] = after.deaf
    
    async def save_voice_activity(self, discord_id: int, session: Dict, 
                                 leave_time: datetime, duration: float):
        """
        Save voice activity record to database
        
        Args:
            discord_id: Discord user ID
            session: Session data dictionary
            leave_time: When they left
            duration: Duration in minutes
        """
        try:
            query = """
                INSERT INTO voice_activity 
                (discord_id, discord_name, display_name, et_guid, et_name,
                 session_date, join_time, leave_time, duration_minutes,
                 channel_id, channel_name, was_muted, was_deafened, gaming_session_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            """
            
            await self.bot.db_adapter.execute(query, (
                str(discord_id),
                session['discord_name'],
                session['display_name'],
                session.get('et_guid'),
                session.get('et_name'),
                session['join_time'].date(),
                session['join_time'],
                leave_time,
                duration,
                session['channel_id'],
                session['channel_name'],
                session['was_muted'],
                session['was_deafened'],
                self.gaming_session_id
            ))
            
            logger.debug(f"💾 Saved voice activity for {session['display_name']}")
            
        except Exception as e:
            logger.error(f"Failed to save voice activity: {e}", exc_info=True)
    
    def set_gaming_session_id(self, session_id: Optional[int]):
        """Set current gaming session ID for linking voice to game stats"""
        self.gaming_session_id = session_id
        logger.debug(f"🎮 Gaming session ID set to: {session_id}")
    
    async def get_session_attendance(self, gaming_session_id: int):
        """
        Get all players who were in voice during a gaming session
        
        Args:
            gaming_session_id: Gaming session to query
            
        Returns:
            List of dicts with player info
        """
        query = """
            SELECT 
                discord_name,
                display_name,
                et_guid,
                et_name,
                SUM(duration_minutes) as total_minutes,
                COUNT(*) as sessions,
                MIN(join_time) as first_join,
                MAX(leave_time) as last_leave
            FROM voice_activity
            WHERE gaming_session_id = $1
            GROUP BY discord_name, display_name, et_guid, et_name
            ORDER BY total_minutes DESC
        """
        
        return await self.bot.db_adapter.fetch_all(query, (gaming_session_id,))
```

### Integration into `ultimate_bot.py`
```python
# In ultimate_bot.py __init__ method, add:

from bot.core.voice_tracker import VoiceTracker

# Initialize voice tracker
self.voice_tracker = VoiceTracker(self)

# In on_voice_state_update method, add:
async def on_voice_state_update(self, member, before, after):
    """🎙️ Detect gaming sessions AND track voice activity"""
    
    # Track voice activity
    await self.voice_tracker.on_voice_update(member, before, after)
    
    # Rest of existing voice detection logic...
    if not self.automation_enabled:
        return
    # ... etc

# In _start_gaming_session method, add:
async def _start_gaming_session(self, participants):
    # ... existing code ...
    
    # Set gaming session ID for voice tracker
    # Use the gaming_session_id from the most recent round
    query = """
        SELECT gaming_session_id FROM rounds 
        WHERE gaming_session_id IS NOT NULL 
        ORDER BY round_date DESC, round_time DESC 
        LIMIT 1
    """
    result = await self.db_adapter.fetch_one(query)
    if result:
        self.voice_tracker.set_gaming_session_id(result[0])

# In _end_gaming_session method, add:
async def _end_gaming_session(self):
    # ... existing code ...
    
    # Clear gaming session ID
    self.voice_tracker.set_gaming_session_id(None)
```

### Migration to Add Table
Add to `postgresql_database_manager.py` in `_migrate_schema_if_needed()`:

```python
# Migration 3: Create voice_activity table if missing
voice_activity_exists = await conn.fetchval("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'voice_activity'
    )
""")

if not voice_activity_exists:
    logger.info("   ➕ Creating voice_activity table...")
    await conn.execute('''
        CREATE TABLE voice_activity (
            id SERIAL PRIMARY KEY,
            discord_id TEXT NOT NULL,
            discord_name TEXT,
            display_name TEXT,
            et_guid TEXT,
            et_name TEXT,
            session_date DATE NOT NULL,
            join_time TIMESTAMP NOT NULL,
            leave_time TIMESTAMP,
            duration_minutes REAL,
            channel_id BIGINT,
            channel_name TEXT,
            was_muted BOOLEAN DEFAULT FALSE,
            was_deafened BOOLEAN DEFAULT FALSE,
            gaming_session_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    await conn.execute('CREATE INDEX idx_voice_discord_id ON voice_activity(discord_id)')
    await conn.execute('CREATE INDEX idx_voice_session_date ON voice_activity(session_date DESC)')
    await conn.execute('CREATE INDEX idx_voice_gaming_session ON voice_activity(gaming_session_id)')
    await conn.execute('CREATE INDEX idx_voice_et_guid ON voice_activity(et_guid)')
    logger.info("   ✅ Created voice_activity table")
```

### New Discord Commands
Create `bot/cogs/voice_stats_cog.py`:

```python
@commands.command(name="voice_attendance")
async def voice_attendance(self, ctx, session_id: int = None):
    """Show who was in voice during a gaming session"""
    
    if session_id is None:
        # Get most recent session
        query = "SELECT MAX(gaming_session_id) FROM voice_activity"
        result = await self.bot.db_adapter.fetch_one(query)
        session_id = result[0] if result else None
    
    if not session_id:
        await ctx.send("No voice activity recorded yet!")
        return
    
    attendance = await self.bot.voice_tracker.get_session_attendance(session_id)
    
    embed = discord.Embed(
        title=f"🎙️ Voice Attendance - Session #{session_id}",
        color=0x00FF00
    )
    
    for i, player in enumerate(attendance, 1):
        et_info = f" → **{player['et_name']}**" if player['et_name'] else " (not linked)"
        embed.add_field(
            name=f"{i}. {player['display_name']}{et_info}",
            value=f"⏱️ {player['total_minutes']:.1f} min",
            inline=False
        )
    
    await ctx.send(embed=embed)
```

---

## 🎯 VOICE-BASED TEAM DETECTION (GAME CHANGER!)

### Why This Matters
Your current team detection uses **5 algorithms to GUESS teams** from game stats. It's probabilistic and can be wrong!

**But if players split into two voice channels → WE KNOW THE TEAMS with 100% confidence!**

### The Solution
```
Voice Channel "🔴 Team A - Axis"     Voice Channel "🔵 Team B - Allies"
├─ C0RNP0RN3 (linked)               ├─ TankMaster (linked)
├─ Medic123 (linked)                ├─ EngiPro (linked)
└─ SniperKing (linked)              └─ RamboJoe (linked)

Result: Perfect team assignments with confidence = 1.0 (100%)
```

### Implementation

**Add to voice_activity table:**
```sql
ALTER TABLE voice_activity ADD COLUMN team_identifier TEXT;  -- 'team_a' or 'team_b'
```

**New table for team snapshots:**
```sql
CREATE TABLE voice_team_snapshots (
    id SERIAL PRIMARY KEY,
    gaming_session_id INTEGER NOT NULL UNIQUE,
    snapshot_time TIMESTAMP NOT NULL,
    team_a_guids TEXT[],  -- Array of ET GUIDs
    team_b_guids TEXT[],
    team_a_discord_names TEXT[],
    team_b_discord_names TEXT[],
    confidence_score REAL DEFAULT 1.0,
    source TEXT DEFAULT 'voice_channels',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Capture teams at session start:**
```python
# In VoiceTracker class
async def capture_team_snapshot(self, gaming_session_id):
    """Capture who's in which voice channel = instant team detection!"""
    team_a_channel_id = int(os.getenv('TEAM_A_VOICE_CHANNEL'))
    team_b_channel_id = int(os.getenv('TEAM_B_VOICE_CHANNEL'))
    
    teams = {'team_a': [], 'team_b': []}
    
    # Get Team A members
    channel_a = self.bot.get_channel(team_a_channel_id)
    if channel_a:
        for member in channel_a.members:
            query = "SELECT player_guid FROM player_links WHERE discord_id = $1"
            result = await self.bot.db_adapter.fetch_one(query, (str(member.id),))
            if result:
                teams['team_a'].append({'guid': result[0], 'name': str(member)})
    
    # Get Team B members
    channel_b = self.bot.get_channel(team_b_channel_id)
    if channel_b:
        for member in channel_b.members:
            query = "SELECT player_guid FROM player_links WHERE discord_id = $1"
            result = await self.bot.db_adapter.fetch_one(query, (str(member.id),))
            if result:
                teams['team_b'].append({'guid': result[0], 'name': str(member)})
    
    # Save snapshot
    await self.save_team_snapshot(gaming_session_id, teams)
    
    logger.info(f"📸 Team snapshot: {len(teams['team_a'])} vs {len(teams['team_b'])}")
    return teams
```

**Priority-based team detection:**
```python
async def get_teams_for_session(gaming_session_id):
    """
    Get teams with priority:
    1. Voice snapshot (confidence: 1.0) ← BEST!
    2. Manual !set_teams (confidence: 0.9)
    3. Algorithmic detection (confidence: 0.5-0.8)
    """
    
    # Try voice first
    query = "SELECT team_a_guids, team_b_guids FROM voice_team_snapshots WHERE gaming_session_id = $1"
    voice_teams = await db.fetch_one(query, (gaming_session_id,))
    
    if voice_teams:
        logger.info("✅ Using VOICE CHANNEL teams (100% accurate!)")
        return {'team_a': voice_teams[0], 'team_b': voice_teams[1], 'confidence': 1.0}
    
    # Fallback to existing detection
    logger.warning("⚠️ No voice snapshot, using algorithmic detection")
    return await advanced_team_detector.detect_teams(gaming_session_id)
```

**New .env variables:**
```bash
TEAM_A_VOICE_CHANNEL=123456789  # Channel ID for Team A
TEAM_B_VOICE_CHANNEL=987654321  # Channel ID for Team B
```

### Benefits
- ✅ **100% Accuracy** - No guessing!
- ✅ **Instant Detection** - Know teams before match starts
- ✅ **Handles Subs** - Track channel switches
- ✅ **Works for Scrims** - Organized teams use separate channels
- ✅ **Confidence Tracking** - Voice=1.0, Manual=0.9, Auto=0.5-0.8

---

## PHASE 2: Database Query Optimization (CRITICAL)
**Effort:** 30 minutes  
**Impact:** HIGH - Immediate performance boost

### Add Missing Indexes
```sql
-- Run these on PostgreSQL database

-- Composite indexes for common queries
CREATE INDEX idx_player_stats_composite ON player_comprehensive_stats(round_id, player_guid);
CREATE INDEX idx_player_stats_date_desc ON player_comprehensive_stats(round_date DESC);
CREATE INDEX idx_rounds_gaming_session ON rounds(gaming_session_id) WHERE gaming_session_id IS NOT NULL;

-- Partial indexes for active data
CREATE INDEX idx_rounds_recent ON rounds(round_date DESC, round_time DESC) 
WHERE round_date >= CURRENT_DATE - INTERVAL '30 days';

-- Weapon stats optimization
CREATE INDEX idx_weapon_stats_player ON weapon_comprehensive_stats(player_guid, weapon_name);
```

### Add to `postgresql_database_manager.py`
In `_create_fresh_schema()` after existing indexes:

```python
# Advanced indexes for performance
await conn.execute('''
    CREATE INDEX idx_player_stats_composite 
    ON player_comprehensive_stats(round_id, player_guid)
''')
await conn.execute('''
    CREATE INDEX idx_player_stats_date_desc 
    ON player_comprehensive_stats(round_date DESC)
''')
await conn.execute('''
    CREATE INDEX idx_rounds_gaming_session 
    ON rounds(gaming_session_id) 
    WHERE gaming_session_id IS NOT NULL
''')
```

---

## PHASE 3: Connection Pool Tuning (QUICK WIN)
**Effort:** 15 minutes  
**Impact:** MEDIUM - Better concurrency

### Update `bot/core/database_adapter.py`
```python
class PostgreSQLAdapter(DatabaseAdapter):
    async def connect(self):
        """Create PostgreSQL connection pool with optimized settings"""
        self.pool = await asyncpg.create_pool(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            
            # Performance tuning
            min_size=5,           # Minimum connections (was: 10)
            max_size=20,          # Maximum connections (was: 10)
            max_queries=50000,    # Recycle connections after 50k queries
            max_inactive_connection_lifetime=300,  # 5 minutes
            command_timeout=60,   # 60 second timeout
            
            # Connection health
            timeout=30,           # Connection timeout
            server_settings={
                'application_name': 'et_legacy_bot',
                'jit': 'off'      # Disable JIT for short queries
            }
        )
        
        logger.info(f"✅ PostgreSQL pool: {self.pool.get_size()} active, "
                   f"{self.pool.get_min_size()}-{self.pool.get_max_size()} range")
```

---

## PHASE 4: Performance Metrics System (RECOMMENDED)
**Effort:** 2 hours  
**Impact:** MEDIUM - Visibility into bottlenecks

### Create `bot/core/metrics.py`
```python
#!/usr/bin/env python3
"""
Performance Metrics Tracker

Monitors:
- Command execution times
- Database query performance
- SSH check latency
- Memory usage
- Active sessions
"""

import logging
import time
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Optional
import psutil

logger = logging.getLogger(__name__)


class BotMetrics:
    """Track bot performance metrics"""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        
        # Command tracking
        self.command_history = deque(maxlen=max_history)
        self.command_counts = defaultdict(int)
        self.command_errors = defaultdict(int)
        
        # Database tracking
        self.db_query_history = deque(maxlen=max_history)
        self.slow_queries = []
        
        # SSH tracking
        self.ssh_check_history = deque(maxlen=max_history)
        
        # System tracking
        self.process = psutil.Process()
        
        logger.info("✅ Metrics tracker initialized")
    
    def track_command(self, command_name: str, duration: float, success: bool = True):
        """Track command execution"""
        self.command_history.append({
            'command': command_name,
            'duration': duration,
            'success': success,
            'timestamp': datetime.utcnow()
        })
        
        self.command_counts[command_name] += 1
        if not success:
            self.command_errors[command_name] += 1
        
        # Alert on slow commands
        if duration > 5.0:
            logger.warning(f"⚠️ Slow command: {command_name} took {duration:.2f}s")
    
    def track_db_query(self, query_type: str, duration: float, rows_affected: int = 0):
        """Track database query performance"""
        record = {
            'type': query_type,
            'duration': duration,
            'rows': rows_affected,
            'timestamp': datetime.utcnow()
        }
        
        self.db_query_history.append(record)
        
        # Track slow queries
        if duration > 1.0:
            self.slow_queries.append(record)
            logger.warning(f"⚠️ Slow query: {query_type} took {duration:.2f}s")
    
    def track_ssh_check(self, duration: float, files_found: int):
        """Track SSH monitoring performance"""
        self.ssh_check_history.append({
            'duration': duration,
            'files': files_found,
            'timestamp': datetime.utcnow()
        })
    
    def get_summary(self) -> Dict:
        """Get performance summary"""
        now = datetime.utcnow()
        last_hour = now - timedelta(hours=1)
        
        # Command stats
        recent_commands = [c for c in self.command_history if c['timestamp'] > last_hour]
        avg_command_time = (
            sum(c['duration'] for c in recent_commands) / len(recent_commands)
            if recent_commands else 0
        )
        
        # Database stats
        recent_queries = [q for q in self.db_query_history if q['timestamp'] > last_hour]
        avg_query_time = (
            sum(q['duration'] for q in recent_queries) / len(recent_queries)
            if recent_queries else 0
        )
        
        # System stats
        memory_mb = self.process.memory_info().rss / 1024 / 1024
        cpu_percent = self.process.cpu_percent()
        
        return {
            'uptime_seconds': (now - self.process.create_time()).total_seconds(),
            'memory_mb': round(memory_mb, 2),
            'cpu_percent': round(cpu_percent, 2),
            'commands_last_hour': len(recent_commands),
            'avg_command_time': round(avg_command_time, 3),
            'queries_last_hour': len(recent_queries),
            'avg_query_time': round(avg_query_time, 3),
            'slow_queries_count': len([q for q in self.slow_queries if q['timestamp'] > last_hour]),
            'top_commands': dict(sorted(self.command_counts.items(), key=lambda x: x[1], reverse=True)[:5]),
            'error_rate': sum(self.command_errors.values()) / max(sum(self.command_counts.values()), 1)
        }
    
    def get_slow_queries(self, limit: int = 10) -> List[Dict]:
        """Get recent slow queries"""
        return sorted(
            self.slow_queries[-100:],
            key=lambda x: x['duration'],
            reverse=True
        )[:limit]


# Decorator for tracking command execution
def track_performance(metrics: BotMetrics):
    """Decorator to track command performance"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start = time.time()
            success = True
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start
                command_name = func.__name__
                metrics.track_command(command_name, duration, success)
        return wrapper
    return decorator
```

### Add Metrics Command
In `bot/cogs/admin_cog.py`:

```python
@commands.command(name="metrics")
@commands.has_permissions(administrator=True)
async def metrics(self, ctx):
    """Show bot performance metrics"""
    if not hasattr(self.bot, 'metrics'):
        await ctx.send("Metrics not enabled")
        return
    
    summary = self.bot.metrics.get_summary()
    
    embed = discord.Embed(
        title="📊 Bot Performance Metrics",
        color=0x00FF00
    )
    
    # System
    uptime_hours = summary['uptime_seconds'] / 3600
    embed.add_field(
        name="System",
        value=f"⏱️ Uptime: {uptime_hours:.1f}h\n"
              f"💾 Memory: {summary['memory_mb']:.1f} MB\n"
              f"🔥 CPU: {summary['cpu_percent']:.1f}%",
        inline=True
    )
    
    # Commands
    embed.add_field(
        name="Commands (Last Hour)",
        value=f"📝 Total: {summary['commands_last_hour']}\n"
              f"⚡ Avg Time: {summary['avg_command_time']*1000:.0f}ms\n"
              f"❌ Error Rate: {summary['error_rate']*100:.1f}%",
        inline=True
    )
    
    # Database
    embed.add_field(
        name="Database (Last Hour)",
        value=f"🔍 Queries: {summary['queries_last_hour']}\n"
              f"⚡ Avg Time: {summary['avg_query_time']*1000:.0f}ms\n"
              f"🐌 Slow: {summary['slow_queries_count']}",
        inline=True
    )
    
    # Top commands
    top_cmds = "\n".join([f"`{k}`: {v}" for k, v in list(summary['top_commands'].items())[:5]])
    embed.add_field(
        name="Top Commands",
        value=top_cmds or "None",
        inline=False
    )
    
    await ctx.send(embed=embed)
```

### Initialize in `ultimate_bot.py`
```python
from bot.core.metrics import BotMetrics

# In __init__
self.metrics = BotMetrics()
```

---

## PHASE 5: Redis Caching Layer (ADVANCED)
**Effort:** 2-3 hours  
**Impact:** HIGH - Dramatically faster repeated queries

### Install Redis
```bash
# On VPS (Debian/Ubuntu)
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis

# Python package
pip install aioredis
```

### Create `bot/core/redis_cache.py`
```python
#!/usr/bin/env python3
"""
Redis-based caching layer for bot queries

Benefits:
- Much faster than database queries
- Shared cache across bot restarts
- TTL-based expiration
- Pattern-based invalidation
"""

import aioredis
import json
import logging
from typing import Optional, Any, List
from functools import wraps

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis caching layer"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None
    
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis = await aioredis.create_redis_pool(
                self.redis_url,
                minsize=5,
                maxsize=10,
                encoding='utf-8'
            )
            logger.info(f"✅ Connected to Redis: {self.redis_url}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self.redis = None
    
    async def close(self):
        """Close Redis connection"""
        if self.redis:
            self.redis.close()
            await self.redis.wait_closed()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.redis:
            return None
        
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 300):
        """Set value in cache with TTL (seconds)"""
        if not self.redis:
            return False
        
        try:
            serialized = json.dumps(value, default=str)
            await self.redis.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    async def delete(self, key: str):
        """Delete key from cache"""
        if not self.redis:
            return
        
        try:
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
    
    async def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern"""
        if not self.redis:
            return
        
        try:
            cursor = b'0'
            while cursor:
                cursor, keys = await self.redis.scan(cursor, match=pattern)
                if keys:
                    await self.redis.delete(*keys)
        except Exception as e:
            logger.error(f"Cache pattern delete error: {e}")
    
    async def invalidate_player(self, player_guid: str):
        """Invalidate all cached data for a player"""
        await self.delete_pattern(f"player:{player_guid}:*")
        await self.delete_pattern(f"stats:*:{player_guid}*")
    
    async def invalidate_session(self, session_id: int):
        """Invalidate all cached data for a session"""
        await self.delete_pattern(f"session:{session_id}:*")


def cached(key_prefix: str, ttl: int = 300):
    """
    Decorator to cache function results
    
    Usage:
        @cached("player_stats", ttl=600)
        async def get_player_stats(self, player_guid):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Build cache key
            cache_key = f"{key_prefix}:{':'.join(str(a) for a in args)}"
            
            # Try cache first
            if hasattr(self.bot, 'redis_cache'):
                cached_value = await self.bot.redis_cache.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"✅ Cache hit: {cache_key}")
                    return cached_value
            
            # Cache miss - fetch from source
            result = await func(self, *args, **kwargs)
            
            # Store in cache
            if hasattr(self.bot, 'redis_cache') and result is not None:
                await self.bot.redis_cache.set(cache_key, result, ttl)
                logger.debug(f"💾 Cached: {cache_key}")
            
            return result
        
        return wrapper
    return decorator
```

### Update `bot/core/stats_cache.py`
Replace in-memory cache with Redis:

```python
from bot.core.redis_cache import RedisCache, cached

class StatsCache:
    def __init__(self, bot):
        self.bot = bot
        # Remove in-memory cache, use Redis instead
    
    @cached("player_stats", ttl=300)
    async def get_player_stats(self, player_guid: str):
        """Get player stats (cached)"""
        query = """
            SELECT * FROM player_comprehensive_stats
            WHERE player_guid = $1
            ORDER BY round_date DESC
            LIMIT 100
        """
        return await self.bot.db_adapter.fetch_all(query, (player_guid,))
    
    @cached("session_stats", ttl=600)
    async def get_session_stats(self, session_id: int):
        """Get session stats (cached)"""
        query = """
            SELECT * FROM rounds
            WHERE gaming_session_id = $1
        """
        return await self.bot.db_adapter.fetch_all(query, (session_id,))
```

### Initialize in `ultimate_bot.py`
```python
from bot.core.redis_cache import RedisCache

# In __init__
self.redis_cache = RedisCache()
await self.redis_cache.connect()

# In close()
await self.redis_cache.close()
```

---

## PHASE 6: Event-Driven Stats Processing (ADVANCED)
**Effort:** 3-4 hours  
**Impact:** MEDIUM - Better handling of concurrent imports

### Create `bot/core/stats_processor.py`
```python
#!/usr/bin/env python3
"""
Event-driven stats processing with worker pool

Benefits:
- Non-blocking stats imports
- Concurrent processing
- Queue management
- Error handling & retry
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional
from collections import deque

logger = logging.getLogger(__name__)


class StatsProcessor:
    """Async worker pool for stats processing"""
    
    def __init__(self, bot, num_workers: int = 3):
        self.bot = bot
        self.num_workers = num_workers
        self.queue = asyncio.Queue()
        self.workers = []
        self.processing = False
        self.stats = {
            'processed': 0,
            'failed': 0,
            'queued': 0
        }
    
    async def start(self):
        """Start worker pool"""
        self.processing = True
        
        for i in range(self.num_workers):
            worker = asyncio.create_task(self._process_worker(i))
            self.workers.append(worker)
        
        logger.info(f"✅ Started {self.num_workers} stats processing workers")
    
    async def stop(self):
        """Stop worker pool"""
        self.processing = False
        
        # Wait for queue to empty
        await self.queue.join()
        
        # Cancel workers
        for worker in self.workers:
            worker.cancel()
        
        await asyncio.gather(*self.workers, return_exceptions=True)
        logger.info("✅ Stopped stats processing workers")
    
    async def enqueue(self, file_path: Path):
        """Add file to processing queue"""
        await self.queue.put(file_path)
        self.stats['queued'] += 1
        logger.debug(f"📥 Queued: {file_path.name} (queue size: {self.queue.qsize()})")
    
    async def _process_worker(self, worker_id: int):
        """Worker task that processes files from queue"""
        logger.info(f"🔧 Worker {worker_id} started")
        
        while self.processing:
            try:
                # Get file from queue (timeout to check processing flag)
                try:
                    file_path = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Process file
                try:
                    logger.info(f"⚙️ Worker {worker_id} processing: {file_path.name}")
                    
                    # Import using database manager
                    from postgresql_database_manager import PostgreSQLDatabaseManager
                    db_manager = PostgreSQLDatabaseManager()
                    await db_manager.initialize()
                    
                    success, message = await db_manager.process_file(file_path)
                    
                    await db_manager.close()
                    
                    if success:
                        self.stats['processed'] += 1
                        logger.info(f"✅ Worker {worker_id} completed: {file_path.name}")
                    else:
                        self.stats['failed'] += 1
                        logger.error(f"❌ Worker {worker_id} failed: {file_path.name} - {message}")
                
                except Exception as e:
                    self.stats['failed'] += 1
                    logger.error(f"❌ Worker {worker_id} error: {e}", exc_info=True)
                
                finally:
                    self.queue.task_done()
                    self.stats['queued'] -= 1
            
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}", exc_info=True)
        
        logger.info(f"🔧 Worker {worker_id} stopped")
```

---

## PHASE 7: Materialized Views for Analytics (OPTIONAL)
**Effort:** 2 hours  
**Impact:** LOW-MEDIUM - Faster complex queries

### Create Materialized Views
```sql
-- Player session summary
CREATE MATERIALIZED VIEW player_session_summary AS
SELECT 
    player_guid,
    player_name,
    gaming_session_id,
    COUNT(*) as rounds_played,
    SUM(kills) as total_kills,
    SUM(deaths) as total_deaths,
    AVG(accuracy) as avg_accuracy,
    AVG(kd_ratio) as avg_kd,
    SUM(damage_given) as total_damage,
    MAX(round_date) as last_played
FROM player_comprehensive_stats
WHERE gaming_session_id IS NOT NULL
GROUP BY player_guid, player_name, gaming_session_id;

CREATE INDEX idx_player_session_summary ON player_session_summary(player_guid, gaming_session_id);

-- Daily player stats
CREATE MATERIALIZED VIEW daily_player_stats AS
SELECT 
    player_guid,
    player_name,
    round_date,
    COUNT(DISTINCT gaming_session_id) as sessions_played,
    COUNT(*) as rounds_played,
    SUM(kills) as total_kills,
    SUM(deaths) as total_deaths,
    AVG(accuracy) as avg_accuracy,
    SUM(time_played_minutes) as total_minutes
FROM player_comprehensive_stats
GROUP BY player_guid, player_name, round_date;

CREATE INDEX idx_daily_player_stats ON daily_player_stats(player_guid, round_date DESC);
```

### Refresh Script
Create `tools/refresh_materialized_views.py`:

```python
#!/usr/bin/env python3
"""Refresh materialized views"""

import asyncio
from postgresql_database_manager import PostgreSQLDatabaseManager

async def refresh_views():
    db = PostgreSQLDatabaseManager()
    await db.initialize()
    
    async with db.pool.acquire() as conn:
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY player_session_summary")
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY daily_player_stats")
    
    await db.close()
    print("✅ Materialized views refreshed")

if __name__ == '__main__':
    asyncio.run(refresh_views())
```

### Cron Job
```bash
# Run every hour
0 * * * * /path/to/venv/bin/python /path/to/tools/refresh_materialized_views.py
```

---

## PHASE 8: Bot Sharding (FUTURE)
**Effort:** 4-6 hours  
**Impact:** HIGH - Required for 2500+ servers

Only implement when approaching Discord's sharding requirements.

### Update `ultimate_bot.py`
```python
from discord import AutoShardedBot

class ShardedETBot(AutoShardedBot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            shard_count=2,  # Auto-calculated if None
            intents=intents
        )
    
    async def on_shard_ready(self, shard_id):
        logger.info(f"🎉 Shard {shard_id} ready")
```

---

## PHASE 9: Security & Permissions System (CRITICAL)
**Effort:** 2-3 hours  
**Impact:** HIGH - Prevents bot/VPS damage, abuse prevention

### Why This Matters
Current state: **Anyone can run dangerous commands!**
- `!rebuild` - Wipes entire database
- `!import` - Triggers SSH connections
- `!check_schema` - Database operations
- Admin commands accessible to everyone

### Role-Based Access Control

#### Permission Levels
```python
# bot/core/permissions.py
from enum import Enum
from discord import Member
from discord.ext import commands

class PermissionLevel(Enum):
    PUBLIC = 0      # Everyone (read-only stats)
    TRUSTED = 1     # Linked players (can modify own data)
    MODERATOR = 2   # Server moderators (can manage sessions)
    ADMIN = 3       # Bot administrators (can import/rebuild)
    OWNER = 4       # God mode (unrestricted access)

# Your Discord ID (OWNER level)
OWNER_IDS = [231165917604741121]

# Role IDs from Discord server
ADMIN_ROLE_IDS = [123456789]     # Bot Admin role
MODERATOR_ROLE_IDS = [987654321] # Moderator role
TRUSTED_ROLE_IDS = [111111111]   # Verified Player role

def get_permission_level(member: Member) -> PermissionLevel:
    """Determine user's permission level"""
    
    # Owner check (you!)
    if member.id in OWNER_IDS:
        return PermissionLevel.OWNER
    
    # Admin check
    if any(role.id in ADMIN_ROLE_IDS for role in member.roles):
        return PermissionLevel.ADMIN
    
    # Moderator check
    if any(role.id in MODERATOR_ROLE_IDS for role in member.roles):
        return PermissionLevel.MODERATOR
    
    # Trusted check (has linked ET account)
    # Check player_links table
    if is_player_linked(member.id):
        return PermissionLevel.TRUSTED
    
    return PermissionLevel.PUBLIC

def requires_permission(level: PermissionLevel):
    """Decorator to enforce permission levels"""
    async def predicate(ctx):
        user_level = get_permission_level(ctx.author)
        
        if user_level.value < level.value:
            await ctx.send(
                f"❌ **Access Denied**\n"
                f"Required: `{level.name}`\n"
                f"Your level: `{user_level.name}`\n"
                f"Contact an administrator for access."
            )
            return False
        
        # Log admin command usage
        if level.value >= PermissionLevel.MODERATOR.value:
            logger.warning(
                f"🔐 {level.name} command used: "
                f"{ctx.command.name} by {ctx.author} ({ctx.author.id})"
            )
        
        return True
    
    return commands.check(predicate)
```

### Command Classification

```python
# PUBLIC (everyone can use)
@commands.command()
async def stats(self, ctx, player_name: str):
    """View player statistics - PUBLIC access"""
    ...

@commands.command()
async def lb(self, ctx, stat: str = "kills"):
    """View leaderboards - PUBLIC access"""
    ...

@commands.command()
async def last_session(self, ctx):
    """View last gaming session - PUBLIC access"""
    ...

# TRUSTED (linked players only)
@commands.command()
@requires_permission(PermissionLevel.TRUSTED)
async def unlink(self, ctx):
    """Unlink your ET account - TRUSTED access"""
    ...

# MODERATOR (session management)
@commands.command()
@requires_permission(PermissionLevel.MODERATOR)
async def set_teams(self, ctx, ...):
    """Manually assign teams - MODERATOR access"""
    ...

@commands.command()
@requires_permission(PermissionLevel.MODERATOR)
async def session_end(self, ctx):
    """Force end current session - MODERATOR access"""
    ...

# ADMIN (database operations)
@commands.command()
@requires_permission(PermissionLevel.ADMIN)
async def import(self, ctx, filename: str):
    """Import stats file - ADMIN access"""
    ...

@commands.command()
@requires_permission(PermissionLevel.ADMIN)
async def check_schema(self, ctx):
    """Verify database schema - ADMIN access"""
    ...

# OWNER (dangerous operations)
@commands.command()
@requires_permission(PermissionLevel.OWNER)
async def rebuild(self, ctx):
    """DANGER: Rebuild entire database - OWNER only"""
    await ctx.send("⚠️ **OWNER COMMAND** - This will wipe all data!")
    ...

@commands.command()
@requires_permission(PermissionLevel.OWNER)
async def shutdown(self, ctx):
    """Shutdown the bot - OWNER only"""
    await ctx.send("👋 Bot shutting down...")
    await self.bot.close()
```

### Audit Logging

```sql
-- Track all admin actions
CREATE TABLE admin_audit_log (
    id SERIAL PRIMARY KEY,
    discord_id TEXT NOT NULL,
    discord_name TEXT NOT NULL,
    command TEXT NOT NULL,
    arguments TEXT,
    permission_level TEXT,
    success BOOLEAN,
    error_message TEXT,
    ip_address TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_timestamp ON admin_audit_log(timestamp DESC);
CREATE INDEX idx_audit_user ON admin_audit_log(discord_id);
```

```python
async def log_admin_action(ctx, command: str, success: bool, error: str = None):
    """Log administrative actions"""
    query = """
        INSERT INTO admin_audit_log
        (discord_id, discord_name, command, arguments, permission_level, 
         success, error_message)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
    """
    
    level = get_permission_level(ctx.author)
    args = ' '.join(str(arg) for arg in ctx.args[2:])  # Skip self and ctx
    
    await bot.db_adapter.execute(query, (
        str(ctx.author.id),
        str(ctx.author),
        command,
        args,
        level.name,
        success,
        error
    ))
```

### Rate Limiting

```python
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    """Prevent command spam"""
    
    def __init__(self):
        self.cooldowns = defaultdict(dict)  # user_id -> {command -> last_use}
    
    def check_cooldown(self, user_id: int, command: str, cooldown_seconds: int) -> bool:
        """Check if user is on cooldown for command"""
        now = datetime.utcnow()
        
        if command in self.cooldowns[user_id]:
            last_use = self.cooldowns[user_id][command]
            time_passed = (now - last_use).total_seconds()
            
            if time_passed < cooldown_seconds:
                return False, cooldown_seconds - time_passed
        
        self.cooldowns[user_id][command] = now
        return True, 0

rate_limiter = RateLimiter()

def rate_limit(seconds: int):
    """Decorator for rate limiting"""
    async def predicate(ctx):
        allowed, remaining = rate_limiter.check_cooldown(
            ctx.author.id, 
            ctx.command.name, 
            seconds
        )
        
        if not allowed:
            await ctx.send(
                f"⏰ **Cooldown Active**\n"
                f"Wait {remaining:.0f} seconds before using `!{ctx.command.name}` again"
            )
            return False
        
        return True
    
    return commands.check(predicate)

# Usage
@commands.command()
@rate_limit(30)  # 30 second cooldown
async def stats(self, ctx, player_name: str):
    ...
```

### Voice Channel Substitution Tracking

```python
# In VoiceTracker class
async def on_voice_update(self, member, before, after):
    """Track substitutions during active gaming session"""
    
    if not self.bot.session_active:
        return
    
    # Detect team switches mid-game
    if before.channel and after.channel:
        # Check if switching between team channels
        team_a_id = int(os.getenv('TEAM_A_VOICE_CHANNEL'))
        team_b_id = int(os.getenv('TEAM_B_VOICE_CHANNEL'))
        
        if before.channel.id in [team_a_id, team_b_id] and \
           after.channel.id in [team_a_id, team_b_id] and \
           before.channel.id != after.channel.id:
            
            # SUBSTITUTION DETECTED!
            query = "SELECT player_guid FROM player_links WHERE discord_id = $1"
            result = await self.bot.db_adapter.fetch_one(query, (str(member.id),))
            
            if result:
                await self.log_substitution(
                    gaming_session_id=self.gaming_session_id,
                    player_guid=result[0],
                    from_team='A' if before.channel.id == team_a_id else 'B',
                    to_team='A' if after.channel.id == team_a_id else 'B',
                    timestamp=datetime.utcnow()
                )
                
                logger.warning(
                    f"🔄 SUBSTITUTION: {member.display_name} switched from "
                    f"Team {'A' if before.channel.id == team_a_id else 'B'} to "
                    f"Team {'A' if after.channel.id == team_a_id else 'B'}"
                )

async def log_substitution(self, gaming_session_id, player_guid, from_team, to_team, timestamp):
    """Log player substitution"""
    query = """
        INSERT INTO player_substitutions
        (gaming_session_id, player_guid, from_team, to_team, timestamp)
        VALUES ($1, $2, $3, $4, $5)
    """
    await self.bot.db_adapter.execute(query, (
        gaming_session_id, player_guid, from_team, to_team, timestamp
    ))
```

### Implementation Steps

1. **Create permissions system** (`bot/core/permissions.py`)
2. **Add role IDs to `.env`**
   ```bash
   OWNER_DISCORD_IDS=231165917604741121
   ADMIN_ROLE_ID=123456789
   MODERATOR_ROLE_ID=987654321
   ```
3. **Add audit log table** (migration)
4. **Decorate all commands** with appropriate permission levels
5. **Add rate limiting** to prevent spam
6. **Test permission denials**
7. **Review audit logs** regularly

### Benefits
- ✅ **Prevents Accidents** - Can't accidentally wipe DB
- ✅ **Abuse Prevention** - Rate limiting stops spam
- ✅ **Accountability** - Audit log tracks all admin actions
- ✅ **Granular Control** - Different access levels
- ✅ **Substitution Tracking** - Know when players switch teams mid-game

---

## PHASE 10: Additional Improvements

### 1. Automated Backups
```python
# Cron job: Daily backups
@tasks.loop(hours=24)
async def daily_backup():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f"backups/etlegacy_{timestamp}.dump"
    
    # PostgreSQL backup
    subprocess.run([
        'pg_dump',
        '-h', config.postgres_host,
        '-U', config.postgres_user,
        '-d', config.postgres_database,
        '-F', 'c',  # Custom format
        '-f', backup_file
    ])
    
    logger.info(f"✅ Daily backup created: {backup_file}")
    
    # Upload to cloud storage (optional)
    await upload_to_s3(backup_file)
```

### 2. Health Check Endpoint
```python
# Web endpoint for monitoring
from aiohttp import web

async def health_check(request):
    """Health check for monitoring"""
    status = {
        'bot_status': 'online' if bot.is_ready() else 'offline',
        'database': 'connected' if db.pool else 'disconnected',
        'sessions_active': bot.session_active,
        'voice_participants': len(bot.voice_tracker.active_sessions),
        'uptime_seconds': (datetime.now() - bot.bot_startup_time).total_seconds()
    }
    return web.json_response(status)

app = web.Application()
app.router.add_get('/health', health_check)
web.run_app(app, port=8080)
```

### 3. Player Notifications
```python
# DM players when they get achievements
async def notify_achievement(player_guid: str, achievement: str):
    """Notify player of new achievement"""
    query = "SELECT discord_id FROM player_links WHERE player_guid = $1"
    result = await db.fetch_one(query, (player_guid,))
    
    if result:
        user = await bot.fetch_user(int(result[0]))
        embed = discord.Embed(
            title="🏆 Achievement Unlocked!",
            description=f"**{achievement}**",
            color=0xFFD700
        )
        await user.send(embed=embed)
```

### 4. Match Result Predictions (ML)
```python
# Use historical data to predict match outcomes
from sklearn.ensemble import RandomForestClassifier

class MatchPredictor:
    def train(self, historical_sessions):
        """Train on past match data"""
        features = []
        outcomes = []
        
        for session in historical_sessions:
            # Features: team avg KD, accuracy, experience, etc.
            features.append(extract_features(session))
            outcomes.append(session['winner'])  # 0 or 1
        
        self.model = RandomForestClassifier()
        self.model.fit(features, outcomes)
    
    def predict_winner(self, team_a_players, team_b_players):
        """Predict which team will win"""
        features = extract_features_from_teams(team_a_players, team_b_players)
        probability = self.model.predict_proba([features])[0]
        
        return {
            'team_a_win_probability': probability[0],
            'team_b_win_probability': probability[1]
        }
```

---

## 📋 Implementation Checklist

### Phase 1: Voice Tracking
- [ ] Create `voice_sessions` table
- [ ] Implement `VoiceSessionManager` class
- [ ] Add voice state event handlers
- [ ] Build player linking system
- [ ] Test with 6+ player sessions

### Phase 2: Session Tracking
- [ ] Create `gaming_sessions` table with proper schema
- [ ] Link rounds to gaming sessions
- [ ] Add session start/end detection
- [ ] Implement voice participant tracking
- [ ] Build `!session_summary` command

### Phase 3: Redis Caching
- [ ] Install Redis on VPS
- [ ] Implement `RedisCache` wrapper
- [ ] Add cache warming on startup
- [ ] Migrate hot queries to Redis
- [ ] Monitor cache hit rates

### Phase 4: Leaderboard Optimization
- [ ] Create `leaderboard_cache` table
- [ ] Build leaderboard pre-computation task
- [ ] Implement incremental updates
- [ ] Add materialized view refresh
- [ ] Benchmark query improvements

### Phase 5: Database Indexing
- [ ] Analyze query execution plans
- [ ] Add composite indexes
- [ ] Create partial indexes for filters
- [ ] Test index impact on insert performance
- [ ] Document index strategy

### Phase 6: Async I/O Optimization
- [ ] Audit blocking operations
- [ ] Convert file I/O to async
- [ ] Implement parallel parsing
- [ ] Add connection pooling tuning
- [ ] Profile async performance

### Phase 7: Pagination System
- [ ] Design pagination API
- [ ] Create `PaginatedView` class
- [ ] Add page navigation buttons
- [ ] Implement search within pages
- [ ] Test with large datasets

### Phase 8: Advanced Analytics
- [ ] Build heatmap generation system
- [ ] Create match timeline visualizer
- [ ] Implement comparative dashboards
- [ ] Add trend analysis queries
- [ ] Design analytics cache strategy

### Phase 9: Security & Permissions
- [ ] Create `bot/core/permissions.py`
- [ ] Add Discord role IDs to `.env`
- [ ] Create `admin_audit_log` table
- [ ] Decorate all commands with permission checks
- [ ] Implement rate limiting system
- [ ] Add substitution tracking
- [ ] Test permission denials
- [ ] Review audit logs

### Phase 10: Additional Features
- [ ] Automated daily backups
- [ ] Health check endpoint
- [ ] Player achievement notifications
- [ ] Match result predictions (ML)

---
- [ ] Create `bot/core/voice_tracker.py`
- [ ] Add voice_activity table to schema
- [ ] Add migration for existing databases
- [ ] Integrate into `ultimate_bot.py`
- [ ] Create `bot/cogs/voice_stats_cog.py`
- [ ] Test voice join/leave tracking
- [ ] Test ET account linking
- [ ] Deploy to VPS

### Phase 2: Database Optimization
- [ ] Add composite indexes
- [ ] Add partial indexes
- [ ] Run ANALYZE on tables
- [ ] Test query performance
- [ ] Document improvements

### Phase 3: Connection Pooling
- [ ] Update pool settings in database_adapter.py
- [ ] Monitor connection usage
- [ ] Adjust based on load

### Phase 4: Metrics System
- [ ] Create `bot/core/metrics.py`
- [ ] Add metrics to commands
- [ ] Create admin metrics command
- [ ] Monitor performance
- [ ] Identify bottlenecks

### Phase 5: Redis Caching
- [ ] Install Redis on VPS
- [ ] Create `bot/core/redis_cache.py`
- [ ] Update StatsCache to use Redis
- [ ] Add cache decorators to cogs
- [ ] Test cache hit rates
- [ ] Monitor memory usage

### Phase 6: Event-Driven Processing
- [ ] Create `bot/core/stats_processor.py`
- [ ] Integrate with SSH monitoring
- [ ] Test worker pool
- [ ] Monitor queue sizes

### Phase 7: Materialized Views
- [ ] Create materialized views
- [ ] Create refresh script
- [ ] Set up cron job
- [ ] Update queries to use views

### Phase 8: Sharding (Future)
- [ ] Monitor server count
- [ ] Implement when approaching limit
- [ ] Test shard communication

---

## 🔧 Testing Strategy

### Voice Tracking
```python
# Test voice join/leave
# 1. Join gaming voice channel
# 2. Check logs for tracking
# 3. Leave channel
# 4. Query voice_activity table
# 5. Verify duration calculation

# Test ET linking
# 1. Link Discord to ET account
# 2. Join voice
# 3. Check et_guid and et_name populated
```

### Performance
```python
# Test caching
# 1. Run !stats command (cache miss)
# 2. Run !stats again (cache hit)
# 3. Check response time difference

# Test metrics
# 1. Run various commands
# 2. Use !metrics command
# 3. Verify tracking working
```

---

## 📊 Expected Results

### Voice Tracking
- Know exactly who played when
- Link Discord activity to game stats
- Track session attendance
- Identify inactive linked accounts

### Performance
- 50-80% faster repeated queries (Redis)
- Better handling of concurrent requests (pooling)
- Visibility into bottlenecks (metrics)
- Reduced database load (caching)

### Scalability
- Handle 100+ concurrent users
- Process multiple stat files simultaneously
- Support future growth to 1000+ users

---

## 🚨 Important Notes

1. **Backup Before Changes:** Always backup database before schema changes
2. **Test on Development:** Test each phase in dev environment first
3. **Monitor Resources:** Watch CPU/memory usage after each phase
4. **Incremental Rollout:** Deploy one phase at a time
5. **Rollback Plan:** Be prepared to revert changes if issues arise

---

## 📝 Change Log

**2025-11-09:** Initial roadmap created based on current bot state
- Voice detection working without database tracking
- PostgreSQL migration complete
- 14 active cogs
- Basic caching implemented

---

## 🎯 Success Metrics

Track these to measure improvement:

- **Response Time:** Average command latency < 500ms
- **Cache Hit Rate:** > 70% for repeated queries
- **Queue Size:** Stats processing queue < 10 items
- **Error Rate:** < 1% command failures
- **Memory Usage:** < 500MB per bot instance
- **Database Connections:** < 15 active connections

---

## 🔗 Related Documentation

- `docs/TECHNICAL_OVERVIEW.md` - System architecture
- `docs/DATA_PIPELINE.md` - Stats import flow
- `bot/core/database_adapter.py` - Database abstraction
- `postgresql_database_manager.py` - Schema management

---

**Remember:** Implement one phase at a time, test thoroughly, and monitor performance. The goal is steady improvement, not breaking changes! 🚀
