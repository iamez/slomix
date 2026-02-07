# Handoff to Next Claude Agent
**Date:** 2026-01-31  
**From:** Claude Opus 4.5 (Configuration Recovery Session)  
**Status:** ✅ Ready for Development

---

## Quick Start

You're now working on the **Slomix Discord Bot** (ET:Legacy stats tracking).

**Current branch:** `feature/lua-webhook-realtime-stats`  
**Last session:** Claude Code configuration restoration & optimization

### Read These First (in order)
1. **Start:** `docs/SESSION_2026-01-31_CLAUDE_CODE_RESTORATION.md` (what just happened)
2. **Reference:** `docs/reference/CLAUDE_CODE_QUICK_REFERENCE.md` (daily commands)
3. **Main Guide:** `docs/CLAUDE.md` (auto-loaded, comprehensive guide)
4. **Navigate:** `docs/SESSION_INDEX.md` (find any documentation)

---

## What Was Done This Session

### Configuration Recovery ✅
- Restored Claude Code configs after 362 MB crash
- Reduced to 1.45 MB (healthy and working)
- MCP PostgreSQL server configured and tested (1,605 rounds accessible)
- Database access: **Working perfectly**

### Settings Review ✅
- Audited Claude Code CLI setup: **Score 7.1/10**
- Found 3 project configs (bot/website/proximity) - this is BY DESIGN
- Identified improvement areas:
  - Strange permissions (wifi5, wifi8, random loops)
  - Missing monitoring commands
  - Only 1 MCP server (can add 2 more)

### Documentation Created ✅
- Comprehensive session report
- Quick reference card
- Settings review with scorecard
- Config audit across all projects
- Navigation index (SESSION_INDEX.md)
- Updated CHANGELOG.md

### Automated Upgrade Script ✅
Created: `~/claude_settings_improvement_plan.sh`

**Will add:**
- Filesystem MCP server (better file ops)
- Git MCP server (enhanced git ops)
- System monitoring commands
- Clean weird permissions
- User preferences (Opus, Plan mode)

**Status:** Ready to run (not executed yet - your choice)

---

## Current Project Status

### Git Status
```
Branch: feature/lua-webhook-realtime-stats
Modified: 9 files (Lua webhook work)
New docs: 3 files
Status: Ready for testing
```

### Development Environment
- Python 3.10.12 ✅
- discord.py 2.3.2 ✅
- asyncpg 0.30.0 ✅
- PostgreSQL: Connected ✅
- Bot: Not running (screen session empty)
- GitHub CLI: Not installed (upgrade script will fix)

### Database
- Type: PostgreSQL 14
- Database: etlegacy
- Rounds: 1,605
- Tables: 32
- MCP Access: **Working**
- Schema: Validated ✅

### Claude Code Configuration
- Global config: 1.4 MB (clean)
- Project configs: 48 KB total (3 projects)
- MCP servers: 1 active (postgres)
- Permissions: Good coverage, needs cleanup
- .claudeignore: Properly configured ✅

---

## Recommended Next Steps

### Option 1: Apply Improvements (Recommended)
```bash
# Run the upgrade script
bash ~/claude_settings_improvement_plan.sh

# Install GitHub CLI
sudo apt install gh
gh auth login

# Restart Claude Code
exit  # Exit current session
claude  # Restart with new configs
```

**After restart you'll have:**
- 3 MCP servers (postgres + filesystem + git)
- Clean permissions
- Monitoring tools
- Better development workflow

### Option 2: Continue Without Upgrades
Current setup works fine - improvements are optional.

Continue with Lua webhook feature development.

---

## Important Warnings

### Do NOT Do These:
1. ❌ Restore full backup (362 MB will crash Claude Code)
2. ❌ Centralize project configs (breaks security isolation)
3. ❌ Commit directly to main branch (use feature branches)
4. ❌ Use SQLite commands (project uses PostgreSQL)
5. ❌ Recalculate R2 differential (parser handles it)

### DO These:
1. ✅ Use feature branches always
2. ✅ Read docs/CLAUDE.md (comprehensive guide)
3. ✅ Query database via MCP tools (fast and easy)
4. ✅ Follow branch policy (never push to main)
5. ✅ Test before committing

---

## MCP Database Tools

You have direct database access:

```
# Query database
mcp__db__execute_sql: SELECT COUNT(*) FROM rounds;

# Explore schema
mcp__db__search_objects --object_type table

# Complex queries
mcp__db__execute_sql: 
  SELECT COUNT(*) 
  FROM rounds 
  WHERE gaming_session_id = (SELECT MAX(gaming_session_id) FROM rounds);
```

**Current data:** 1,605 rounds across 32 tables

---

## Project Structure Reminder

```
slomix_discord/
├── bot/                    # Main bot code
│   ├── cogs/              # 14 command modules
│   ├── core/              # Business logic
│   └── services/          # Service layer
├── docs/                  # 135+ documentation files
│   ├── SESSION_*.md       # Session reports
│   ├── reference/         # Reference docs
│   └── reports/           # Detailed reports
├── .claude/               # Project Claude config
│   ├── memories.md        # Session memory
│   ├── settings.json      # Permissions
│   └── settings.local.json # Extended permissions
├── vps_scripts/           # Lua webhook scripts
└── postgresql_database_manager.py  # DB operations
```

---

## Common Tasks Quick Reference

### Check Bot Status
```bash
screen -ls  # Check if bot running
systemctl status etlegacy-bot  # Check service
```

### Database Query
```bash
# Via MCP (preferred):
mcp__db__execute_sql: SELECT * FROM rounds LIMIT 5;

# Direct psql:
PGPASSWORD='etlegacy_secure_2025' psql -h localhost -U etlegacy_user -d etlegacy
```

### Git Workflow
```bash
git status
git checkout -b feature/my-feature
git add <specific-files>
git commit -m "description"
git push origin feature/my-feature
```

### View Logs
```bash
tail -f logs/bot.log
grep "ERROR" logs/bot.log
```

---

## Current Work: Lua Webhook Feature

**Branch:** `feature/lua-webhook-realtime-stats`

**What it does:**
- Real-time stats notification from game server
- Fixes surrender timing bug
- Captures team composition
- Tracks pause events

**Modified files:**
- bot/cogs/last_session_cog.py
- bot/community_stats_parser.py
- bot/logging_config.py
- bot/services/session_data_service.py
- bot/services/session_stats_aggregator.py
- bot/services/session_view_handlers.py
- bot/ultimate_bot.py
- postgresql_database_manager.py
- vps_scripts/stats_discord_webhook.lua

**Status:** Ready for testing

---

## Documentation Navigation

**For questions about:**
- Claude Code: `docs/reference/CLAUDE_CODE_QUICK_REFERENCE.md`
- Bot architecture: `docs/SYSTEM_ARCHITECTURE.md`
- Database: `docs/DATA_PIPELINE.md`
- Commands: `docs/COMMANDS.md`
- Latest changes: `docs/CHANGELOG.md`
- All sessions: `docs/SESSION_INDEX.md`

**Main guide:** `docs/CLAUDE.md` (auto-loaded by Claude Code)

---

## Emergency Procedures

### Claude Code Won't Start
```bash
# Check config size
du -sh ~/.claude  # Should be <50 MB

# Clean debug logs
rm ~/.claude/debug/*.txt

# Verify MCP config
cat ~/.claude/mcp.json
```

### Database Issues
```bash
# Test connection
PGPASSWORD='etlegacy_secure_2025' psql -d etlegacy -c "SELECT 1;"

# Check service
sudo systemctl status postgresql
```

### Bot Won't Start
```bash
# Check logs
tail logs/bot.log

# Test manually
python3 -m bot.ultimate_bot
```

---

## Key Files Reference

**Configuration:**
- `.claude/settings.local.json` - Project permissions
- `~/.claude/mcp.json` - MCP servers
- `.env` - Environment variables
- `.claudeignore` - Excluded directories

**Core Code:**
- `bot/ultimate_bot.py` - Main entry point
- `postgresql_database_manager.py` - DB operations
- `bot/community_stats_parser.py` - Stats parser

**Documentation:**
- `docs/CLAUDE.md` - Main guide (auto-loaded)
- `docs/SESSION_INDEX.md` - Navigate all docs
- This file - Handoff to next agent

---

## Success Criteria

You're ready when:
- ✅ You've read the session report
- ✅ You understand what was done
- ✅ You know where documentation is
- ✅ You can query the database via MCP
- ✅ You know current branch and status

---

## Contact & Support

**For help:**
- Read `docs/CLAUDE.md` (comprehensive)
- Check `docs/SESSION_INDEX.md` (find specific docs)
- Review `docs/reference/CLAUDE_CODE_QUICK_REFERENCE.md` (commands)

**Common issues:**
- All documented in session reports
- Check `docs/archive/` for historical fixes
- See `docs/CHANGELOG.md` for recent changes

---

**Last Updated:** 2026-01-31  
**Next Agent:** Continue Lua webhook feature or apply improvements first  
**Configuration Status:** ✅ Healthy and optimized  
**Ready for:** Development

---

Good luck! Everything is documented and ready. 🚀
