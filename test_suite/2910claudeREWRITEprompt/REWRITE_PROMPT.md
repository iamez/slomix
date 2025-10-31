# 🚀 ET:Legacy Discord Bot - Clean Rewrite Request

## Project Overview

I need a clean rewrite of my ET:Legacy game stats Discord bot. The current bot works but has accumulated technical debt from months of iterative fixes and needs a professional rebuild with proper architecture.

**GitHub Repository:** [YOUR_GITHUB_URL_HERE]

**Current Bot File:** ultimate_bot_FINAL.py (in outputs folder or your repo)

## What The Bot Does

The bot monitors ET:Legacy game servers and provides Discord integration for:
- 📊 Player statistics tracking and leaderboards
- 🔗 Discord account linking to in-game profiles
- 🎮 Session management and monitoring
- 📥 Automatic stats file download via SSH
- 🏆 Real-time game summaries and round results

## Current Problems (Why Rewrite Is Needed)

1. **Code Quality Issues:**
   - Duplicated code in header (lines 1-36 are copy/paste artifacts)
   - Accumulated technical debt from many iterations
   - Inconsistent code structure and patterns
   - Poor separation of concerns

2. **Recent Bug Fixes Applied (Patches on Patches):**
   - Fixed alias tracking (player_aliases table wasn't being updated)
   - Fixed !stats command (couldn't find players by name)
   - Fixed !link command (couldn't search/link accounts)
   - Added !list_guids command (admin helper for linking)

3. **Architecture Concerns:**
   - Not following proper Cog pattern consistently
   - Database queries could be optimized
   - Error handling is inconsistent
   - Logging could be better structured

## Critical Fixes That MUST Be Included

### Fix #1: Automatic Alias Tracking ⭐ MOST IMPORTANT
**Problem:** The bot was processing stats but NOT updating the `player_aliases` table, causing !stats and !link to fail.

**Solution Required:**
```python
# In the stats processing function, after inserting to player_comprehensive_stats:
async def _insert_player_stats(self, db, session_id, date, stats, player):
    # ... insert to player_comprehensive_stats ...
    
    # ⭐ CRITICAL: Update player aliases for !stats and !link
    await self._update_player_alias(
        db,
        player.get('guid'),
        player.get('name'),
        date
    )

async def _update_player_alias(self, db, guid, alias, last_seen_date):
    """
    Track player aliases for !stats and !link commands.
    This is CRITICAL for these commands to work!
    """
    # Check if this GUID+alias combination exists
    cursor = await db.execute(
        'SELECT times_seen FROM player_aliases WHERE guid = ? AND alias = ?',
        (guid, alias)
    )
    existing = await cursor.fetchone()
    
    if existing:
        # Update existing: increment times_seen, update last_seen
        await db.execute(
            '''UPDATE player_aliases 
               SET times_seen = times_seen + 1, last_seen = ?
               WHERE guid = ? AND alias = ?''',
            (last_seen_date, guid, alias)
        )
    else:
        # Insert new alias
        await db.execute(
            '''INSERT INTO player_aliases (guid, alias, first_seen, last_seen, times_seen)
               VALUES (?, ?, ?, ?, 1)''',
            (guid, alias, last_seen_date, last_seen_date)
        )
```

### Fix #2: !stats Command
**Problem:** Couldn't find players because player_aliases table was empty.

**Requirements:**
- Search by Discord mention: `!stats @user`
- Search by player name: `!stats PlayerName` (partial match OK)
- Show own stats if linked: `!stats` (no args)
- Must query player_aliases table first to find GUID
- Then get stats from player_comprehensive_stats
- Display in clean Discord embed with stats, weapons, etc.

### Fix #3: !link Command
**Problem:** Couldn't find/search players to link.

**Requirements:**
- Smart self-link: `!link` shows top 3 suggestions with reactions
- Direct GUID link: `!link ABC12345` with confirmation
- Name search: `!link PlayerName` with options
- Admin link others: `!link @user ABC12345` (admin permission)
- Must search player_aliases table to show available players
- Show player aliases (top 2 names) for identification

### Fix #4: NEW !list_guids Command ⭐ ADMIN GAME CHANGER
**Problem:** Admins had to manually hunt for GUIDs in logs to link players.

**Solution Required:**
```python
@commands.command(name='list_guids', aliases=['listguids', 'unlinked'])
async def list_guids(self, ctx, *, search_term: str = None):
    """
    Show unlinked players with GUIDs and aliases for easy admin linking.
    
    Modes:
    - !list_guids              → Top 10 most active unlinked
    - !list_guids recent       → Last 7 days
    - !list_guids PlayerName   → Search by name
    - !list_guids all          → Show all (max 20)
    """
    # Query player_aliases + player_comprehensive_stats
    # Filter: WHERE guid NOT IN (SELECT et_guid FROM player_links)
    # Show: GUID, top 2 aliases, K/D, games, last_seen
    # Format in Discord embed with easy copy/paste
```

**Display Format:**
```
🆔 ABC12345
**PrimaryName** / SecondName (+2 more)
📊 5,234K / 3,112D / 1.68 KD
🎮 156 games • Last: 2025-10-28

💡 To link: !link @user ABC12345
```

## Database Schema (Must Use)

```sql
-- Player aliases (for name lookups)
CREATE TABLE player_aliases (
    guid TEXT NOT NULL,           -- Player GUID (8 chars)
    alias TEXT NOT NULL,          -- Player name seen in game
    first_seen TEXT,              -- First date with this name
    last_seen TEXT,               -- Most recent date
    times_seen INTEGER DEFAULT 1, -- Frequency counter
    PRIMARY KEY (guid, alias)
);

-- Player linking (Discord to ET:Legacy)
CREATE TABLE player_links (
    discord_id TEXT PRIMARY KEY,
    discord_username TEXT,
    et_guid TEXT,
    et_name TEXT,
    linked_date TEXT,
    verified INTEGER DEFAULT 0
);

-- Comprehensive stats (main stats table)
CREATE TABLE player_comprehensive_stats (
    -- [full schema from current bot]
    session_id INTEGER,
    session_date TEXT,
    player_guid TEXT,
    player_name TEXT,
    kills INTEGER,
    deaths INTEGER,
    -- ... all other stat fields ...
);

-- Sessions tracking
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date TEXT,
    map_name TEXT,
    round_number INTEGER,
    -- ... other session fields ...
);

-- Processed files (prevents re-processing)
CREATE TABLE processed_files (
    filename TEXT PRIMARY KEY,
    success INTEGER,
    error_message TEXT,
    processed_at TEXT
);
```

## Features To Preserve (Keep These!)

### Core Commands (All Working):
- ✅ `!ping` - Bot status
- ✅ `!help_command` - Command list
- ✅ `!leaderboard [type]` - Rankings (kills/kd/dpm/acc/hs)
- ✅ `!session [date]` - Session details
- ✅ `!session_start [map]` - Start monitoring
- ✅ `!session_end` - End monitoring
- ✅ `!sync_stats` - Manual stats sync
- ✅ `!unlink` - Unlink account

### Fixed/New Commands (Integrate Properly):
- ✅ `!stats [player]` - Player statistics (FIXED)
- ✅ `!link [target] [guid]` - Account linking (FIXED)
- 🆕 `!list_guids [search]` - List unlinked players (NEW)

### Background Tasks (Keep These):
- SSH monitoring for new stats files
- Automatic download and processing
- Round summary posting to Discord
- Cache system for performance
- Session management (auto-start at 20:00 CET)
- Voice channel monitoring for sessions

### Key Features:
- Season system (quarterly resets)
- StopwatchScoring integration
- Cache system for performance
- Multiple database path resolution
- Comprehensive error logging
- Discord embed formatting

## Code Quality Requirements

### Architecture:
- ✅ Proper Discord.py Cogs pattern throughout
- ✅ Clean separation of concerns (commands, database, processing)
- ✅ Single Responsibility Principle for methods
- ✅ DRY (Don't Repeat Yourself) - no code duplication

### Database:
- ✅ Use aiosqlite properly (async/await)
- ✅ Connection pooling or proper connection management
- ✅ Parameterized queries (SQL injection prevention)
- ✅ Transactions for multi-step operations
- ✅ Proper error handling and rollback

### Error Handling:
- ✅ Try/except blocks in all commands
- ✅ Meaningful error messages to users
- ✅ Detailed logging for debugging
- ✅ Graceful degradation (don't crash on errors)

### Code Style:
- ✅ Clear, descriptive function/variable names
- ✅ Docstrings for all classes and methods
- ✅ Type hints where helpful
- ✅ Comments for complex logic
- ✅ Consistent formatting (PEP 8 style)

### Performance:
- ✅ Cache frequently used data
- ✅ Optimize database queries (JOINs, indexes)
- ✅ Async operations for I/O
- ✅ Avoid blocking operations

## External Dependencies

The bot uses:
```python
import discord
from discord.ext import commands, tasks
import aiosqlite
import asyncio
import os
import sys
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Custom imports (from your GitHub repo):
from tools.stopwatch_scoring import StopwatchScoring
from community_stats_parser import C0RNP0RN3StatsParser
```

**Note:** Also uses SSH (paramiko/asyncssh) for remote file operations if SSH_ENABLED=true.

## Configuration (.env Variables)

```bash
# Discord
DISCORD_BOT_TOKEN=xxx
STATS_CHANNEL_ID=xxx

# Database
ETLEGACY_DB_PATH=/path/to/etlegacy_production.db

# SSH (optional)
SSH_ENABLED=false
SSH_HOST=xxx
SSH_USER=xxx
SSH_KEY_PATH=xxx
STATS_DIR=/path/on/server

# Voice automation (optional)
AUTOMATION_ENABLED=false
GAMING_VOICE_CHANNELS=xxx,xxx,xxx
SESSION_START_THRESHOLD=6
SESSION_END_THRESHOLD=2
SESSION_END_DELAY=300
```

## What I Need From You

Please create a clean, modern, production-ready rewrite that:

1. **Fixes the core issues:**
   - ✅ Automatic alias tracking (player_aliases table)
   - ✅ Working !stats command
   - ✅ Working !link command
   - ✅ New !list_guids command

2. **Maintains all working features:**
   - All existing commands that work
   - Background tasks and monitoring
   - SSH integration
   - Session management

3. **Improves code quality:**
   - Clean architecture with proper Cogs
   - Consistent patterns throughout
   - Good error handling and logging
   - Well-documented code

4. **Is production-ready:**
   - No duplicated code
   - No dead code
   - Proper async/await usage
   - Optimized database queries

## Success Criteria

The rewritten bot should:
- ✅ Start without errors
- ✅ All commands work correctly
- ✅ `!stats` and `!link` work flawlessly (with alias tracking)
- ✅ `!list_guids` helps admins link players easily
- ✅ Stats processing automatically updates player_aliases
- ✅ Code is clean, documented, and maintainable
- ✅ Performance is good (cached queries, optimized)
- ✅ Easy to add new features in the future

## Additional Notes

- Keep the overall structure similar (don't need to change everything)
- Focus on fixing the critical issues and cleaning up the code
- The bot is used by a small group (~10-20 active players)
- Runs on a Linux VPS (Ubuntu)
- Python 3.10+
- Discord.py 2.3.x

## Files I'm Providing

1. **GitHub repo:** [YOUR_GITHUB_LINK]
2. **Current bot:** ultimate_bot_FINAL.py
3. **Stats parser:** community_stats_parser.py (from repo)
4. **Scoring system:** tools/stopwatch_scoring.py (from repo)
5. **Sample stats files:** 2025-10-23-*.txt (in project)
6. **Lua stats generator:** c0rnp0rn7.lua (for reference)

## Expected Deliverables

1. **ultimate_bot_v2.py** - The clean rewritten bot
2. **README_V2.md** - Updated documentation
3. **MIGRATION_GUIDE.md** - How to migrate from old to new
4. **CHANGES.md** - What changed and why

---

**Let's make this bot production-ready! 🚀**
