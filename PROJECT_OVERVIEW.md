# ET:Legacy Stats Ecosystem

## Vision

A comprehensive stats tracking and analytics platform for Wolfenstein: Enemy Territory Legacy servers. Started as a Discord bot, expanding into web interfaces and advanced combat analytics.

## The Big Picture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ET:LEGACY GAME SERVER                           │
│  ┌─────────────────┐    ┌─────────────────────────────────────┐    │
│  │  c0rnp0rn.lua   │    │  proximity_tracker.lua (prototype)  │    │
│  │  (stats mod)    │    │  (engagement tracking)              │    │
│  └────────┬────────┘    └──────────────┬──────────────────────┘    │
│           │                            │                            │
│           ▼                            ▼                            │
│    stats/*.txt files           *_engagements.txt files              │
└───────────┬────────────────────────────┬────────────────────────────┘
            │                            │
            │         SSH/SFTP           │
            ▼                            ▼
┌───────────────────────────────────────────────────────────────────────┐
│                         LOCAL SERVER (VPS)                            │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                     PostgreSQL Database                          │ │
│  │  • player_comprehensive_stats (53 columns)                       │ │
│  │  • gaming_sessions, session_rounds                               │ │
│  │  • combat_engagement, player_teamplay_stats (proximity)          │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                              ▲                                        │
│              ┌───────────────┼───────────────┐                       │
│              │               │               │                        │
│  ┌───────────┴───────────┐   │   ┌──────────┴───────────┐           │
│  │   Discord Bot (main)  │   │   │   Website (FastAPI)  │           │
│  │   • 14 cogs           │   │   │   • Read-only DB     │           │
│  │   • Live posting      │   │   │   • Public stats     │           │
│  │   • !stats commands   │   │   │   • Leaderboards     │           │
│  └───────────────────────┘   │   └──────────────────────┘           │
│                              │                                        │
│              ┌───────────────┴───────────────┐                       │
│              │  Proximity Parser (prototype) │                        │
│              │  • Engagement analytics       │                        │
│              │  • Crossfire detection        │                        │
│              │  • Heatmap generation         │                        │
│              └───────────────────────────────┘                       │
└───────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
slomix_discord/                    # Root - Main Discord Bot
├── bot/                           # Bot source code
│   ├── ultimate_bot.py            # Main entry (4,990 lines)
│   ├── cogs/                      # 14 command modules
│   ├── core/                      # Shared business logic
│   └── services/                  # Automation (SSH, health)
├── postgresql_database_manager.py # DB management & imports
├── community_stats_parser.py      # Parse c0rnp0rn.lua output
│
├── website/                       # SUB-PROJECT: Web Interface
│   ├── website.code-workspace     # Open this for website dev
│   ├── backend/                   # FastAPI server
│   ├── js/                        # Frontend (vanilla JS)
│   └── index.html                 # Main page
│
├── proximity/                     # SUB-PROJECT: Combat Analytics
│   ├── proximity.code-workspace   # Open this for proximity dev
│   ├── lua/                       # Game server Lua script
│   ├── parser/                    # Python parser
│   └── schema/                    # PostgreSQL schema
│
└── local_stats/                   # Stats files from game server
```

## Components

### 1. Discord Bot (PRODUCTION)
**Status:** Production-ready, running on VPS

The core system. Tracks player stats from ET:Legacy servers via c0rnp0rn.lua mod.

**Features:**
- Real-time stats posting to Discord
- 50+ stats per player per round
- Session grouping (12-hour windows)
- Team detection algorithms
- Leaderboards, comparisons, records

**Key Commands:** `!stats`, `!last_session`, `!compare`, `!top`, `!leaderboard`

### 2. Website (PROTOTYPE)
**Status:** Prototype, basic functionality working

Web interface for viewing stats without Discord.

**Goal:** Public-facing stats page anyone can access

**Stack:** FastAPI backend + vanilla JS frontend

**Features (planned):**
- Player profiles with full stats
- Leaderboards and records
- Session history with graphs
- Search functionality

### 3. Proximity Tracker (PROTOTYPE)
**Status:** Prototype v3, not yet integrated

Advanced combat analytics that c0rnp0rn.lua doesn't capture.

**Goal:** Track teamplay coordination and combat patterns

**What it tracks:**
- **Crossfire:** 2+ players hitting same target within 1 second
- **Escapes:** Player survives after taking damage (5s + 300 units)
- **Engagements:** Combat windows from first hit to death/escape
- **Heatmaps:** Per-map kill/death density grids

**Future possibilities:**
- "Best duo" leaderboards
- Teamplay ratings
- Map visualization overlays
- Focus-fire coordination scores

## Data Flow

### Current (Bot)
```
Game Server → c0rnp0rn.lua → stats/*.txt → SSH → Parser → PostgreSQL → Bot → Discord
```

### Future (Full Ecosystem)
```
Game Server
    ├── c0rnp0rn.lua → stats/*.txt ─────────────┐
    └── proximity_tracker.lua → *_engagements.txt ──┤
                                                    ▼
                                              SSH/Download
                                                    │
                    ┌───────────────────────────────┴──────────────────────────────┐
                    │                         PostgreSQL                           │
                    │  player_comprehensive_stats │ combat_engagement              │
                    │  gaming_sessions            │ player_teamplay_stats          │
                    │  session_rounds             │ crossfire_pairs                │
                    │  processed_files            │ map_kill_heatmap               │
                    └──────────────┬──────────────┴───────────────┬────────────────┘
                                   │                              │
                    ┌──────────────┴──────────────┐    ┌─────────┴─────────┐
                    │        Discord Bot          │    │      Website      │
                    │  • Live game posting        │    │  • Public stats   │
                    │  • Interactive commands     │    │  • Visualizations │
                    │  • Admin tools              │    │  • Map heatmaps   │
                    └─────────────────────────────┘    └───────────────────┘
```

## Why Three Projects?

| Concern | Bot | Website | Proximity |
|---------|-----|---------|-----------|
| Audience | Discord users | Anyone with browser | Advanced analytics |
| Access | Private server | Public | Internal |
| Data | Read/Write | Read-only | Write new tables |
| Language | Python | Python + JS | Lua + Python |
| Complexity | High (mature) | Medium | High (algorithms) |

Separating them means:
- **Focused development** - Each workspace has relevant context only
- **Independent deployment** - Website can update without touching bot
- **Clear boundaries** - Website can't accidentally write to main stats
- **Specialized AI assistance** - Copilot instructions tuned per project

## For AI Agents

### Working on Bot (this workspace)
- Main codebase, 4,990+ line bot
- Use `postgresql_database_manager.py` for DB operations
- Never break the 53-column schema
- SSH monitoring in `ultimate_bot.py`, NOT `ssh_monitor.py`

### Working on Website (`website/website.code-workspace`)
- FastAPI + vanilla JS only
- READ-ONLY database access
- Don't add frameworks - keep it simple

### Working on Proximity (`proximity/proximity.code-workspace`)
- Lua script runs on game server (can't test locally without ET)
- Parser can be tested with sample files
- Design for FOREVER storage (~50MB/year)

## Historical Context

- **2024:** Bot started as simple stats tracker
- **Oct 2025:** Major schema unification (35 → 53 columns)
- **Nov 2025:** VPS migration, PostgreSQL as primary
- **Dec 2025:** Website prototype started
- **Dec 2025:** Proximity tracker v3 designed (engagement-centric)

## Future Roadmap

### Short Term
- [ ] Complete website basic functionality
- [ ] Test proximity tracker on live server
- [ ] Integrate proximity parser with bot

### Medium Term
- [ ] Website: Interactive graphs and charts
- [ ] Website: Player search and profiles
- [ ] Proximity: "Best duo" Discord commands
- [ ] Proximity: Teamplay rating system

### Long Term
- [ ] Website: Map visualization with heatmap overlays
- [ ] Website: Match replays from position data
- [ ] Proximity: Real-time crossfire alerts in Discord
- [ ] Mobile-friendly website design

## Contributing

1. **Bot changes:** Work in main workspace, test with `python bot/ultimate_bot.py`
2. **Website changes:** Open `website/website.code-workspace`
3. **Proximity changes:** Open `proximity/proximity.code-workspace`

Each sub-project has its own `.github/copilot-instructions.md` with context.

## Key Files Reference

| File | What It Does |
|------|--------------|
| `bot/ultimate_bot.py` | Main bot entry, cog loader, SSH monitor |
| `postgresql_database_manager.py` | Schema, imports, backups |
| `community_stats_parser.py` | Parse c0rnp0rn.lua output |
| `bot/core/database_adapter.py` | Async DB abstraction |
| `website/backend/main.py` | FastAPI entry point |
| `proximity/lua/proximity_tracker.lua` | Game server module |
| `proximity/parser/parser.py` | Engagement parser |

---

*This ecosystem was built to track stats for a Wolfenstein: Enemy Territory community. The game is from 2003 but still has active players. ET:Legacy is a modern open-source client.*
