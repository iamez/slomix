# 🎮 ET:Legacy Stats Bot - Next Generation
### **Fully Autonomous Gaming Session Tracking**

> **From**: Your friend who codes  
> **Status**: Revolutionary automation incoming  
> **TL;DR**: Bot watches voice channels, auto-posts stats when you play, no commands needed!

---

## 🌟 What We're Building

Imagine this: You and your squad hop into Discord voice, start playing ET:Legacy, and **magically**:

- ✨ Bot detects you're gaming (6+ people in voice)
- 🤖 Automatically starts monitoring the game server
- 📊 Posts round summaries after each round
- 🏁 Posts full session summary when everyone leaves
- 🎯 **Zero commands needed - completely automatic!**

---

## 📸 Visual Journey

### **BEFORE** (Current Manual System)
```
┌─────────────────────────────────────┐
│  😴 Bot sleeping (not monitoring)   │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│  🎮 You play ET:Legacy for 2 hours │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│  📁 Files pile up on server         │
│  (no one knows)                     │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│  ❌ Manual: !monitor start          │
│  ❌ Manual: python import.py        │
│  ❌ Manual: !last_session           │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│  😑 "Ugh, too much work"            │
│  Stats never get posted...          │
└─────────────────────────────────────┘
```

### **AFTER** (New Autonomous System)
```
┌─────────────────────────────────────┐
│  🎙️ 6 people join Discord voice    │
│  (vid, superboy, olz, carniee, ...) │
└─────────────────────────────────────┘
           ↓ (Bot detects!)
┌─────────────────────────────────────┐
│  🤖 Bot: "Gaming session started!"  │
│  📊 Auto-enables monitoring         │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│  🎮 You play ET:Legacy              │
│  (Round 1 finishes on erdenberg)    │
└─────────────────────────────────────┘
           ↓ (30 seconds later)
┌─────────────────────────────────────┐
│  💬 Discord: "Round 1 Complete!"    │
│  📊 Top player: vid (543 DPM)       │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│  🎮 Round 2 finishes                │
└─────────────────────────────────────┘
           ↓ (30 seconds later)
┌─────────────────────────────────────┐
│  💬 "Round 2 + MAP COMPLETE!"       │
│  🏆 Map MVP: vid (1,087 DPM)        │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│  🎮 2 hours of gaming...            │
│  (4 maps, 8 rounds total)           │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│  👋 Everyone leaves voice channel   │
└─────────────────────────────────────┘
           ↓ (5 min later)
┌─────────────────────────────────────┐
│  🏁 "Session Complete!"             │
│  📊 Duration: 2h 35m                │
│  🏆 MVP: vid (5,432 total DPM)      │
│  👥 @vid @superboy @olz +4 played   │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│  😎 "That was automatic and smooth" │
│  ✨ No commands needed!             │
└─────────────────────────────────────┘
```

---

## 🎬 Real Example Session

### 8:00 PM - Voice Channel Activity

```
🎙️ ET:Legacy Team A          🎙️ ET:Legacy Team B
├── 🟢 vid                    ├── 🟢 carniee
├── 🟢 superboy               ├── 🟢 c0rnp0rn3
├── 🟢 olz                    ├── 🟢 player5
└── 🟢 player6                └── (empty)

👥 Total: 6 players → SESSION STARTS! 🎮
```

**Bot automatically posts:**
```
╔════════════════════════════════════╗
║  🎮 Gaming Session Started!       ║
║                                    ║
║  6 players detected in voice      ║
║  Monitoring enabled automatically ║
║                                    ║
║  Good luck and have fun! 🔥       ║
╚════════════════════════════════════╝
```

---

### 8:15 PM - First Round Ends

**Server creates file:** `2025-10-04-201523-erdenberg_t2-round-1.txt`

**Bot detects new file within 30 seconds and posts:**
```
╔═════════════════════════════════════════════╗
║  🎯 erdenberg_t2 - Round 1 Complete        ║
║  Match started at 20:15                     ║
║                                             ║
║  ⚔️ Team Scores                             ║
║  Axis: 3 | Allies: 2                        ║
║                                             ║
║  🏆 Top Performers                          ║
║  1. vid - 15K/8D (543 DPM) 🔥              ║
║  2. superboy - 12K/9D (498 DPM)            ║
║  3. carniee - 11K/7D (456 DPM)             ║
║                                             ║
║  Round 2 starting soon...                   ║
╚═════════════════════════════════════════════╝
```

---

### 8:28 PM - Round 2 Ends + Map Complete

**Server creates:** `2025-10-04-202847-erdenberg_t2-round-2.txt`

**Bot posts TWO embeds:**

**Embed 1: Round 2**
```
╔═════════════════════════════════════════════╗
║  🎯 erdenberg_t2 - Round 2 Complete        ║
║  Final round finished!                      ║
║                                             ║
║  ⚔️ Team Scores                             ║
║  Axis: 2 | Allies: 3                        ║
║                                             ║
║  🏆 Top Performers                          ║
║  1. vid - 18K/11D (587 DPM)                ║
║  2. olz - 14K/9D (521 DPM)                 ║
║  3. carniee - 13K/10D (489 DPM)            ║
╚═════════════════════════════════════════════╝
```

**Embed 2: Map Summary** (Both rounds combined!)
```
╔═════════════════════════════════════════════╗
║  🏁 erdenberg_t2 - MAP COMPLETE            ║
║  Both rounds finished on 2025-10-04         ║
║                                             ║
║  🏆 Winner: Allies wins!                    ║
║                                             ║
║  📊 Combined Stats                          ║
║  Total Kills: 347                           ║
║  Total Deaths: 298                          ║
║  Average DPM: 487.3                         ║
║                                             ║
║  👑 Map MVP                                 ║
║  vid                                        ║
║  33K/19D                                    ║
║  1,130 DPM (both rounds)                    ║
║                                             ║
║  GG! Next map loading... 🎮                ║
╚═════════════════════════════════════════════╝
```

---

### 10:45 PM - Session Ends

Everyone leaves voice channel:
```
🎙️ ET:Legacy Team A          🎙️ ET:Legacy Team B
└── (empty)                   └── (empty)

👥 Total: 0 players
⏰ Waiting 5 minutes to confirm...
```

**10:50 PM - Official Session End**

**Bot posts final summary:**
```
╔════════════════════════════════════════════════╗
║  🏁 Gaming Session Complete!                  ║
║  Duration: 2 hours 35 minutes                 ║
║                                                ║
║  📊 Session Stats                              ║
║  Maps Played: 4                                ║
║  • erdenberg_t2                                ║
║  • braundorf_b4                                ║
║  • supply                                      ║
║  • goldrush                                    ║
║                                                ║
║  Total Rounds: 8                               ║
║  Total Kills: 3,847                            ║
║  Total Deaths: 3,291                           ║
║  Average DPM: 412.5                            ║
║                                                ║
║  🏆 Session MVP: vid                           ║
║  Total DPM: 5,432 (crushing it! 🔥)           ║
║                                                ║
║  👥 Participants                               ║
║  @vid @superboy @olz @carniee @c0rnp0rn3      ║
║  @player5 @player6                             ║
║                                                ║
║  Thanks for playing! GG! 🎮                   ║
╚════════════════════════════════════════════════╝
```

---

## 🧠 How It Works (The Magic)

### **Step 1: Voice Channel Monitoring**

```python
# Bot constantly watches Discord voice channels
@bot.event
async def on_voice_state_update(member, before, after):
    # Someone joined/left a voice channel!
    
    # Count players in gaming channels
    total_players = count_players_in_gaming_channels()
    
    if total_players >= 6:
        # Enough players! START SESSION!
        await start_gaming_session()
    
    elif total_players < 2:
        # Almost empty... END SESSION!
        await end_gaming_session()
```

**Triggers:**
- ✅ 6+ players in voice = Auto-start monitoring
- ✅ < 2 players for 5 min = Auto-stop monitoring

---

### **Step 2: SSH Server Monitoring**

```python
# Bot connects to game server via SSH every 30 seconds
@tasks.loop(seconds=30)
async def endstats_monitor():
    if not bot.session_active:
        return  # No active session, skip monitoring
    
    # Connect to server
    ssh.connect('puran.hehe.si', port=48101, user='et')
    
    # List files in gamestats folder
    files = sftp.listdir('/home/et/.etlegacy/legacy/gamestats/')
    
    # Check for new files
    for file in files:
        if file not in processed_files:
            # NEW FILE! Process it!
            await process_new_round(file)
```

**What it checks:**
- 📂 Server folder: `/home/et/.etlegacy/legacy/gamestats/`
- 🆕 New files = new rounds finished
- ⏱️ Checks every 30 seconds (fast!)

---

### **Step 3: Smart Round Detection**

```python
# Analyze filename to determine round type
def parse_filename(filename):
    # Example: "2025-10-04-201523-erdenberg_t2-round-1.txt"
    
    match = re.match(r'(\d{4}-\d{2}-\d{2})-(\d{6})-(.+)-round-(\d+)\.txt', filename)
    
    return {
        'date': '2025-10-04',
        'time': '201523',
        'map': 'erdenberg_t2',
        'round': 1  # or 2
    }

# Different posts for Round 1 vs Round 2
if round == 1:
    post_round_1_summary()  # Just round stats

elif round == 2:
    post_round_2_summary()  # Round stats
    post_map_complete_summary()  # + Combined map stats!
```

---

### **Step 4: Discord Integration**

```python
# Post beautiful embeds to Discord
async def post_round_summary(round_data):
    embed = discord.Embed(
        title=f"🎯 {round_data['map']} - Round {round_data['round']} Complete",
        color=0x00FF00
    )
    
    embed.add_field(
        name="🏆 Top Performers",
        value="1. vid - 15K/8D (543 DPM)\n2. superboy - 12K/9D (498 DPM)"
    )
    
    await channel.send(embed=embed)
```

---

## 🎯 Key Features

### ✨ **Fully Automatic**
- No `!monitor start` commands
- No manual imports
- No `!last_session` needed
- **Just play and it works!**

### 🎙️ **Voice Channel Detection**
- Bot watches who's in voice
- 6+ players = session starts
- Everyone leaves = session ends
- **Knows who participated!**

### ⚡ **Real-Time Stats**
- Round ends → Stats posted in 30 seconds
- No waiting for manual imports
- Immediate feedback after each round

### 🏆 **Smart Summaries**
- Round 1 = Round summary only
- Round 2 = Round + Map summary
- Session end = Full session summary
- **Context-aware posting!**

### 👥 **Participant Tracking**
- Bot knows who was in voice
- Tags participants in summaries
- Links voice presence to player stats
- **Social proof: "We played together!"**

---

## 📊 Technical Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Discord Voice Channels              │
│  🎙️ 6+ players detected                             │
└────────────────────┬─────────────────────────────────┘
                     │ on_voice_state_update event
                     ↓
┌──────────────────────────────────────────────────────┐
│              Bot: Session Manager                    │
│  • Start monitoring when 6+ players                  │
│  • Stop monitoring when < 2 players                  │
│  • Track participants and duration                   │
└────────────────────┬─────────────────────────────────┘
                     │ Enable monitoring flag
                     ↓
┌──────────────────────────────────────────────────────┐
│          Bot: SSH Monitor (every 30s)                │
│  • Connect to game server                            │
│  • List files in gamestats/                          │
│  • Detect new files                                  │
│  • Copy & process new rounds                         │
└────────────────────┬─────────────────────────────────┘
                     │ New file detected
                     ↓
┌──────────────────────────────────────────────────────┐
│             Bot: Stats Processor                     │
│  • Parse filename (map, round, time)                 │
│  • Parse file content (kills, deaths, DPM)           │
│  • Insert into database                              │
│  • Prepare Discord embeds                            │
└────────────────────┬─────────────────────────────────┘
                     │ Stats ready
                     ↓
┌──────────────────────────────────────────────────────┐
│          Discord: #stats Channel                     │
│  📊 "Round 1 Complete!"                              │
│  📊 "Round 2 + Map Complete!"                        │
│  🏁 "Session Complete!" (when voice empties)         │
└──────────────────────────────────────────────────────┘
```

---

## 🚀 Benefits

### For You and Your Squad:
- ✅ **Zero effort** - No commands to remember
- ✅ **Instant gratification** - See stats right after rounds
- ✅ **Social proof** - Everyone tagged in summaries
- ✅ **Session history** - Full record of gaming nights
- ✅ **Competitive fun** - Compare performance immediately

### For the Bot:
- ✅ **Smart resource usage** - Only monitors during sessions
- ✅ **Clear boundaries** - Knows when sessions start/end
- ✅ **Better data** - Links voice presence to game stats
- ✅ **Autonomous operation** - Works without human intervention

---

## 🎮 Example Gaming Night

### **Timeline:**

| Time  | Event | Bot Action |
|-------|-------|------------|
| 8:00 PM | 6 people join voice | 🤖 "Session started!" + enable monitoring |
| 8:15 PM | Round 1 ends (erdenberg) | 📊 Post Round 1 summary |
| 8:28 PM | Round 2 ends (erdenberg) | 📊 Post Round 2 + Map summary |
| 8:45 PM | Round 1 ends (braundorf) | 📊 Post Round 1 summary |
| 9:02 PM | Round 2 ends (braundorf) | 📊 Post Round 2 + Map summary |
| 9:20 PM | Round 1 ends (supply) | 📊 Post Round 1 summary |
| 9:35 PM | Round 2 ends (supply) | 📊 Post Round 2 + Map summary |
| 9:50 PM | Round 1 ends (goldrush) | 📊 Post Round 1 summary |
| 10:08 PM | Round 2 ends (goldrush) | 📊 Post Round 2 + Map summary |
| 10:45 PM | Everyone leaves voice | ⏳ Wait 5 min to confirm... |
| 10:50 PM | Still empty | 🏁 "Session Complete!" + full summary |

**Result:**
- 8 automatic round posts
- 4 automatic map summaries
- 1 automatic session summary
- **15 total Discord posts - ZERO manual commands!**

---

## 💡 Why This Is Genius

### **The Problem We're Solving:**

Most stat tracking systems require manual work:
- ❌ Manual commands to start/stop
- ❌ Manual imports of data
- ❌ Manual requests for stats
- ❌ Players forget or are too lazy

**Result:** Stats never get posted, data gets lost, no one sees their performance

### **Our Solution:**

Use voice channel presence as a proxy for "gaming session":
- ✅ 6+ in voice = They're probably playing
- ✅ Voice empty = Session over
- ✅ Automate everything in between
- ✅ Zero human intervention needed

**Result:** Stats always posted, immediate feedback, seamless UX, community engagement!

---

## 🎯 Development Status

### ✅ **Completed:**
- Alias linking system (48 players tracked)
- Player stats database (12,414 records)
- Stats parser (handles all ET:Legacy formats)
- Discord bot foundation (commands, embeds)
- SSH infrastructure (server connection working)

### 📋 **In Design:** (You are here!)
- Automation system architecture
- Voice channel detection logic
- Smart session management
- Autonomous monitoring

### 🚧 **Next Steps:**
1. Implement voice channel monitoring (1 hour)
2. Build session start/end logic (1 hour)
3. Connect to SSH monitoring system (1 hour)
4. Create session summary embeds (1 hour)
5. Test with real gaming sessions (1 hour)

**Total dev time: 5-6 hours**

---

## 🏆 The End Vision

Imagine a future where:
- 🎙️ You hop in Discord voice with friends
- 🤖 Bot: "Gaming session started!"
- 🎮 You play ET:Legacy for hours
- 📊 Stats automatically posted after every round
- 👥 Everyone sees their performance instantly
- 🏁 Session ends, full summary posted with everyone tagged
- 😎 **You did NOTHING manually - it just worked**

**That's the future we're building!**

---

## 📞 Questions?

Ask your coding friend anything:
- "How does voice detection work?"
- "What if someone stays AFK in voice?"
- "Can we set custom thresholds?"
- "What about spectators?"
- "How accurate is the detection?"

**We've thought of everything!** 🧠

---

<p align="center">
  <strong>Built with ❤️ for the ET:Legacy community</strong><br>
  <em>Making stats tracking effortless and automatic</em>
</p>

---

## 🎨 Bonus: ASCII Art Preview

```
         _____  _____   _                                    
        | ____||_   _| | |     ___   __ _   __ _   ___  _   _ 
        |  _|    | |   | |    / _ \ / _` | / _` | / __|| | | |
        | |___   | |   | |___|  __/| (_| || (_| || (__ | |_| |
        |_____|  |_|   |_____|\___| \__, | \__,_| \___| \__, |
                                    |___/                |___/ 
         ____   _           _           ____          _   
        / ___| | |_   __ _ | |_  ___   | __ )   ___  | |_ 
        \___ \ | __| / _` || __|/ __|  |  _ \  / _ \ | __|
         ___) || |_ | (_| || |_ \__ \  | |_) || (_) || |_ 
        |____/  \__| \__,_| \__||___/  |____/  \___/  \__|
                                                           
        🤖 Now with 100% more automation! 🎮
```

---

**Ready to make your gaming stats effortless?** Let's build this! 🚀
