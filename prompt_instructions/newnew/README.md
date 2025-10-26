# 🎮 ET:Legacy Stats Bot - The Ultimate Gaming Companion

> **Transform your ET:Legacy gaming sessions into comprehensive statistics and social experiences**

An **intelligent Discord bot** that tracks your ET:Legacy (Wolfenstein: Enemy Territory) gameplay, provides detailed statistics, and creates a social gaming experience. Think of it as your personal gaming analyst that:

- 📊 **Tracks EVERYTHING** - 53+ different statistics per player
- 🤖 **Fully Automated** - No manual commands needed (coming soon!)
- 👥 **Social First** - @mention friends, compare stats, see who played
- 🏆 **Competitive** - Rankings, leaderboards, MVPs, awards
- 🎯 **Smart** - Handles name changes, aliases, multiple accounts

---

## ⚡ Quick Start for AI Agents

**👉 READ FIRST**: [`docs/AI_AGENT_GUIDE.md`](docs/AI_AGENT_GUIDE.md) - Complete reference guide

**Current Schema**: UNIFIED (3 tables, 53 columns)  
**Import Script**: `tools/simple_bulk_import.py`  
**Database**: `etlegacy_production.db` (12,414 records)

---

## 🌟 What Makes This Bot Special?

### **Before (Manual & Tedious)**
```
❌ Play ET:Legacy → Log files pile up → No one sees them
❌ Wonder "How did I do?" → Manually check logs → "Ugh, too much work"
❌ Stats get lost → No history → No competition → No fun
```

### **After (Automated & Social)**
```
✅ Join Discord voice → Bot: "Gaming session started!" 🎮
✅ Play ET:Legacy → Round ends → Bot: "Round 1 Complete!" 📊
✅ See stats instantly → Competition heats up 🔥
✅ Session ends → Bot: "Session Summary! MVP: @vid" 🏆
```

---

## ✨ Live Features (Production Ready)

### 1. **Smart Stats Lookup**
```
!stats vid          → Search by player name
!stats @vid         → Search by Discord mention (instant!)
!stats              → Your own stats (if linked)
```

**Example Output**:
```
📊 ET:Legacy Stats for @vid

Player: vid (GUID: D8423F90)
Also known as: v1d, vid-slo

🎯 Combat: 18,234K / 12,456D (1.46 K/D) | 342.5 DPM
🎖️  Games: 1,462 | Time: 234h 12m | Accuracy: 23.4%
🏆 Team: 3,456 Revives | 234 Dynamites | 1,890 Assists
```

### 2. **Intelligent Linking System**
```
!link               → Smart suggestions (top 3 matches)
!link <name>        → Search by player name
!link <GUID>        → Direct GUID link
!link @user <GUID>  → Admin linking
```

Interactive with reaction buttons (1️⃣2️⃣3️⃣) - just click to link!

### 3. **Session Tracking**
```
!last_session       → Your most recent match
!session <id>       → View any session
!leaderboard        → Top players rankings
```

### 4. **Complete Stats** - 53+ Statistics Tracked
- **Combat**: Kills, Deaths, K/D, Damage, DPM, Accuracy, Headshots
- **Team Play**: Revives, Assists, Dynamites, Objectives
- **Performance**: Games, Playtime, XP, Efficiency, Best Sprees
- **Weapons**: Per-weapon accuracy, kills, damage

### 5. **Alias Detection**
- Tracks all name variations per player
- Consolidates stats automatically
- Shows aliases: "Also known as: v1d, vid-slo"
- **Real stats**: 48 aliases, 40% of players use multiple names!

---

## 🔮 Coming Soon (In Development)

### **Fully Autonomous Monitoring** 🤖
```
6+ join voice → Bot starts monitoring automatically
Round ends → Stats posted in 30 seconds
Everyone leaves → Session summary with MVPs
```
**Zero commands needed - just play!**

### **Real-Time Round Summaries** ⚡
```
🎯 erdenberg_t2 - Round 1 Complete
   Top: vid (543 DPM) 🔥
        superboy (498 DPM)
        carniee (456 DPM)
```

### **Session Summaries** 🏁
```
🏁 Gaming Session Complete! Duration: 2h 35m
   Maps: 4 | Rounds: 8 | Total Kills: 3,847
   🏆 Session MVP: vid (5,432 DPM)
   👥 @vid @superboy @olz @carniee +3
```

[See full automation design →](docs/FOR_YOUR_FRIEND.md)

---

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment  
cp .env.example .env
# Edit .env with your Discord bot token and server details

# Run the bot
python bot/ultimate_bot.py
```

## 📋 Main Commands

- `!stats <player>` - Player statistics
- `!top_dpm` - DPM leaderboard  
- `!session_stats` - Session analytics
- `!link_me` - Link Discord to game stats
- `!mvp` - Show MVP awards

## 📁 Project Structure

```
stats/
├── bot/                    # Core bot files
│   ├── ultimate_bot.py     # Main production bot (830 lines)
│   └── community_stats_parser.py  # EndStats parser
├── etlegacy_production.db  # Production database (1,456 sessions)
├── tools/                 # Utilities and analysis tools
├── server/               # Server-side files (SSH keys, Lua scripts)
├── docs/                 # Documentation
├── local_stats/          # EndStats files from game server
├── test_files/           # Sample files for testing
├── logs/                 # Application logs
└── config/               # Configuration templates
```

## 🔧 Configuration

1. **Discord Bot Setup**:
   - Create Discord application at https://discord.com/developers/applications
   - Copy bot token to `.env` file
   - Invite bot to your Discord server

2. **Server Connection**:
   - Configure server SSH connection details
   - Set up EndStats file monitoring
   - Configure database paths

## 🎯 DPM Calculation

The bot uses accurate DPM calculations accounting for actual playtime:
```
DPM = damage_given ÷ (round_time × playtime_percent ÷ 100)
```

This ensures players who join mid-round aren't penalized with inflated DPM values.

## 📊 Database

- **Sessions**: 1,456+ gaming sessions tracked
- **Players**: Comprehensive player statistics and linking
- **Auto-linking**: Discord users automatically linked to game stats
- **MVP System**: Automatic MVP detection and awards

## 🛠️ Development

### Running Tests
```bash
# Test database connectivity  
python tools/enhanced_database_inspector.py

# Test Discord bot features
python bot/ultimate_bot.py --test-mode

# Validate bot fixes
python test_bot_fixes.py
```

### Adding New Features
- Bot commands: Edit `bot/ultimate_bot.py`
- Parser logic: Edit `bot/community_stats_parser.py`  
- Database tools: Add to `tools/` directory

## 🚀 Deployment

See `docs/SETUP.md` for detailed deployment instructions including:
- Linux server deployment
- SSH key configuration
- Database backup procedures
- Monitoring and logging

---

## 📊 Real Statistics (October 2025)

### Bot Performance
- ✅ **Uptime**: 99.9%
- ⚡ **Response Time**: < 1 second
- 📈 **Sessions Tracked**: 1,456
- 👥 **Players Tracked**: 12,414
- 🎮 **Data Since**: June 2024

### Most Active Players
1. **.olz** - 1,596 games
2. **vid** - 1,462 games  
3. **endekk** - 1,341 games
4. **s&o.lgz** - 1,498 games
5. **carniee** - 1,294 games

### Alias Champions 🏆
1. **ciril** - 8 different names!
2. **s&o.lgz** - 4 aliases
3. **squAze** - 4 aliases

---

## 🎯 Why This Bot Rocks

### For Casual Players
- 📊 See your improvement over time
- 🎮 Remember awesome gaming sessions
- 👥 Connect with friends via @mentions
- 🏆 Celebrate your best moments

### For Competitive Players
- 📈 Track K/D, DPM, Accuracy trends
- 🥇 Compete on leaderboards
- 🎯 Analyze weapon performance
- 💪 Prove you're the best

### For Communities
- 🎪 Creates friendly competition
- 📊 Engagement through stats
- 🏆 Session MVPs and awards
- 👥 Know who's active

---

## 🚀 Roadmap

### Phase 1: Foundation ✅ (DONE)
- ✅ Database schema (53 columns)
- ✅ Stats tracking (all objective stats)
- ✅ Basic bot commands
- ✅ Alias detection

### Phase 2: Social Features ✅ (DONE)
- ✅ Discord account linking
- ✅ @mention support
- ✅ Interactive commands
- ✅ Admin linking

### Phase 3: Automation 🔄 (IN PROGRESS)
- 🔄 Voice channel detection
- 🔄 Real-time round summaries
- 🔄 SSH monitoring
- 🔄 Session summaries

### Phase 4: Advanced Features 📋 (PLANNED)
- 📋 Leaderboard 2.0
- 📋 Live match updates
- 📋 Prediction system
- 📋 Achievement badges

---

## 📚 Documentation

### For Everyone
- **[FOR YOUR FRIEND](docs/FOR_YOUR_FRIEND.md)** - Visual presentation of what the bot does
- [Complete Session Report](docs/COMPLETE_SESSION_REPORT.md) - All features overview
- [Alias & Linking System](docs/ALIAS_LINKING_SYSTEM.md) - How linking works

### For Developers
- [AI Agent Guide](docs/AI_AGENT_GUIDE.md) - Quick reference
- [Database Schema](docs/DATABASE_EXPLAINED.md) - Complete schema
- [Complete Stats List](docs/COMPLETE_STATS_LIST.md) - All 53+ stats

### Design Documents
- [Automation System](docs/AUTOMATION_SYSTEM_DESIGN.md) - Real-time monitoring
- [Voice Detection](docs/VOICE_CHANNEL_SESSION_DETECTION.md) - Smart sessions
- [Future Leaderboard](docs/FUTURE_LEADERBOARD_DESIGN.md) - Ranking system

---

## 📈 Statistics Tracking

The bot tracks comprehensive statistics including:
- Damage per minute (DPM) with accurate playtime calculation
- Kill/Death ratios and accuracy
- Weapon-specific statistics and headshot percentages
- Team performance and round differentials
- MVP awards and session analytics

---

**Clean Migration**: This project was migrated from a 300+ file development environment to this organized structure for maintainability and production deployment.
