# 🎙️ SMART SESSION DETECTION SYSTEM
**Status**: 💡 Concept Design  
**Innovation**: Voice channel presence = automatic stats monitoring  
**Impact**: No manual commands, fully autonomous experience

---

## 🧠 THE BIG IDEA

### Current Problem:
```
❌ Bot monitors 24/7 (even when server is empty)
❌ Manual !monitor start/stop commands needed
❌ Stats posted when no one cares (3am, empty server)
❌ No way to know "who was in this session"
```

### Smart Solution:
```
✅ Bot watches Discord voice channels
✅ 6+ people join = "Oh, they're gathering to play!"
✅ Auto-enable gamestats monitoring
✅ Everyone leaves = "Session over!"
✅ Auto-disable monitoring + post session summary
✅ Track "who participated" from voice channel
```

---

## 🎯 DETECTION RULES

### Session Start Triggers:

**Option 1: Single Channel Threshold**
```
IF 6+ players in ANY voice channel
THEN start monitoring gamestats
```

**Option 2: Multi-Channel Detection**
```
IF (3+ in Channel A) AND (3+ in Channel B)
THEN start monitoring
REASON: Teams splitting for match
```

**Option 3: Smart Combined**
```
IF 6+ total across gaming voice channels
THEN start monitoring
```

### Session End Triggers:

```
IF voice channels < 2 players for 5 minutes
THEN stop monitoring
THEN post "Session Complete" summary
```

**Why 5 minute buffer?**
- Prevents false stops during quick restarts
- Allows bathroom breaks, snack runs
- Avoids premature session end

---

## 🏗️ SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────┐
│               Discord Voice Channels                    │
│  🎙️ ET:Legacy Team A     🎙️ ET:Legacy Team B          │
│  ├── vid                  ├── carniee                   │
│  ├── superboy             ├── c0rnp0rn3                 │
│  ├── olz                  ├── player5                   │
│  └── player6              └── (empty)                   │
│                                                          │
│  👥 Total: 6 players in voice                           │
└──────────────────────┬──────────────────────────────────┘
                       │ Voice State Update Event
                       ↓
┌─────────────────────────────────────────────────────────┐
│            Bot: Session Detection Logic                 │
│  🧠 Check: 6+ players in gaming channels?               │
│  ✅ YES → Start session monitoring                      │
│  📝 Track: [vid, superboy, olz, carniee, c0rnp0rn3,..] │
│  ⏰ Start time: 2025-10-04 20:15:00                     │
└──────────────────────┬──────────────────────────────────┘
                       │ Enable monitoring
                       ↓
┌─────────────────────────────────────────────────────────┐
│          SSH Monitor (endstats_monitor task)            │
│  🔄 Poll server every 30s                               │
│  📂 Check: /home/et/.etlegacy/legacy/gamestats/        │
│  🆕 Detect new files → Process → Post to Discord        │
│  ⏱️ Monitoring active...                                │
└──────────────────────┬──────────────────────────────────┘
                       │ 2 hours later...
                       ↓
┌─────────────────────────────────────────────────────────┐
│               Discord Voice Channels                    │
│  🎙️ ET:Legacy Team A     🎙️ ET:Legacy Team B          │
│  └── (empty)              └── (empty)                   │
│                                                          │
│  👥 Total: 0 players (everyone left)                    │
└──────────────────────┬──────────────────────────────────┘
                       │ Voice State Update (empty)
                       ↓
┌─────────────────────────────────────────────────────────┐
│            Bot: Session End Detection                   │
│  🧠 Check: < 2 players for 5+ minutes?                  │
│  ✅ YES → End session                                   │
│  ⏰ End time: 2025-10-04 22:43:00                       │
│  📊 Duration: 2h 28m                                    │
│  👥 Participants: vid, superboy, olz, carniee, c0rnp... │
└──────────────────────┬──────────────────────────────────┘
                       │ Post session summary
                       ↓
┌─────────────────────────────────────────────────────────┐
│            Discord: #stats Channel                      │
│  ╔═══════════════════════════════════════════════════╗  │
│  ║ 🏁 SESSION COMPLETE                               ║  │
│  ║ Duration: 2h 28m                                  ║  │
│  ║ Maps Played: erdenberg_t2, braundorf_b4, supply  ║  │
│  ║ Participants: @vid @superboy @olz @carniee +3    ║  │
│  ║                                                   ║  │
│  ║ 🏆 Session MVP: vid (5,432 DPM)                  ║  │
│  ║ 💀 Total Kills: 2,847                            ║  │
│  ║ ⏱️ Total Playtime: 14h 32m (combined)            ║  │
│  ╚═══════════════════════════════════════════════════╝  │
└─────────────────────────────────────────────────────────┘
```

---

## 💻 DISCORD API CAPABILITIES

### YES, Bots Can See Voice Channel Members!

```python
import discord
from discord.ext import commands

class VoiceMonitor(commands.Cog):
    """Monitor voice channel activity"""
    
    def __init__(self, bot):
        self.bot = bot
        self.gaming_channels = [
            123456789,  # ET:Legacy Team A
            987654321   # ET:Legacy Team B
        ]
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Triggered when ANYONE joins/leaves/moves voice channels"""
        
        # Check if it's a gaming channel
        channel = after.channel or before.channel
        if not channel or channel.id not in self.gaming_channels:
            return
        
        # Count total players in gaming channels
        total_players = 0
        participants = []
        
        for channel_id in self.gaming_channels:
            channel = self.bot.get_channel(channel_id)
            if channel and isinstance(channel, discord.VoiceChannel):
                total_players += len(channel.members)
                participants.extend([m.id for m in channel.members])
        
        print(f"👥 Voice update: {total_players} players in gaming channels")
        
        # Check session start
        if total_players >= 6 and not self.bot.session_active:
            await self.start_session(participants)
        
        # Check session end
        elif total_players < 2 and self.bot.session_active:
            await self.end_session(participants)
    
    async def start_session(self, participants):
        """Start a gaming session"""
        print(f"🎮 SESSION STARTED with {len(participants)} players")
        self.bot.session_active = True
        self.bot.session_start_time = discord.utils.utcnow()
        self.bot.session_participants = participants
        
        # Enable endstats monitoring
        self.bot.monitoring = True
        
        # Post to Discord
        channel = self.bot.get_channel(STATS_CHANNEL_ID)
        embed = discord.Embed(
            title="🎮 Gaming Session Started!",
            description=f"{len(participants)} players detected in voice",
            color=0x00FF00
        )
        await channel.send(embed=embed)
    
    async def end_session(self, participants):
        """End a gaming session"""
        # Wait 5 minutes to confirm everyone really left
        await asyncio.sleep(300)  # 5 min buffer
        
        # Re-check player count
        total_players = sum(
            len(self.bot.get_channel(cid).members)
            for cid in self.gaming_channels
        )
        
        if total_players >= 2:
            print("False alarm - players came back")
            return
        
        print(f"🏁 SESSION ENDED after 5min empty")
        
        # Calculate duration
        duration = discord.utils.utcnow() - self.bot.session_start_time
        
        # Disable monitoring
        self.bot.monitoring = False
        self.bot.session_active = False
        
        # Post session summary
        await self.post_session_summary(duration, self.bot.session_participants)
```

**Key Events:**
- `on_voice_state_update`: Fires when ANY user joins/leaves/moves
- `channel.members`: List of all users in a voice channel
- `len(channel.members)`: Count of users

---

## 📊 SESSION TRACKING DATABASE

### New Table: `gaming_sessions`

```sql
CREATE TABLE gaming_sessions (
    session_id INTEGER PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_seconds INTEGER,
    participant_count INTEGER,
    participants TEXT,  -- JSON array of user IDs
    maps_played TEXT,   -- JSON array of maps
    total_rounds INTEGER,
    status TEXT DEFAULT 'active',  -- 'active', 'ended'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### Track Participants:

```python
async def link_session_to_players(session_id, participant_ids):
    """Link gaming session to player records"""
    
    async with aiosqlite.connect(DB_PATH) as db:
        for user_id in participant_ids:
            # Find player by Discord ID (from aliases?)
            cursor = await db.execute('''
                SELECT player_id FROM players
                WHERE discord_id = ?
            ''', (user_id,))
            
            player = await cursor.fetchone()
            if player:
                # Link player to session
                await db.execute('''
                    INSERT INTO session_participants
                    (session_id, player_id, joined_voice_at)
                    VALUES (?, ?, ?)
                ''', (session_id, player[0], datetime.now().isoformat()))
        
        await db.commit()
```

---

## 🎯 SMART FEATURES

### 1. **Participant Tagging**

```python
# In session summary embed
participant_mentions = " ".join([f"<@{uid}>" for uid in participants[:10]])

embed.add_field(
    name="👥 Participants",
    value=participant_mentions or "Unknown players",
    inline=False
)
```

**Result**: @vid @superboy @olz @carniee @c0rnp0rn3 +5 more

---

### 2. **Smart Threshold Adjustment**

```python
# Learn from patterns
if hour_of_day >= 19 and hour_of_day <= 23:  # Prime time
    THRESHOLD = 6
elif day_of_week in [5, 6]:  # Weekend
    THRESHOLD = 8
else:
    THRESHOLD = 4
```

---

### 3. **Pre-Game Notification**

```python
if total_players >= 4 and not session_active:
    # Almost enough for a session!
    await channel.send(
        "🎮 4 players in voice - need 2 more to start monitoring!"
    )
```

---

### 4. **AFK Detection**

```python
# If someone is in voice but no gamestats for 30+ min
if last_player_stats_time > 30 minutes ago:
    # They're probably AFK
    participants.remove(player_id)
```

---

### 5. **Session Summary Stats**

```python
async def post_session_summary(duration, participants):
    """Post comprehensive session summary"""
    
    # Query all rounds during session
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT 
                COUNT(DISTINCT map_name) as maps_played,
                COUNT(*) as total_rounds,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                AVG(dpm) as avg_dpm
            FROM sessions s
            JOIN player_session_stats pss ON s.session_id = pss.session_id
            WHERE s.session_date >= ?
        ''', (session_start_time.isoformat(),))
        
        stats = await cursor.fetchone()
    
    embed = discord.Embed(
        title="🏁 Gaming Session Complete!",
        description=f"Duration: {format_duration(duration)}",
        color=0xFFD700
    )
    
    embed.add_field(
        name="📊 Session Stats",
        value=(
            f"**Maps Played**: {stats[0]}\n"
            f"**Total Rounds**: {stats[1]}\n"
            f"**Total Kills**: {stats[2]:,}\n"
            f"**Average DPM**: {stats[4]:.1f}"
        )
    )
    
    # MVP
    cursor = await db.execute('''
        SELECT player_name, SUM(dpm) as total_dpm
        FROM player_session_stats
        WHERE session_id IN (
            SELECT session_id FROM sessions
            WHERE session_date >= ?
        )
        GROUP BY player_name
        ORDER BY total_dpm DESC
        LIMIT 1
    ''', (session_start_time.isoformat(),))
    
    mvp = await cursor.fetchone()
    
    embed.add_field(
        name="🏆 Session MVP",
        value=f"**{mvp[0]}** - {mvp[1]:.1f} total DPM"
    )
    
    # Participants
    mentions = " ".join([f"<@{uid}>" for uid in participants])
    embed.add_field(
        name="👥 Participants",
        value=mentions,
        inline=False
    )
    
    await channel.send(embed=embed)
```

---

## 🔧 CONFIGURATION

### `.env` Settings:

```bash
# Voice channel monitoring
GAMING_VOICE_CHANNELS=123456789,987654321  # Comma-separated IDs
SESSION_START_THRESHOLD=6  # Min players to start
SESSION_END_THRESHOLD=2    # Min players to keep active
SESSION_END_DELAY=300      # Seconds to wait before ending (5 min)

# Stats posting
STATS_CHANNEL_ID=111222333444555
AUTO_POST_SUMMARIES=true
```

---

## 📋 IMPLEMENTATION PLAN

### Phase 1: Voice Monitoring (1 hour)
- [ ] Add `on_voice_state_update` listener
- [ ] Implement player counting logic
- [ ] Test with real voice channels
- [ ] Add logging for debugging

### Phase 2: Session Management (1 hour)
- [ ] Create `gaming_sessions` table
- [ ] Implement session start/end logic
- [ ] Add 5-minute end delay
- [ ] Track participant IDs

### Phase 3: Integration (1 hour)
- [ ] Connect to `endstats_monitor` task
- [ ] Enable/disable monitoring based on session
- [ ] Link sessions to player stats
- [ ] Test full flow

### Phase 4: Session Summaries (1 hour)
- [ ] Build session summary embed
- [ ] Query stats across multiple rounds
- [ ] Calculate MVPs and totals
- [ ] Add participant mentions

### Phase 5: Polish (30 min)
- [ ] Add pre-game notifications
- [ ] Implement smart thresholds
- [ ] Add error handling
- [ ] Test edge cases

**Total Time**: 4-5 hours

---

## 🎮 USER EXPERIENCE

### Scenario: Friday Night Gaming

**8:00 PM** - Players start joining voice
```
🎙️ ET:Legacy Team A: vid, superboy
🎙️ ET:Legacy Team B: carniee
```
*Bot: Watching... 3 players*

**8:15 PM** - More players join
```
🎙️ ET:Legacy Team A: vid, superboy, olz, player4
🎙️ ET:Legacy Team B: carniee, c0rnp0rn3, player7
```
*Bot: 7 players detected!*

```
╔════════════════════════════════════════╗
║ 🎮 Gaming Session Started!            ║
║ 7 players detected in voice channels  ║
║ Monitoring enabled automatically      ║
║ Good luck and have fun! 🔥            ║
╚════════════════════════════════════════╝
```

**8:20 PM** - First round ends
```
╔════════════════════════════════════════╗
║ 🎯 erdenberg_t2 - Round 1 Complete    ║
║ Axis: 3 | Allies: 2                   ║
║ Top: vid (543 DPM), superboy (498)    ║
╚════════════════════════════════════════╝
```

**8:35 PM** - Round 2 ends
```
╔════════════════════════════════════════╗
║ 🎯 erdenberg_t2 - Round 2 Complete    ║
║ ...                                    ║
╚════════════════════════════════════════╝

╔════════════════════════════════════════╗
║ 🏁 erdenberg_t2 - MAP COMPLETE        ║
║ Winner: Allies                         ║
║ MVP: vid (1,087 DPM combined)         ║
╚════════════════════════════════════════╝
```

**10:45 PM** - Everyone leaves voice
```
🎙️ ET:Legacy Team A: (empty)
🎙️ ET:Legacy Team B: (empty)
```
*Bot: 0 players... waiting 5 minutes to confirm*

**10:50 PM** - Session officially ends
```
╔═══════════════════════════════════════════════╗
║ 🏁 Gaming Session Complete!                  ║
║ Duration: 2h 35m                              ║
║                                               ║
║ 📊 Session Stats:                             ║
║ Maps Played: 4                                ║
║ Total Rounds: 8                               ║
║ Total Kills: 3,847                            ║
║ Average DPM: 412.5                            ║
║                                               ║
║ 🏆 Session MVP: vid - 5,432 total DPM        ║
║                                               ║
║ 👥 Participants:                              ║
║ @vid @superboy @olz @carniee @c0rnp0rn3 +2   ║
║                                               ║
║ Thanks for playing! GG! 🎮                   ║
╚═══════════════════════════════════════════════╝
```

---

## 🚀 ADVANTAGES

**For Players:**
- ✅ Zero manual commands needed
- ✅ Stats automatically posted
- ✅ Session summary when done
- ✅ Know who participated
- ✅ Seamless experience

**For Bot:**
- ✅ Only monitors when needed (saves resources)
- ✅ Clear session boundaries
- ✅ Better context for stats
- ✅ Can track "who played together"

**For Community:**
- ✅ Encourages voice channel use
- ✅ Creates "session records"
- ✅ Social proof ("look who played!")
- ✅ Historical session tracking

---

## ⚠️ EDGE CASES

### 1. Someone Stays in Voice After Session
```
Solution: 5-minute delay + re-check
If < 2 players for 5 min = session over
```

### 2. Split Sessions (Break in Middle)
```
Problem: Play 2h, break 30min, play 2h more
Solution: Session ends after 5min empty
         New session starts when 6+ return
```

### 3. Spectators in Voice
```
Problem: 10 in voice, but only 6 playing
Solution: Cross-reference with actual gamestats
         If player not in stats = spectator
```

### 4. Server Crash Mid-Session
```
Solution: Session stays active (voice still occupied)
         Monitoring continues when server returns
```

---

## 🎯 SUCCESS METRICS

- ✅ **Accuracy**: 95%+ session start/end detection
- ✅ **Latency**: Session start detected within 30 seconds
- ✅ **Reliability**: No false stops (5-min buffer works)
- ✅ **User Satisfaction**: Zero manual commands needed

---

**Status**: 💡 Design Complete - Ready for Implementation  
**Innovation Level**: 🚀🚀🚀 HIGH (fully autonomous!)  
**Estimated Dev Time**: 4-5 hours
