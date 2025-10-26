# 🤖 REAL-TIME STATS AUTOMATION SYSTEM
**Status**: 📋 Design Phase  
**Priority**: 🔥 HIGH - Major UX improvement  
**Goal**: Automatic Discord posting when rounds finish

---

## 💡 THE VISION

**Current Flow** (Manual):
```
1. Round finishes on server
2. GameStats file created: /home/et/.etlegacy/legacy/gamestats/2025-10-02-232818-erdenberg_t2-round-2.txt
3. ❌ File sits there until manual import
4. ❌ No one knows round ended
5. ❌ Manual: python tools/simple_bulk_import.py local_stats/*.txt
6. ❌ Manual: !last_session in Discord
```

**Automated Flow** (Goal):
```
1. Round finishes on server
2. GameStats file created: 2025-10-02-232818-erdenberg_t2-round-2.txt
3. ✅ Bot detects new file via SSH monitoring
4. ✅ Bot copies/processes file immediately
5. ✅ Bot posts to Discord automatically:
   - Round 1 → "Round 1 Summary"
   - Round 2 → "Round 2 Summary" + "Map Complete Summary"
6. ✅ Community sees results instantly
```

---

## 🎯 CORE REQUIREMENTS

### Must Have:
1. ✅ SSH connection to ET:Legacy server
2. ✅ Monitor `/home/et/.etlegacy/legacy/gamestats/` folder
3. ✅ Detect new `.txt` files (round finished)
4. ✅ Distinguish Round 1 vs Round 2 files
5. ✅ Process files in real-time OR copy for processing
6. ✅ Post Round 1 summary after Round 1
7. ✅ Post Round 2 + Map summary after Round 2
8. ✅ No duplicate processing
9. ✅ Handle errors gracefully

### Nice to Have:
- 📊 Real-time player count updates
- 🏆 Live DPM leaderboard during match
- 📈 Match progress indicator
- 🎮 Server status embed

---

## 🏗️ SYSTEM ARCHITECTURE

### Components:

```
┌─────────────────────────────────────────────────────────┐
│          ET:Legacy Game Server (puran.hehe.si)         │
│  /home/et/.etlegacy/legacy/gamestats/                  │
│  ├── 2025-10-02-232339-erdenberg_t2-round-1.txt ✅     │
│  └── 2025-10-02-232818-erdenberg_t2-round-2.txt ✅ NEW │
└──────────────────────┬──────────────────────────────────┘
                       │ SSH Monitor (30s poll)
                       ↓
┌─────────────────────────────────────────────────────────┐
│              Discord Bot (ultimate_bot.py)              │
│  Background Task: endstats_monitor()                   │
│  ├── SSH to server every 30 seconds                    │
│  ├── List files in gamestats/                          │
│  ├── Compare with known files                          │
│  └── Process new files                                  │
└──────────────────────┬──────────────────────────────────┘
                       │ New file detected
                       ↓
┌─────────────────────────────────────────────────────────┐
│                  Processing Pipeline                    │
│  1. Identify round number from filename                 │
│  2. Copy file OR process over SSH                       │
│  3. Parse with C0RNP0RN3StatsParser                    │
│  4. Insert into database                                │
│  5. Prepare Discord embeds                              │
│  6. Post to channel                                     │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 FILE NAMING PATTERN ANALYSIS

### Current Format:
```
YYYY-MM-DD-HHMMSS-<map_name>-round-<N>.txt

Examples:
2025-10-02-232339-erdenberg_t2-round-1.txt
2025-10-02-232818-erdenberg_t2-round-2.txt
2025-10-02-234400-braundorf_b4-round-1.txt
2025-10-02-234859-braundorf_b4-round-2.txt
```

### Detection Logic:
```python
import re

def parse_gamestats_filename(filename):
    """Parse gamestats filename to extract metadata"""
    # Pattern: YYYY-MM-DD-HHMMSS-<map>-round-<N>.txt
    pattern = r'(\d{4}-\d{2}-\d{2})-(\d{6})-(.+)-round-(\d+)\.txt'
    
    match = re.match(pattern, filename)
    if not match:
        return None
    
    date, time, map_name, round_num = match.groups()
    
    return {
        'date': date,
        'time': time,
        'map_name': map_name,
        'round_number': int(round_num),
        'filename': filename,
        'is_round_1': int(round_num) == 1,
        'is_round_2': int(round_num) == 2,
        'is_map_complete': int(round_num) == 2  # Round 2 = map done
    }

# Test
info = parse_gamestats_filename('2025-10-02-232818-erdenberg_t2-round-2.txt')
print(info)
# {
#   'date': '2025-10-02',
#   'time': '232818',
#   'map_name': 'erdenberg_t2',
#   'round_number': 2,
#   'is_round_1': False,
#   'is_round_2': True,
#   'is_map_complete': True
# }
```

---

## 🔌 SSH MONITORING

### Existing Infrastructure:
```python
# tools/ssh_sync_and_import.py already has SSH setup!
SSH_HOST = os.getenv('SSH_HOST', 'puran.hehe.si')
SSH_PORT = int(os.getenv('SSH_PORT', '48101'))
SSH_USER = os.getenv('SSH_USER', 'et')
SSH_KEY_PATH = os.path.expanduser(os.getenv('SSH_KEY_PATH', '~/.ssh/etlegacy_bot'))
REMOTE_PATH = '/home/et/.etlegacy/legacy/gamestats/'
```

### Bot Already Has Monitor Stub:
```python
# bot/ultimate_bot.py lines 3604-3614
@tasks.loop(seconds=30)
async def endstats_monitor(self):
    """🔄 Monitor for new EndStats files"""
    if not self.monitoring:
        return

    try:
        # SSH connection logic here
        pass  # ← WE NEED TO IMPLEMENT THIS!

    except Exception as e:
        logger.error(f"EndStats monitoring error: {e}")
```

**WE NEED TO**: Fill in the `pass` with actual logic!

---

## 🛠️ IMPLEMENTATION OPTIONS

### Option A: **Copy Files for Processing** (RECOMMENDED)

**Pros**:
- ✅ Simple and reliable
- ✅ Bot has full control over files
- ✅ Can retry parsing if needed
- ✅ Local file = faster processing
- ✅ Works even if SSH connection drops

**Cons**:
- ❌ Need to track processed files (avoid duplicates)
- ❌ Extra disk space (minimal)

**How it works**:
```python
async def endstats_monitor(self):
    """Monitor and copy new gamestats files"""
    
    # Connect via SSH
    ssh = paramiko.SSHClient()
    ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, key_filename=SSH_KEY_PATH)
    sftp = ssh.open_sftp()
    
    # List remote files
    remote_files = sftp.listdir(REMOTE_PATH)
    gamestats_files = [f for f in remote_files if f.endswith('.txt')]
    
    # Compare with processed files
    new_files = []
    async with aiosqlite.connect(DB_PATH) as db:
        for filename in gamestats_files:
            cursor = await db.execute('SELECT 1 FROM processed_files WHERE filename = ?', (filename,))
            if not await cursor.fetchone():
                new_files.append(filename)
    
    # Process new files
    for filename in new_files:
        # Copy to local
        local_path = f'local_stats/{filename}'
        sftp.get(f'{REMOTE_PATH}/{filename}', local_path)
        
        # Parse and process
        await process_gamestats_file(local_path, filename)
    
    sftp.close()
    ssh.close()
```

---

### Option B: **Process Over SSH Directly**

**Pros**:
- ✅ No local file storage needed
- ✅ Faster (no file copy)

**Cons**:
- ❌ More complex error handling
- ❌ Need to re-download if parsing fails
- ❌ SSH connection must stay open

**How it works**:
```python
async def endstats_monitor(self):
    """Monitor and process files over SSH"""
    
    ssh = paramiko.SSHClient()
    ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, key_filename=SSH_KEY_PATH)
    sftp = ssh.open_sftp()
    
    # List files
    remote_files = sftp.listdir(REMOTE_PATH)
    
    for filename in remote_files:
        if not filename.endswith('.txt'):
            continue
        
        # Check if processed
        if await is_file_processed(filename):
            continue
        
        # Read file content directly
        with sftp.open(f'{REMOTE_PATH}/{filename}', 'r') as f:
            content = f.read()
        
        # Parse content
        parser = C0RNP0RN3StatsParser()
        result = parser.parse_content(content)  # Need to add this method
        
        # Process result
        await process_parsed_stats(result, filename)
    
    sftp.close()
    ssh.close()
```

**RECOMMENDATION**: **Option A** (copy files) for reliability!

---

## 📊 PROCESSING PIPELINE

### Step-by-Step:

```python
async def process_gamestats_file(filepath, filename):
    """Process a single gamestats file"""
    
    # 1. Parse filename
    file_info = parse_gamestats_filename(filename)
    if not file_info:
        logger.error(f"Invalid filename format: {filename}")
        return
    
    logger.info(f"📄 Processing {filename}")
    logger.info(f"   Map: {file_info['map_name']}")
    logger.info(f"   Round: {file_info['round_number']}")
    logger.info(f"   Complete: {file_info['is_map_complete']}")
    
    # 2. Parse file content
    parser = C0RNP0RN3StatsParser()
    result = parser.parse_file(filepath)
    
    if not result or 'error' in result:
        logger.error(f"Parse failed: {filename}")
        return
    
    # 3. Insert into database
    async with aiosqlite.connect(DB_PATH) as db:
        # Insert session
        cursor = await db.execute('''
            INSERT INTO sessions (
                session_date, map_name, round_number,
                time_limit, actual_time
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            result['timestamp'],
            result['map'],
            result['round'],
            result.get('time_limit', '0:00'),
            result.get('actual_time', '0:00')
        ))
        
        session_id = cursor.lastrowid
        
        # Insert player stats (bulk)
        # ... (existing import logic)
        
        # Mark as processed
        await db.execute('''
            INSERT INTO processed_files (filename, processed_at)
            VALUES (?, ?)
        ''', (filename, datetime.now().isoformat()))
        
        await db.commit()
    
    # 4. Post to Discord
    await post_round_summary(session_id, file_info)
```

---

## 📢 DISCORD POSTING LOGIC

### Round Detection:

```python
async def post_round_summary(session_id, file_info):
    """Post round summary to Discord"""
    
    channel = bot.get_channel(STATS_CHANNEL_ID)
    if not channel:
        logger.error("Stats channel not found!")
        return
    
    if file_info['is_round_1']:
        # Round 1 only
        await post_round_1_summary(channel, session_id, file_info)
    
    elif file_info['is_round_2']:
        # Round 2 + Map Complete
        await post_round_2_summary(channel, session_id, file_info)
        await post_map_complete_summary(channel, file_info)
```

---

### Round 1 Summary:

```python
async def post_round_1_summary(channel, session_id, file_info):
    """Post Round 1 summary"""
    
    # Get stats from database
    stats = await get_round_stats(session_id)
    
    embed = discord.Embed(
        title=f"🎮 {file_info['map_name']} - Round 1 Complete",
        description=f"Match started at {file_info['time']}",
        color=0x00FF00,
        timestamp=datetime.now()
    )
    
    # Add team scores
    embed.add_field(
        name="⚔️ Team Scores",
        value=f"**Axis**: {stats['axis_score']}\\n**Allies**: {stats['allies_score']}",
        inline=True
    )
    
    # Add top players
    top_players = await get_top_players(session_id, limit=3)
    player_list = "\\n".join([
        f"{i+1}. **{p['name']}** - {p['kills']}K/{p['deaths']}D ({p['dpm']:.1f} DPM)"
        for i, p in enumerate(top_players)
    ])
    
    embed.add_field(
        name="🏆 Top Performers",
        value=player_list,
        inline=False
    )
    
    embed.set_footer(text="Round 2 starting soon...")
    
    await channel.send(embed=embed)
    logger.info(f"✅ Posted Round 1 summary for {file_info['map_name']}")
```

---

### Round 2 + Map Summary:

```python
async def post_round_2_summary(channel, session_id, file_info):
    """Post Round 2 summary"""
    
    stats = await get_round_stats(session_id)
    
    embed = discord.Embed(
        title=f"🎮 {file_info['map_name']} - Round 2 Complete",
        description="Final round finished!",
        color=0x0099FF,
        timestamp=datetime.now()
    )
    
    # Similar to Round 1...
    
    await channel.send(embed=embed)
    logger.info(f"✅ Posted Round 2 summary for {file_info['map_name']}")


async def post_map_complete_summary(channel, file_info):
    """Post full map summary (both rounds combined)"""
    
    # Get both rounds for this map
    map_name = file_info['map_name']
    date = file_info['date']
    
    # Find both round sessions
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT session_id FROM sessions
            WHERE map_name = ? AND session_date LIKE ?
            ORDER BY round_number
        ''', (map_name, f'{date}%'))
        
        sessions = await cursor.fetchall()
    
    if len(sessions) < 2:
        logger.warning("Can't create map summary - missing rounds")
        return
    
    # Aggregate stats from both rounds
    combined_stats = await get_combined_round_stats(sessions)
    
    embed = discord.Embed(
        title=f"🏁 {map_name} - MAP COMPLETE",
        description=f"Both rounds finished on {date}",
        color=0xFFD700,  # Gold
        timestamp=datetime.now()
    )
    
    # Winner
    embed.add_field(
        name="🏆 Winner",
        value=f"**{combined_stats['winner']}** wins!",
        inline=False
    )
    
    # Combined team stats
    embed.add_field(
        name="📊 Combined Stats",
        value=(
            f"**Total Kills**: {combined_stats['total_kills']:,}\\n"
            f"**Total Deaths**: {combined_stats['total_deaths']:,}\\n"
            f"**Average DPM**: {combined_stats['avg_dpm']:.1f}"
        ),
        inline=True
    )
    
    # MVP
    mvp = combined_stats['mvp']
    embed.add_field(
        name="👑 Map MVP",
        value=(
            f"**{mvp['name']}**\\n"
            f"{mvp['kills']}K/{mvp['deaths']}D\\n"
            f"{mvp['dpm']:.1f} DPM"
        ),
        inline=True
    )
    
    embed.set_footer(text="GG! Next map loading...")
    
    # Add image if available
    # embed.set_image(url=f"attachment://map_summary_{map_name}.png")
    
    await channel.send(embed=embed)
    logger.info(f"✅ Posted MAP COMPLETE summary for {map_name}")
```

---

## 🔧 ERROR HANDLING

### Must Handle:

1. **SSH Connection Fails**
   ```python
   try:
       ssh.connect(...)
   except paramiko.AuthenticationException:
       logger.error("SSH auth failed - check key")
       return
   except TimeoutError:
       logger.error("SSH timeout - server down?")
       return
   ```

2. **File Parse Fails**
   ```python
   result = parser.parse_file(filepath)
   if not result or 'error' in result:
       # Don't mark as processed - retry next time
       logger.error(f"Parse failed: {filename}")
       return
   ```

3. **Database Error**
   ```python
   try:
       await db.execute(...)
   except sqlite3.IntegrityError as e:
       # Duplicate? Already processed?
       logger.warning(f"DB error: {e}")
       # Still mark as processed to avoid infinite retry
   ```

4. **Discord Posting Fails**
   ```python
   try:
       await channel.send(embed=embed)
   except discord.Forbidden:
       logger.error("Bot lacks permission to post")
   except discord.HTTPException as e:
       logger.error(f"Discord API error: {e}")
   ```

5. **Partial Round Detection**
   ```python
   # What if Round 1 file is missing?
   if file_info['is_round_2']:
       # Check if Round 1 exists
       round_1_exists = await check_round_1_processed(map_name, date)
       if not round_1_exists:
           logger.warning("Round 2 detected but Round 1 missing!")
           # Post Round 2 anyway? Or skip map summary?
   ```

---

## 📋 IMPLEMENTATION CHECKLIST

### Phase 1: Setup (30 min)
- [ ] Update `.env` with SSH credentials
- [ ] Test SSH connection manually
- [ ] Verify SSH key works
- [ ] Test `sftp.listdir(REMOTE_PATH)`

### Phase 2: File Detection (1 hour)
- [ ] Implement `parse_gamestats_filename()`
- [ ] Add `processed_files` tracking
- [ ] Test file listing and comparison
- [ ] Handle edge cases (invalid filenames)

### Phase 3: Processing (1 hour)
- [ ] Implement `process_gamestats_file()`
- [ ] Integrate with existing parser
- [ ] Test database insertion
- [ ] Mark files as processed

### Phase 4: Discord Integration (1 hour)
- [ ] Implement `post_round_1_summary()`
- [ ] Implement `post_round_2_summary()`
- [ ] Implement `post_map_complete_summary()`
- [ ] Add channel ID to `.env`

### Phase 5: Bot Integration (30 min)
- [ ] Fill in `endstats_monitor()` task
- [ ] Add enable/disable flag (`self.monitoring`)
- [ ] Add `!monitor start/stop` commands
- [ ] Test in production

### Phase 6: Testing (1 hour)
- [ ] Test with real server files
- [ ] Verify Round 1 detection
- [ ] Verify Round 2 + map summary
- [ ] Test error scenarios
- [ ] Monitor for 24 hours

**Total Estimated Time**: 5-6 hours

---

## 🎯 SUCCESS METRICS

- ✅ **Latency**: Round summaries posted within 60 seconds of file creation
- ✅ **Accuracy**: 100% of rounds detected correctly
- ✅ **Reliability**: No duplicate posts, no missed rounds
- ✅ **Uptime**: Monitoring runs 24/7 without crashes
- ✅ **User Feedback**: Community finds summaries useful

---

## 🔮 FUTURE ENHANCEMENTS

### Phase 2 Ideas:
1. **Live Match Updates**
   - Monitor `/path/to/live/stats` (if server provides)
   - Post DPM leaderboard every 5 minutes during match
   - "Match in progress" embed with player count

2. **Match Predictions**
   - Analyze Round 1 stats
   - Predict Round 2 winner
   - Show prediction accuracy over time

3. **Player Notifications**
   - @mention players who reached milestones
   - "🏆 @vid just reached 100 kills this session!"
   - "🎯 @carniee has 50% accuracy this round!"

4. **Interactive Stats**
   - React with 📊 to see detailed stats
   - React with 🏆 to see your personal performance
   - React with 📸 to generate match image

5. **Voice Channel Integration**
   - Update voice channel name: "🎮 12/32 players on supply"
   - Move bot to voice channel when match starts
   - Play sound effects for MVPs

---

**Status**: 📋 Design Complete - Ready for Implementation  
**Next Step**: Implement Phase 1 (SSH Setup + File Detection)  
**Estimated Dev Time**: 5-6 hours total
