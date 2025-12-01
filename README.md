# 🎮 ET:Legacy Stats Bot - Production-Grade Gaming Analytics Platform

> **Enterprise-level data pipeline transforming ET:Legacy gaming sessions into comprehensive, real-time statistics**

[![Production Status](https://img.shields.io/badge/status-production-brightgreen)](https://github.com/iamez/slomix)
[![Data Integrity](https://img.shields.io/badge/data%20integrity-6%20layers-blue)](docs/SAFETY_VALIDATION_SYSTEMS.md)
[![Automation](https://img.shields.io/badge/automation-fully%20implemented-orange)](bot/services/automation/INTEGRATION_GUIDE.md)

A **production-grade Discord bot** with **zero-downtime automation**, **6-layer data validation**, and **intelligent differential stat calculation** for ET:Legacy game servers.

## 🔥 Recent Updates (December 2025)

### **🔧 v1.0.1: Critical Bug Fixes (December 1, 2025)** 🆕

**Live Posting Fixed!** Resolved race condition that prevented Discord stats posting:

- 🔴 **SSHMonitor Race Condition** - Fixed critical bug where two monitoring systems competed for files, causing live Discord posting to fail
- 🔇 **Silent Channel Checks** - Bot no longer announces "wrong channel" errors; silently ignores commands in non-configured channels
- 📢 **Channel Filtering Fix** - Fixed bot responding to commands in wrong channels
- 🌐 **Website Fixes** - Fixed HTML corruption, JS duplicate functions, and SQL injection vulnerability

**Technical:** SSHMonitor auto-start disabled; `endstats_monitor` now handles SSH + DB import + Discord posting as single system.

### **🎯 MAJOR: Competitive Analytics System (Weeks 11-12)**

**The prediction system is HERE!** An AI-powered match prediction engine with 12 new commands:

- 🔮 **Match Predictions** - AI predicts match outcomes when teams split into voice channels
- 📊 **4-Factor Algorithm** - H2H (40%), Form (25%), Map Performance (20%), Substitutions (15%)
- 🎯 **Confidence Scoring** - High/Medium/Low confidence based on data quality
- 📈 **Accuracy Tracking** - Brier score calculation, trend analysis, performance metrics
- 🏆 **Player Leaderboards** - Most predictable, unpredictable (wildcards), and active players
- 🗺️ **Map Analytics** - Map-specific prediction accuracy and team bias detection
- 💬 **12 New Commands** - 7 user commands + 5 admin commands for complete analytics

**Status:** Fully functional, ready to enable after monitoring week (64% of project complete, 39/61 hours)

**Latest Session Enhancements:**
- 🏆 **Achievement System** - Player badges for medics, engineers, combat specialists, and more!
- 🎨 **Custom Display Names** - Linked players can set personalized display names
- 📊 **Enhanced Performance Graphs** - Exact value labels on all stat visualizations
- 📢 **Upgraded Auto-Posting** - Now shows ALL players with comprehensive stats (not just top performers)
- 🎯 **Improved Session Output** - Redesigned !last_session format with achievement badges

**Previous Critical Optimizations:**
- ✅ **Voice-Conditional SSH Monitoring** - Only checks SSH when players in voice (massive resource savings!)
- ✅ **SSH Monitor Startup Optimization** - Only checks last 24h on startup (not all 3,766 files)
- ✅ **PostgreSQL Boolean Compatibility** - Fixed boolean type errors in queries
- ✅ **File Exclusion Filters** - Automatically excludes `_ws.txt` and unwanted files
- ✅ **Security Hardening** - Secure temp files, command sanitization, and rate limiting

## ✨ What Makes This Special

- � **6-Layer Data Integrity** - Transaction safety, ACID guarantees, per-insert verification
- 🤖 **Full Automation** - SSH monitoring, auto-download, auto-import, auto-post (60s cycle)
- 🧮 **Differential Calculation** - Smart Round 2 stats (subtracts Round 1 for accurate team-swap metrics)
- 📊 **53+ Statistics** - K/D, DPM, accuracy, efficiency, weapon breakdowns, objective stats
- ⚡ **Real-Time Processing** - VPS → Local → Database → Discord in <3 seconds per file
- 🎯 **Zero Data Loss** - PostgreSQL transactions, rollback on error, 4,193 verified inserts

**[📊 View Data Pipeline](docs/DATA_PIPELINE.md)** | **[🔒 Safety & Validation Systems](docs/SAFETY_VALIDATION_SYSTEMS.md)** | **[🔄 Round 2 Pipeline Explained](docs/ROUND_2_PIPELINE_EXPLAINED.txt)** | **[📝 Changelog](docs/CHANGELOG.md)**

---

## 🏗️ System Architecture

### **Data Pipeline Overview**

```
┌─────────────────────────────────────────────────────────────────┐
│                    ET:Legacy Game Server (VPS)                  │
│  /home/et/.etlegacy/legacy/gamestats/*.txt (3,694 files)       │
└────────────────┬────────────────────────────────────────────────┘
                 │ SSH/SFTP (every 60 seconds)
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│              Layer 1: Download & Transfer Integrity             │
│  ✓ File exists check  ✓ Size validation  ✓ Readability check   │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│           Layer 2: Duplicate Prevention (4-Step Check)          │
│  ✓ Startup time filter  ✓ Cache check  ✓ Filesystem check      │
│  ✓ Database processed_files  ✓ Database rounds table           │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│        Layer 3: Parser-Level Validation & Differential          │
│  ✓ Round 2 detection  ✓ Type/range validation                  │
│  ✓ Time-gap matching (reject >60min)  ✓ Map name matching      │
│  ✓ Logical validation (headshots ≤ kills)                       │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│        Layer 4: Pre-Insert Validation (7 Comprehensive          │
│                     Checks)                                     │
│  1. Player count match    2. Weapon count match                 │
│  3. Total kills match     4. Total deaths match                 │
│  5. Weapon/player kills   6. No negative values                 │
│  7. Round 2 validation (team distribution skipped)              │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│   Layer 5: PostgreSQL Transaction (ACID Guarantees)             │
│  ✓ BEGIN TRANSACTION  ✓ Per-insert verification (RETURNING)    │
│  ✓ Gaming session ID calculation (60-min gap threshold)         │
│  ✓ COMMIT or ROLLBACK (all-or-nothing)                          │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│              Layer 6: Database Constraints                      │
│  ✓ NOT NULL  ✓ CHECK (kills >= 0)  ✓ UNIQUE  ✓ FOREIGN KEY    │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Discord Auto-Post (Optional)                   │
│  Round summaries → #stats channel (if automation enabled)       │
└─────────────────────────────────────────────────────────────────┘
```

**Processing Speed:**
- Download: ~0.5s per file
- Parse: ~0.8s per file (Round 2: +0.3s for differential)
- Validate: ~0.2s per file
- Database Insert: ~1.5s per file (with verification)
- **Total: ~3 seconds per file** (end-to-end)

---

## 🔒 Data Integrity & Safety Systems

### **6 Layers of Protection**

| Layer | Component | What It Protects | Blocking? |
|-------|-----------|------------------|-----------|
| **1** | File Transfer | Download corruption, empty files | ✅ Yes |
| **2** | Duplicate Prevention | Re-processing, bot restarts | ✅ Yes |
| **3** | Parser Validation | Invalid types, impossible stats | ✅ Yes |
| **4** | 7-Check Validation | Aggregate mismatches, data loss | ⚠️ No (warns) |
| **5** | Per-Insert Verification | Silent corruption, type conversion | ✅ Yes |
| **6** | PostgreSQL Constraints | NOT NULL, negative values, orphans | ✅ Yes |

**Result:** Every data point verified at **multiple checkpoints** before commit.

**[📖 Full Documentation: SAFETY_VALIDATION_SYSTEMS.md](docs/SAFETY_VALIDATION_SYSTEMS.md)**

### **Special Safety Features**

#### **Round 2 Differential Calculation**
When processing Round 2 files (team-swap rounds), the system:
1. ✅ Detects Round 2 files automatically
2. ✅ Searches for matching Round 1 file (same map, <60min gap)
3. ✅ Rejects old Round 1 files (prevents matching wrong session)
4. ✅ Calculates differential stats (Round 2 - Round 1)
5. ✅ Produces accurate per-team performance metrics

**Example:**
```
Round 1: 21:31 (etl_adlernest) - Player vid: 20 kills
Round 2: 23:41 (etl_adlernest) - Player vid: 42 kills cumulative
         ❌ REJECTED: 21:31 Round 1 (135.9 min gap - different session)
         ✅ MATCHED: 23:41 Round 1 (5.8 min gap - same session)
         Result: vid Round 2 stats = 22 kills (42 - 20)
```

**[📖 Full Documentation: ROUND_2_PIPELINE_EXPLAINED.txt](docs/ROUND_2_PIPELINE_EXPLAINED.txt)**

#### **Gaming Session ID Calculation**
Automatically groups rounds into gaming sessions:
- ✅ Calculates time gap between rounds
- ✅ If gap > 60 minutes: **New session**
- ✅ If gap ≤ 60 minutes: **Same session**
- ✅ Powers `!last_session` command accuracy

#### **Transaction Safety (ACID)**
- ✅ **Atomicity:** All inserts succeed or all rollback
- ✅ **Consistency:** Database constraints enforced
- ✅ **Isolation:** Concurrent operations don't interfere
- ✅ **Durability:** Committed data survives crashes

**Production Proof:**
- **303 files downloaded** ✅
- **0 files failed** ✅
- **4,193 successful verifications** ✅
- **1 Round 2 rejection** (correct behavior - rejected old Round 1) ✅

---

## 🌟 Features

### **🔮 Competitive Analytics - AI Match Predictions** 🆕

**The most advanced prediction system for any gaming stats platform:**

#### **Prediction Engine**
- 🤖 **Automatic Detection** - Detects when players split into team voice channels (3v3, 4v4, 5v5, 6v6)
- 🧠 **4-Factor Algorithm** - Weighted analysis of Head-to-Head (40%), Recent Form (25%), Map Performance (20%), Substitutions (15%)
- 🎯 **Confidence Scoring** - High/Medium/Low confidence based on historical data quality
- 📊 **Real-Time Probability** - Live win probability calculations (30-70% range with sigmoid scaling)
- ⏱️ **Cooldown Management** - Smart 5-minute cooldown prevents prediction spam

#### **Analytics & Commands**
- 📈 **!predictions** - View recent predictions with beautiful embeds
- 📊 **!prediction_stats** - Accuracy statistics dashboard (overall, by confidence level, recent trends)
- 👤 **!my_predictions** - Personal match history and performance
- 📉 **!prediction_trends** - Daily accuracy trends with improvement detection
- 🏆 **!prediction_leaderboard** - Rankings: Most predictable, wildcards, most active players
- 🗺️ **!map_predictions** - Map-specific accuracy and team bias detection
- ❓ **!prediction_help** - Complete user documentation

#### **Admin Tools**
- 🔧 **!admin_predictions** - Advanced filtering (pending, completed, correct, incorrect)
- ✏️ **!update_prediction_outcome** - Manual result updates with Brier score calculation
- 🔄 **!recalculate_predictions** - Batch accuracy recalculation
- 📊 **!prediction_performance** - System performance dashboard
- 🛠️ **!admin_prediction_help** - Admin documentation

#### **Database & Tracking**
- 💾 **3 New Tables** - match_predictions (35 columns), session_results (21 columns), map_performance (13 columns)
- 🎯 **Accuracy Tracking** - Brier score calculation, prediction correctness, confidence analysis
- 📊 **Trend Analysis** - Week-over-week comparison, best/worst days, improving/declining detection
- 🏅 **Leaderboards** - Player predictability rankings with minimum 3 matches filter

**[📖 Implementation Guide](COMPETITIVE_ANALYTICS_IMPLEMENTATION_GUIDE.md)** | **[📊 Progress Tracker](IMPLEMENTATION_PROGRESS_TRACKER.md)**

---

### **Production-Ready Statistics** ✅

#### **Intelligent Stats System**
- 📊 **53+ Statistics Tracked** - K/D, DPM, accuracy, efficiency, headshots, damage, playtime
- 🎯 **Smart Player Lookup** - `!stats vid` or `!stats @discord_user` (instant)
- 🔗 **Interactive Linking** - React with 1️⃣2️⃣3️⃣ to link Discord account to game stats
- � **Alias Tracking** - Automatically consolidates stats across name changes
- 📈 **Session Analytics** - `!last_session` shows 14-20 rounds per gaming session
- 🗺️ **Map Statistics** - Per-map breakdowns with R1/R2 differential
- 🏆 **Achievement System** - Dynamic badges for medics, engineers, sharpshooters, rambo, objective specialists
- 🎨 **Custom Display Names** - Linked players can set personalized names with `!set_display_name`

#### **Leaderboard System**
- 🥇 **11 Leaderboard Categories** - K/D, DPM, accuracy, headshots, efficiency, etc.
- � **Dynamic Rankings** - Real-time updates as games are played
- 🎮 **Minimum Thresholds** - Prevents stat padding (min 10 rounds, 300 damage, etc.)

#### **Database & Performance**
- �️ **PostgreSQL 18.0** - Production-grade ACID compliance
- ⚡ **Connection Pooling** - asyncpg for high-performance async queries
- 📦 **7 Tables, 53 Columns** - Comprehensive unified schema
- 🔄 **Gaming Session Grouping** - Automatic 60-minute gap detection
- 💾 **Processed Files Tracking** - Prevents duplicate imports

### **Full Automation - Implemented & Ready** 🤖

**All automation features are production-ready!** Requires `.env` configuration.

#### **Zero-Touch Operation**
- 🎙️ **Voice Detection** - Monitors gaming voice channels (6+ users = auto-start)
- 🔄 **SSH Monitoring** - Checks VPS every 60 seconds for new files
- 📥 **Auto-Download** - SFTP transfer with integrity verification
- 🤖 **Auto-Import** - Parse → Validate → Database (6-layer safety)
- 📢 **Auto-Post** - Round summaries posted to Discord automatically
- 🏁 **Session Summaries** - Auto-posted when players leave voice

#### **Smart Startup Optimization** ⚡
- 🚀 **24-Hour Lookback** - On startup, only processes files from last 24 hours (not all historical files)
- 📅 **Configurable Window** - Set `SSH_STARTUP_LOOKBACK_HOURS` (default: 24)
- 🎯 **File Filtering** - Automatically excludes `_ws.txt` and other unwanted files
- ⏱️ **Fast Startup** - Processes ~5 recent files instead of 3,766+ historical files

#### **Voice-Conditional SSH Monitoring** 🎙️
- 🎮 **Smart Checks** - Only checks SSH when players are in voice channels (saves resources!)
- 💤 **Idle Mode** - Skips SSH checks when voice channels are empty (0 players)
- ⚡ **Active Mode** - Checks SSH every 60s when 1+ players in voice
- ⏳ **Grace Period** - Continues checking for 10min after players leave (catches final round files)
- 🔧 **Configurable** - Set `SSH_VOICE_CONDITIONAL=true`, `SSH_GRACE_PERIOD_MINUTES=10`

**Enable:** Set `AUTOMATION_ENABLED=true` and `SSH_ENABLED=true` in `.env`

**[📖 Setup Guide: bot/services/automation/INTEGRATION_GUIDE.md](bot/services/automation/INTEGRATION_GUIDE.md)**

---

## 🚀 Quick Start

### **Prerequisites**
- Python 3.9+
- PostgreSQL 12+ (local or remote)
- Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))
- SSH access to ET:Legacy server (optional, for automation)

### **Installation**

```bash
# 1. Clone repository
git clone https://github.com/iamez/slomix.git
cd slomix

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your settings:
#   - DISCORD_TOKEN
#   - POSTGRES_* settings
#   - SSH_* settings (optional)
nano .env

# 4. Setup database (first time only)
python postgresql_database_manager.py
# Choose:
#   1 - Create fresh database (initialize schema)
#   2 - Import all files from local_stats/ directory

# 5. Run the bot
python -m bot.ultimate_bot
```

### **Database Configuration**

Edit `.env` file:
```env
# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=etlegacy
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Discord Bot
DISCORD_TOKEN=your_bot_token_here
STATS_CHANNEL_ID=your_channel_id

# Automation (Optional)
AUTOMATION_ENABLED=false
SSH_ENABLED=false
SSH_HOST=your.vps.server
SSH_PORT=22
SSH_USER=et
SSH_KEY_PATH=~/.ssh/etlegacy_bot
REMOTE_STATS_PATH=/home/et/.etlegacy/legacy/gamestats
SSH_CHECK_INTERVAL=60
SSH_STARTUP_LOOKBACK_HOURS=24
SSH_VOICE_CONDITIONAL=true
SSH_GRACE_PERIOD_MINUTES=10

# Voice Channels (comma-separated IDs for voice-conditional monitoring)
GAMING_VOICE_CHANNELS=947583652957659166,1029097483697143938
```

---

## 📋 Commands

### **🔮 Prediction Commands** 🆕

**User Commands (7):**
- `!predictions [limit]` - View recent predictions (default: 10)
- `!prediction_stats [days]` - Accuracy statistics dashboard (default: 30 days)
- `!my_predictions` - Your personal match prediction history
- `!prediction_trends [days]` - Daily accuracy trends and analysis (default: 30 days)
- `!prediction_leaderboard [category]` - Player rankings (predictable/unpredictable/active)
- `!map_predictions [map]` - Map-specific prediction statistics
- `!prediction_help` - Complete prediction system documentation

**Admin Commands (5):**
- `!admin_predictions [status] [limit]` - Advanced prediction filtering
- `!update_prediction_outcome <id> <winner> <score_a> <score_b>` - Update match results
- `!recalculate_predictions [days]` - Recalculate accuracy for recent predictions
- `!prediction_performance` - System performance dashboard
- `!admin_prediction_help` - Admin documentation and tools

---

### **Player Statistics**
- `!stats <player>` - Full player statistics (K/D, DPM, accuracy, etc.)
- `!stats @user` - Stats for Discord-linked player
- `!compare <player1> <player2>` - Head-to-head comparison

### **Leaderboards**
- `!top_dpm` - Damage per minute rankings
- `!top_kd` - K/D ratio leaderboard
- `!top_accuracy` - Weapon accuracy rankings
- `!top_efficiency` - Kill efficiency leaderboard
- Plus 7 more leaderboard categories!

### **Session & Round Info**
- `!last_session` - Latest gaming session (14-20 rounds)
- `!last_round` - Most recent round played
- `!session_stats` - Current session analytics

### **Account Management**
- `!link` - Link Discord account to game stats (interactive)
- `!link_me` - Quick link (if GUID known)
- `!unlink` - Remove Discord link
- `!set_display_name <name>` - Set custom display name for linked account
- `!achievements` - View achievement system help and available badges

### **Admin Commands**
- `!sync_month` - Sync last 30 days from VPS
- `!sync_all` - Sync all files from VPS
- `!rebuild_sessions` - Recalculate gaming sessions
- `!health` - System health check

### **Help & Info**
- `!help` - Show all commands
- `!mvp` - MVP awards for session
- `!ping` - Bot latency and cache stats

---

## 📁 Project Structure

```
slomix/
├── 📊 Core Systems
│   ├── bot/
│   │   ├── ultimate_bot.py              # Main bot (enhanced with predictions)
│   │   ├── community_stats_parser.py    # Round 1/2 differential parser (1,036 lines)
│   │   ├── cogs/
│   │   │   ├── last_session_cog.py      # Session stats & summaries
│   │   │   ├── predictions_cog.py       # 🆕 Prediction user commands (862 lines)
│   │   │   ├── admin_predictions_cog.py # 🆕 Prediction admin tools (530 lines)
│   │   │   └── sync_cog.py              # VPS sync commands
│   │   ├── services/
│   │   │   ├── prediction_engine.py     # 🆕 AI prediction engine (540 lines)
│   │   │   ├── prediction_embed_builder.py # 🆕 Beautiful prediction embeds (395 lines)
│   │   │   └── voice_session_service.py # 🆕 Team split detection
│   │   ├── core/
│   │   │   ├── database_adapter.py      # PostgreSQL/SQLite abstraction
│   │   │   └── stats_cache.py           # TTL-based caching (300s)
│   │
│   └── postgresql_database_manager.py   # Database operations (1,573 lines)
│       ├── 6-layer validation system
│       ├── ACID transaction wrapper
│       ├── Per-insert verification (RETURNING clause)
│       └── Gaming session ID calculation
│
├── 🔒 Safety & Validation Documentation
│   └── docs/SAFETY_VALIDATION_SYSTEMS.md  # Complete safety inventory
│
├── 📖 Pipeline Documentation
│   ├── docs/DATA_PIPELINE.md            # Detailed technical pipeline
│   └── docs/ROUND_2_PIPELINE_EXPLAINED.txt  # Differential calculation
│
├── 🤖 Automation Documentation
│   └── bot/services/automation/INTEGRATION_GUIDE.md  # Automation setup
│
├── 📂 Data & Logs
│   ├── local_stats/                     # Stats files (288+ files)
│   └── logs/                            # Application logs
│       ├── bot.log                      # Main bot log
│       ├── errors.log                   # Error tracking
│       ├── database.log                 # Database operations
│       └── commands.log                 # Command usage
│
├── ⚙️ Configuration
│   ├── .env                             # Environment configuration
│   ├── .env.example                     # Template
│   └── requirements.txt                 # Python dependencies (11 packages)
│
├── 📚 Documentation
│   ├── docs/
│   │   ├── COMMANDS.md                  # Bot commands reference
│   │   ├── DATA_PIPELINE.md             # Pipeline documentation
│   │   ├── FIELD_MAPPING.md             # Stats fields reference
│   │   ├── SYSTEM_ARCHITECTURE.md       # Architecture docs
│   │   ├── TECHNICAL_OVERVIEW.md        # Technical guide
│   │   └── COMPETITIVE_ANALYTICS_MASTER_PLAN.md # 🆕 Prediction system design
│   ├── DEPLOYMENT_CHECKLIST.md          # Deployment guide
│   ├── COMPETITIVE_ANALYTICS_IMPLEMENTATION_GUIDE.md # 🆕 Prediction implementation
│   ├── IMPLEMENTATION_PROGRESS_TRACKER.md # 🆕 Project progress (64% complete)
│   ├── WEEK_HANDOFF_MEMORY.md           # 🆕 Week handoff documentation
│   ├── GEMINI_IMPLEMENTATION_GUIDE.md   # 🆕 Website developer guide
│   ├── VPS_SETUP.md                     # VPS setup instructions
│   └── AI_AGENT_INSTRUCTIONS.md         # For AI assistants
│
├── 🌐 Website (Separate Project - In Development)
│   ├── website/backend/                 # FastAPI backend
│   ├── website/index.html               # Tailwind CSS frontend
│   └── website/js/app.js                # SPA logic
│
└── 🔧 Development Tools
    ├── check_last_session_data.py       # Diagnostic scripts
    ├── find_missing_files.py            # VPS sync verification
    └── test_logging.py                  # Log system test
```

**Key Files:**
- **`postgresql_database_manager.py`** - ALL database operations (1,573 lines: create, import, rebuild, validate)
- **`bot/ultimate_bot.py`** - Main production bot (enhanced with predictions)
- **`bot/community_stats_parser.py`** - Round 2 differential calculation (1,036 lines)
- **`bot/services/prediction_engine.py`** - 🆕 AI prediction engine (540 lines)
- **`bot/cogs/predictions_cog.py`** - 🆕 User prediction commands (862 lines)
- **`bot/core/database_adapter.py`** - Async DB abstraction layer
- **`docs/SAFETY_VALIDATION_SYSTEMS.md`** - Complete safety documentation
- **`IMPLEMENTATION_PROGRESS_TRACKER.md`** - 🆕 Project progress tracking

---

## �️ Database Schema

### **PostgreSQL Production Schema**

```sql
-- Main Tables
rounds (id, round_date, round_time, match_id, map_name, round_number, 
        gaming_session_id, winner_team, time_limit, actual_time)

player_comprehensive_stats (53 columns)
    ├── Core: round_id, player_guid, player_name, team
    ├── Combat: kills, deaths, headshots, damage_given, damage_received
    ├── Performance: kd_ratio, dpm, efficiency, accuracy
    ├── Time: time_played_seconds, time_played_minutes, time_dead_ratio
    └── Objectives: revives, constructions, dynamites, etc. (25 columns)

weapon_stats (round_id, player_guid, weapon_name, kills, deaths, 
              headshots, hits, shots, accuracy)

-- Management Tables
processed_files (filename, processed_at, success, error_message)
player_links (discord_user_id, player_guid, linked_at)
player_aliases (guid, alias, times_seen, last_seen)
session_teams (session_id, player_guid, team)

-- 🆕 Competitive Analytics Tables (Weeks 11-12)
match_predictions (35 columns, 6 indexes)
    ├── Prediction: team_a/b_guids, team_a/b_win_probability, confidence
    ├── Factors: h2h_score, form_score, map_score, subs_score, weighted_score
    ├── Metadata: prediction_time, session_date, format (3v3, 4v4, etc.)
    ├── Results: actual_winner, prediction_correct, prediction_accuracy
    └── Discord: discord_message_id, discord_channel_id

session_results (21 columns)
    ├── Session: session_date, gaming_session_id, format, total_rounds
    ├── Teams: team_1/2_guids, team_1/2_names, team_1/2_score
    ├── Outcome: winning_team, round_details (JSON)
    └── Timing: session_start_time, session_end_time, duration

map_performance (13 columns)
    ├── Player: player_guid, map_name
    ├── Stats: matches_played, wins, losses, win_rate
    └── Performance: avg_kills, avg_deaths, avg_kd_ratio, avg_dpm
```

**Gaming Session ID:**
- Automatically calculated during import
- 60-minute gap = new session
- Powers `!last_session` accuracy

**Indexes:**
```sql
CREATE INDEX idx_rounds_session ON rounds(gaming_session_id);
CREATE INDEX idx_player_round ON player_comprehensive_stats(round_id);
CREATE INDEX idx_player_guid ON player_comprehensive_stats(player_guid);
CREATE UNIQUE INDEX idx_player_round_unique ON player_comprehensive_stats(round_id, player_guid);
```

---

## 🧮 How It Works

### **Round 2 Differential Calculation**

ET:Legacy maps have **team-swap rounds** (Round 1 → Round 2). Stats files show **cumulative totals**, not per-round performance. The bot calculates true Round 2 stats:

**The Problem:**
```
Round 1 (Axis): Player vid gets 20 kills
Round 2 (Allies): Stats file shows 42 kills (cumulative)
```

**Without Differential:**
- Round 2 stats = 42 kills ❌ (WRONG - includes Round 1)

**With Differential:**
1. ✅ Detect Round 2 file: `2025-11-04-234716-etl_adlernest-round-2.txt`
2. ✅ Search for Round 1: `2025-11-04-*-etl_adlernest-round-1.txt`
3. ✅ Find multiple candidates:
   - `2025-11-04-213124-etl_adlernest-round-1.txt` (21:31) - 135.9 min gap
   - `2025-11-04-234127-etl_adlernest-round-1.txt` (23:41) - 5.8 min gap
4. ✅ Reject old Round 1 (>60 min gap - different session)
5. ✅ Match correct Round 1 (5.8 min gap - same session)
6. ✅ Calculate: `Round 2 kills = 42 - 20 = 22 kills` ✅ (CORRECT)

**Time-Gap Validation:**
```python
if time_gap_minutes > 60:
    logger.warning(f"❌ Rejected: {r1_file} ({time_gap_minutes:.1f} min gap - too old)")
    continue  # Try next Round 1 file

if time_gap_minutes < 60:
    logger.info(f"✅ Match found: {r1_file} ({time_gap_minutes:.1f} min before)")
    # Use this Round 1 for subtraction
```

**Production Proof:**
```
[2025-11-06 09:19:16] Processing 2025-11-04-234716-etl_adlernest-round-2.txt
[R2] Detected Round 2 file
  → Found 2 same-day Round 1 files
  → ❌ Rejected: 2025-11-04-213124-etl_adlernest-round-1.txt (135.9 min gap)
  → ✅ Match found: 2025-11-04-234127-etl_adlernest-round-1.txt (5.8 min)
[OK] Successfully calculated Round 2-only stats for 8 players
```

**[📖 Complete Documentation: ROUND_2_PIPELINE_EXPLAINED.txt](docs/ROUND_2_PIPELINE_EXPLAINED.txt)**

---

## 🎯 DPM Calculation

**Accurate playtime-adjusted damage per minute:**

```python
# WRONG (naive calculation)
dpm = damage_given / total_round_time
# Problem: Penalizes players who join mid-round

# CORRECT (playtime-adjusted)
actual_playtime_seconds = time_played_seconds
actual_playtime_minutes = actual_playtime_seconds / 60.0
dpm = damage_given / actual_playtime_minutes if actual_playtime_minutes > 0 else 0

# Example:
# Round time: 10 minutes
# Player joins at 5 minutes (plays 5 minutes)
# Damage given: 1500
# DPM = 1500 / 5 = 300 DPM (accurate)
# NOT 1500 / 10 = 150 DPM (wrong - player wasn't there)
```

**Why This Matters:**
- ✅ Fair comparison for late joiners
- ✅ Accurate performance metrics
- ✅ Leaderboards reflect true skill

---
## 🛠️ Development

### **Database Operations**

**ALL database operations use `postgresql_database_manager.py`:**

```bash
python postgresql_database_manager.py
```

**Available Operations:**
1. **Create Fresh Database** - Initialize schema from scratch
2. **Import All Files** - Incremental import (safe, skips processed files)
3. **Rebuild from Scratch** - Nuclear option (wipes all data, re-imports)
4. **Fix Specific Date Range** - Re-import specific dates
5. **Validate Database** - Run 7-check validation on all data
6. **Quick Test** - Import 10 files for testing

⚠️ **IMPORTANT:** Never create new import/database scripts. This is the **ONLY** tool for database operations.

### **Running Tests**

```bash
# Test parser functionality
python bot/community_stats_parser.py test_files/sample-round-1.txt

# Test database health
python postgresql_database_manager.py
# Choose option 5 (Validate database)

# Test Discord bot
python -m bot.ultimate_bot
# Use !ping to check latency
```

### **Adding New Features**

**Bot Commands:**
```bash
# Edit main bot file
nano bot/ultimate_bot.py

# Or add a new cog
nano bot/cogs/new_feature_cog.py
```

**Parser Logic:**
```bash
# Edit differential calculation
nano bot/community_stats_parser.py
```

**Database Operations:**
```bash
# Edit database manager (NOT new scripts!)
nano postgresql_database_manager.py
```

### **Code Quality**

**Logging:**
- All operations logged to `logs/` directory
- Structured logging with timestamps
- Separate error, database, and command logs

**Error Handling:**
- Transaction rollback on errors
- Graceful degradation
- Detailed error messages in logs

**Performance:**
- asyncio/asyncpg for async operations
- Connection pooling (min 2, max 10)
- TTL-based caching (300s)

---

## 🚀 Deployment

### **Production Environment**

**Requirements:**
- Ubuntu 20.04+ or Windows Server
- PostgreSQL 12+
- Python 3.9+
- 2GB RAM minimum
- SSH access to ET:Legacy server (for automation)

**Production Checklist:**
- [ ] PostgreSQL installed and running
- [ ] Bot user created with database access
- [ ] `.env` file configured with production values
- [ ] Database schema created (`option 1`)
- [ ] Initial data imported (`option 2`)
- [ ] Bot runs without errors
- [ ] Automation tested (if enabled)
- [ ] Logs directory exists and writable
- [ ] Backup system configured

### **Linux Deployment**

```bash
# Install dependencies
sudo apt update
sudo apt install postgresql python3-pip

# Create database
sudo -u postgres createdb etlegacy
sudo -u postgres psql -c "CREATE USER etbot WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE etlegacy TO etbot;"

# Setup bot
cd /opt/slomix
pip3 install -r requirements.txt
python3 postgresql_database_manager.py  # Option 1, then 2

# Run as service
sudo nano /etc/systemd/system/etlegacy-bot.service
```

**Service File:**
```ini
[Unit]
Description=ET:Legacy Stats Bot
After=network.target postgresql.service

[Service]
Type=simple
User=etbot
WorkingDirectory=/opt/slomix
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 -m bot.ultimate_bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl enable etlegacy-bot
sudo systemctl start etlegacy-bot
sudo systemctl status etlegacy-bot
```

### **Monitoring**

```bash
# Check logs
tail -f logs/bot.log
tail -f logs/errors.log

# Check database
psql -d etlegacy -c "SELECT COUNT(*) FROM rounds;"

# Check bot health (in Discord)
!health
!ping
```

### **Backup Strategy**

```bash
# Database backup (daily)
pg_dump etlegacy > backup/etlegacy_$(date +%Y%m%d).sql

# Backup rotation (keep 7 days)
find backup/ -name "etlegacy_*.sql" -mtime +7 -delete

# Test restore
psql -d etlegacy_test < backup/etlegacy_20251106.sql
```

---

## 📈 Performance Metrics

### **Production Statistics**

| Metric | Value |
|--------|-------|
| **Files Imported** | 303 (recent sync) |
| **Total Rounds** | 1,862+ |
| **Unique Players** | 25 |
| **Verified Inserts** | 4,193 (100% success) |
| **Import Speed** | ~3 seconds per file |
| **Database Size** | ~50MB (with indexes) |
| **Bot Response Time** | <100ms (cached queries) |

### **Scalability**

**Current Load:**
- 60-second SSH monitoring cycle
- ~10 new files per gaming session
- ~30 seconds total import time per session
- Zero performance degradation

**Tested Capacity:**
- ✅ 3,694 files on VPS (tested with sync)
- ✅ Concurrent Discord commands (10+ simultaneous)
- ✅ Large gaming sessions (20 rounds, 10 players)
- ✅ 24/7 uptime (weeks without restart)

**Optimization:**
- Connection pooling prevents DB bottlenecks
- TTL caching reduces query load by 80%
- Async operations prevent blocking
- Indexed queries (<10ms on average)

---

## 🐛 Troubleshooting

### **Common Issues**

#### **Bot Won't Start**
```bash
# Check logs
tail -n 50 logs/errors.log

# Verify database connection
psql -d etlegacy -c "SELECT 1;"

# Check .env file
cat .env | grep -v "^#"
```

#### **Files Not Importing**
```bash
# Check processed files
psql -d etlegacy -c "SELECT COUNT(*) FROM processed_files WHERE success = false;"

# View errors
psql -d etlegacy -c "SELECT filename, error_message FROM processed_files WHERE success = false LIMIT 10;"

# Re-import failed files
python postgresql_database_manager.py  # Option 2
```

#### **Automation Not Working**
```bash
# Check SSH connection
ssh -i ~/.ssh/etlegacy_bot et@your.vps.server

# Verify .env settings
cat .env | grep SSH_

# Check automation logs
tail -f logs/bot.log | grep "SSH"
```

#### **Database Errors**
```bash
# Check database health
python postgresql_database_manager.py  # Option 5

# Verify schema
psql -d etlegacy -c "\dt"  # List tables

# Check for corruption
psql -d etlegacy -c "SELECT COUNT(*) FROM rounds WHERE gaming_session_id IS NULL;"
```

### **Getting Help**

1. **Check Documentation:**
   - [docs/SAFETY_VALIDATION_SYSTEMS.md](docs/SAFETY_VALIDATION_SYSTEMS.md) - Data integrity
   - [docs/ROUND_2_PIPELINE_EXPLAINED.txt](docs/ROUND_2_PIPELINE_EXPLAINED.txt) - Differential logic
   - [bot/services/automation/INTEGRATION_GUIDE.md](bot/services/automation/INTEGRATION_GUIDE.md) - Automation setup
   - [docs/DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md) - Deployment guide

2. **Check Logs:**
   - `logs/bot.log` - General operations
   - `logs/errors.log` - Error tracking
   - `logs/database.log` - Database operations

3. **Validate Data:**
   - Run `!health` in Discord
   - Check database with option 5
   - Verify file counts match VPS

4. **Report Issues:**
   - Include log excerpts
   - Specify error messages
   - Note when issue started
   - Describe steps to reproduce

---

## 📚 Documentation Index

### **Getting Started**
- [README.md](README.md) - This file (you are here!)
- [docs/DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md) - Deployment guide
- [docs/FRESH_INSTALL_GUIDE.md](docs/FRESH_INSTALL_GUIDE.md) - Fresh installation guide
- [bot/services/automation/INTEGRATION_GUIDE.md](bot/services/automation/INTEGRATION_GUIDE.md) - Automation setup
- [docs/AI_AGENT_INSTRUCTIONS.md](docs/AI_AGENT_INSTRUCTIONS.md) - For AI assistants

### **🆕 Competitive Analytics (Prediction System)**
- [COMPETITIVE_ANALYTICS_IMPLEMENTATION_GUIDE.md](COMPETITIVE_ANALYTICS_IMPLEMENTATION_GUIDE.md) - Complete implementation guide
- [IMPLEMENTATION_PROGRESS_TRACKER.md](IMPLEMENTATION_PROGRESS_TRACKER.md) - Project progress (64% complete, 39/61 hours)
- [WEEK_HANDOFF_MEMORY.md](WEEK_HANDOFF_MEMORY.md) - Week handoff documentation
- [docs/COMPETITIVE_ANALYTICS_MASTER_PLAN.md](docs/COMPETITIVE_ANALYTICS_MASTER_PLAN.md) - System design and architecture
- [GEMINI_IMPLEMENTATION_GUIDE.md](GEMINI_IMPLEMENTATION_GUIDE.md) - Website integration guide

### **🆕 Website Project (In Development)**
- [WEBSITE_PROJECT_REVIEW.md](WEBSITE_PROJECT_REVIEW.md) - Technical review (8/10 rating)
- [WEBSITE_VISION_REVIEW_2025-11-28.md](WEBSITE_VISION_REVIEW_2025-11-28.md) - Strategic vision (9.5/10 rating)
- [WEBSITE_APPJS_CHANGES_2025-11-28.md](WEBSITE_APPJS_CHANGES_2025-11-28.md) - Recent changes analysis

### **System Architecture**
- [docs/DATA_PIPELINE.md](docs/DATA_PIPELINE.md) - Complete data pipeline
- [docs/TECHNICAL_OVERVIEW.md](docs/TECHNICAL_OVERVIEW.md) - Technical architecture
- [docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md) - System overview
- [docs/SAFETY_VALIDATION_SYSTEMS.md](docs/SAFETY_VALIDATION_SYSTEMS.md) - 6-layer safety
- [docs/ROUND_2_PIPELINE_EXPLAINED.txt](docs/ROUND_2_PIPELINE_EXPLAINED.txt) - Differential calculation

### **Reference & Guides**
- [docs/FIELD_MAPPING.md](docs/FIELD_MAPPING.md) - Stats field reference
- [docs/COMMANDS.md](docs/COMMANDS.md) - Bot commands reference
- [docs/CONFIGURATION_REFERENCE.md](docs/CONFIGURATION_REFERENCE.md) - Configuration guide
- [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md) - Testing procedures

### **Operations & Deployment**
- [docs/VPS_DEPLOYMENT_GUIDE.md](docs/VPS_DEPLOYMENT_GUIDE.md) - VPS deployment
- [docs/LINUX_DEPLOYMENT_GUIDE.md](docs/LINUX_DEPLOYMENT_GUIDE.md) - Linux deployment
- [docs/LAPTOP_DEPLOYMENT_GUIDE.md](docs/LAPTOP_DEPLOYMENT_GUIDE.md) - Local deployment
- [docs/DISASTER_RECOVERY.md](docs/DISASTER_RECOVERY.md) - Disaster recovery procedures

### **System Documentation**
- [docs/ACHIEVEMENT_SYSTEM.md](docs/ACHIEVEMENT_SYSTEM.md) - Achievement system
- [docs/ADVANCED_TEAM_DETECTION.md](docs/ADVANCED_TEAM_DETECTION.md) - Team detection
- [docs/SEASON_SYSTEM.md](docs/SEASON_SYSTEM.md) - Season system
- [docs/STOPWATCH_IMPLEMENTATION.md](docs/STOPWATCH_IMPLEMENTATION.md) - Stopwatch mode
- [docs/SUBSTITUTION_DETECTION.md](docs/SUBSTITUTION_DETECTION.md) - Player substitution
- [docs/CHANGELOG.md](docs/CHANGELOG.md) - Project changelog

---

## 🤝 Contributing

**Contributions welcome!** Please:
1. Fork the repository
2. Create a feature branch
3. Follow existing code style
4. Add tests for new features
5. Update documentation
6. Submit pull request

**Code Standards:**
- PEP 8 for Python
- Docstrings for functions
- Type hints where applicable
- Comprehensive error handling
- Structured logging

---

## 📄 License

This is a private project. All rights reserved.

---

## 🙏 Acknowledgments

**Built With:**
- [discord.py](https://github.com/Rapptz/discord.py) - Discord API wrapper
- [asyncpg](https://github.com/MagicStack/asyncpg) - PostgreSQL async driver
- [PostgreSQL](https://www.postgresql.org/) - Production database
- [ET:Legacy](https://www.etlegacy.com/) - Game engine

**Special Thanks:**
- ET:Legacy community for EndStats mod
- Discord.py community for excellent documentation
- PostgreSQL team for rock-solid database

---

## 📞 Contact

**Project Maintainer:** [@iamez](https://github.com/iamez)  
**Repository:** [github.com/iamez/slomix](https://github.com/iamez/slomix)  
**Issues:** [GitHub Issues](https://github.com/iamez/slomix/issues)

---

<div align="center">

**⭐ Star this repo if it helped you!**

Built with ❤️ for the ET:Legacy community

</div>
