# 🎯 GitHub Project Structure Analysis

## Core Files Needed for Bot to Function

### 1. **Bot Core** (Essential)
```
bot/
├── ultimate_bot.py          - Main bot file (5,656 lines)
├── community_stats_parser.py - Stats file parser
└── cogs/
    └── synergy_analytics.py  - FIVEEYES cog (optional)
```

### 2. **Database** (Essential)
```
create_unified_database.py  - Creates 53-column schema (BOT-COMPATIBLE)
```

### 3. **Configuration** (Essential)
```
.env                    - Environment variables (NOT in git)
.env.example            - Template for .env
requirements.txt        - Python dependencies
```

### 4. **Tools** (Optional but useful)
```
tools/
├── simple_bulk_import.py     - Import stats files
├── sync_stats.py             - SSH sync from server
├── update_team_names.py      - Update session_teams
└── create_session_teams_table.py - Setup hardcoded teams
```

### 5. **Documentation** (Essential for GitHub)
```
README.md               - Main project documentation
LICENSE                 - Open source license
.gitignore             - Ignore .env, database, local files
```

---

## Dependencies Identified

### From `bot/ultimate_bot.py`:
```python
# Standard library
import asyncio
import datetime
import logging
import os
import time
import sqlite3

# External packages
import aiosqlite       # Async SQLite
import discord         # Discord API
from discord.ext import commands, tasks

# Optional (for SSH features)
import paramiko        # SSH/SFTP
import pytz            # Timezone handling
```

### From `bot/community_stats_parser.py`:
```python
import re              # Regex for parsing
import os
```

---

## Python Package Requirements

```txt
# Core Discord
discord.py>=2.3.0
aiosqlite>=0.19.0

# Optional SSH Features
paramiko>=3.0.0
pytz>=2023.3
```

---

## Environment Variables Needed

```env
# Discord Bot Configuration
DISCORD_BOT_TOKEN=your_bot_token_here
GUILD_ID=your_server_id
STATS_CHANNEL_ID=your_channel_id

# Optional: SSH Monitoring
SSH_ENABLED=false
SSH_HOST=your_server
SSH_PORT=22
SSH_USER=username
SSH_KEY_PATH=~/.ssh/id_rsa
REMOTE_STATS_DIR=/path/to/gamestats
SSH_CHECK_INTERVAL=30

# Optional: Voice Channel Automation
AUTOMATION_ENABLED=false
GAMING_VOICE_CHANNELS=channel_id1,channel_id2
ACTIVE_PLAYER_THRESHOLD=6
INACTIVE_DURATION_SECONDS=180
```

---

## Files NOT Needed for GitHub

### Development/Debug Files (200+ files!)
- All `check_*.py` scripts (diagnostic tools)
- All `debug_*.py` scripts
- All `analyze_*.py` scripts
- All `compare_*.py` scripts
- All `test_*.py` scripts
- `comprehensive_audit.py`
- `check_syntax.py`
- `check_database_integrity.py`

### Backup Folders
- `backups/` (entire folder - 50+ files)
- `prompt_instructions/` (old files)

### Documentation Overload (67+ MD files!)
- `docs/` folder - 44 files
- Root MD files - 67 files
- **Solution**: Consolidate into ONE comprehensive README.md

### Database Files
- `etlegacy_production.db` (user creates this)
- `*.db` files

### Local Data
- `local_stats/` folder (1,862 stat files)
- User downloads their own stats

### Analytics/Experimental
- `analytics/` folder (synergy detection - optional)
- `tools/migrations/` (one-time migrations)

---

## Proposed GitHub Structure

```
etlegacy-discord-bot/          ← Clean project root
├── README.md                   ← Comprehensive guide
├── LICENSE                     ← GPL-3.0 or MIT
├── .gitignore                  ← Ignore .env, *.db, local_stats/
├── requirements.txt            ← Python dependencies
├── .env.example                ← Configuration template
│
├── bot/                        ← Core bot code
│   ├── __init__.py
│   ├── ultimate_bot.py         ← Main bot (5,656 lines)
│   ├── community_stats_parser.py ← Parser
│   └── cogs/
│       ├── __init__.py
│       └── synergy_analytics.py  ← Optional FIVEEYES
│
├── tools/                      ← Utility scripts
│   ├── __init__.py
│   ├── simple_bulk_import.py   ← Import stats
│   ├── sync_stats.py           ← SSH sync
│   ├── update_team_names.py    ← Team management
│   └── create_session_teams_table.py
│
├── database/                   ← Database setup
│   ├── __init__.py
│   └── create_unified_database.py ← Schema creator
│
└── docs/                       ← Minimal documentation
    ├── SETUP.md                ← Quick start guide
    ├── COMMANDS.md             ← Command reference
    └── CONFIGURATION.md        ← Advanced config
```

---

## Documentation Consolidation Plan

### Current Situation
- **111 MD files** scattered everywhere!
- **67 in root** (development session logs)
- **44 in docs/** (guides, references, archives)
- **Confusion**: Which file to read? Which to share?

### Solution: ONE Master README

**Keep Only**:
1. `README.md` (main) - 300-400 lines
   - Project overview
   - Features
   - Quick start
   - Commands
   - Configuration
   - Troubleshooting
   - Contributing

2. `docs/SETUP.md` (optional) - Detailed setup
3. `docs/COMMANDS.md` (optional) - Full command reference
4. `docs/CONFIGURATION.md` (optional) - Advanced config

**Archive Everything Else**:
- Move to `docs/archive/` or delete entirely
- Most are session logs (development history)
- Not useful for GitHub users

---

## Size Comparison

### Current Workspace (Messy)
```
Total files: ~500+
Python files: 436
MD files: 111
Database: 1 (10MB)
Stats files: 1,862
Backups: 100+
```

### GitHub Project (Clean)
```
Total files: ~20
Python files: 8 core files
MD files: 1-4
Database: 0 (user creates)
Stats files: 0 (user downloads)
Backups: 0
Size: <1MB (code only)
```

**97% smaller!** Clean, focused, professional.

---

## Next Steps

1. ✅ Create `github/` folder
2. ✅ Copy essential files
3. ✅ Create configuration templates
4. ✅ Write consolidated README.md
5. ✅ Test bot runs from GitHub structure
6. ✅ Prepare for public release

---

**Generated**: October 7, 2025
**Purpose**: GitHub preparation analysis
**Status**: Ready to implement
