# Claude Code CLI Settings Review - Slomix Discord Bot
Date: 2026-01-31

## Current Configuration Analysis

### ✅ What You're Doing RIGHT

1. **MCP PostgreSQL Server** - EXCELLENT!
   - Direct database access via mcp__db__execute_sql
   - Can query/explore schema without writing SQL files
   - Properly configured for etlegacy database

2. **Project-Specific Permissions** - GOOD!
   - settings.json: Basic commands (python, git, pip, pytest)
   - settings.local.json: Extended permissions (psql, ssh, screen)
   - MCP tools whitelisted explicitly

3. **Feature Branch Workflow** - PERFECT!
   - Currently on: feature/lua-webhook-realtime-stats
   - Following CLAUDE.md guidelines (never commit to main)

4. **Security Isolation** - GOOD!
   - Project permissions don't leak to other projects
   - Global settings are minimal (empty allow list)

### ⚠️ Issues Found

1. **Redundant/Strange Permissions** in settings.local.json:
   - Line 42-43: `Bash(wifi5)` and `Bash(wifi8)` - What are these?
   - Lines 33-40: Hardcoded loop commands (openssl rand, awk, etc.)
   - These look like leftover experiment commands

2. **Missing Useful Permissions**:
   - `systemctl` commands (to check bot service status)
   - `journalctl` (to read bot logs)
   - `tail -f` (to follow logs in real-time)
   - `du` and `df` (disk usage checks)
   - `ps` and `top` (process monitoring)

3. **No GitHub CLI (gh)**:
   - CLAUDE.md mentions using `gh` for PR creation
   - Not installed on system
   - No permissions configured for it

4. **PostgreSQL Credentials in Multiple Places**:
   - PGPASSWORD in settings.local.json (line 11 and 45)
   - Could use .pgpass file instead for cleaner auth

### 🎯 Recommended Improvements

#### 1. Clean Up settings.local.json

Remove these oddball commands:
```json
"Bash(wifi5)",
"Bash(wifi8)",
"Bash(for i in 1 2 3)",
"Bash(do openssl rand 10000)",
"Bash(fold:*)",
"Bash(while read -r n)",
"Bash(do awk -v k=\"$n\" '$1==k {print $2}' /tmp/wordlist.txt)",
"Bash(openssl rand:*)",
```

Add these useful commands:
```json
"Bash(systemctl status etlegacy-bot)",
"Bash(journalctl -u etlegacy-bot:*)",
"Bash(tail:*)",
"Bash(head:*)",
"Bash(du:*)",
"Bash(df:*)",
"Bash(ps:*)",
"Bash(top:*)",
"Bash(htop:*)",
"Bash(free:*)",
"Bash(uptime)",
"Bash(whoami)",
"Bash(pwd)",
"Bash(env)",
"Bash(which:*)",
"Bash(gh:*)"
```

#### 2. Install GitHub CLI

```bash
# Install gh CLI for PR management
sudo apt install gh
# Or via snap:
sudo snap install gh
```

Then add to settings.local.json:
```json
"Bash(gh pr:*)",
"Bash(gh issue:*)",
"Bash(gh repo:*)",
"Bash(gh auth:*)"
```

#### 3. Add More MCP Servers (Optional)

Consider these useful MCP servers:

**A. Filesystem MCP** (Better file operations):
```json
"filesystem": {
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-filesystem",
    "/home/samba/share/slomix_discord"
  ]
}
```

**B. Git MCP** (Enhanced git operations):
```json
"git": {
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-git",
    "--repository",
    "/home/samba/share/slomix_discord"
  ]
}
```

**C. Web Search MCP** (For looking up docs):
```json
"brave-search": {
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-brave-search"
  ],
  "env": {
    "BRAVE_API_KEY": "your-api-key"
  }
}
```

#### 4. Add .claudeignore (Already Exists!)

Good - you have .claudeignore. Should contain:
```
__pycache__/
*.pyc
.env
*.db
*.db-journal
logs/
local_stats/
backups/
*.log
.venv/
venv/
node_modules/
.git/
```

#### 5. Consider Adding User Preferences

In `~/.claude/settings.json`, add:
```json
{
  "permissions": {
    "allow": [],
    "deny": [],
    "ask": []
  },
  "enabledPlugins": {},
  "defaults": {
    "model": "opus",
    "mode": "plan",
    "explainMode": true
  }
}
```

Benefits:
- Always start in plan mode (safer for code changes)
- Use Opus by default (smarter for complex tasks)
- Get educational explanations

### 📊 Missing Development Tools

Tools mentioned in CLAUDE.md but not verified:

1. **GitHub CLI (gh)** - NOT INSTALLED
   ```bash
   sudo apt install gh
   gh auth login
   ```

2. **PostgreSQL Client Tools** - ✅ INSTALLED (psql works)

3. **Python Testing** - ✅ pytest installed

4. **Screen** - ✅ INSTALLED (for bot daemon)

5. **SSH Tools** - ✅ INSTALLED (ssh, scp, rsync)

### 🔧 Suggested MCP Tools Priority

**High Priority** (Install these):
1. ✅ PostgreSQL MCP - Already have it!
2. ⭐ Filesystem MCP - Better file operations
3. ⭐ Git MCP - Enhanced git operations

**Medium Priority**:
4. Web Search MCP - For looking up Discord.py docs
5. GitHub MCP - PR/issue management

**Low Priority**:
6. Memory MCP - Long-term context storage
7. Sequential Thinking MCP - Complex reasoning

### 🎨 Optional: Add Project Metadata

Create `.claude/config.json`:
```json
{
  "project": {
    "name": "Slomix Discord Bot",
    "version": "1.0.5",
    "type": "python-discord-bot",
    "defaultBranch": "main",
    "productionBranch": "main",
    "featureBranchPrefix": "feature/"
  },
  "ai": {
    "contextFiles": [
      "docs/CLAUDE.md",
      "docs/AI_COMPREHENSIVE_SYSTEM_GUIDE.md",
      ".claude/memories.md"
    ],
    "ignorePatterns": [
      "logs/**",
      "local_stats/**",
      "backups/**"
    ]
  }
}
```

### 🚀 Quick Wins

**Do these NOW:**
1. Clean up settings.local.json (remove wifi5/wifi8/rand loops)
2. Add system monitoring commands (systemctl, journalctl, tail)
3. Install gh CLI
4. Add filesystem MCP server

**Do later:**
5. Add git MCP server
6. Configure user preferences (model, mode defaults)
7. Consider web search MCP if you frequently look up docs

### 📝 Summary Scorecard

| Category | Status | Score |
|----------|--------|-------|
| MCP PostgreSQL | ✅ Working | 10/10 |
| Project Permissions | ✅ Good | 8/10 |
| Global Settings | ⚠️ Minimal | 5/10 |
| Development Tools | ⚠️ Missing gh | 7/10 |
| Security Isolation | ✅ Excellent | 10/10 |
| Permission Cleanup | ❌ Needs work | 4/10 |
| MCP Coverage | ⚠️ Could expand | 6/10 |
| **OVERALL** | **✅ Good** | **7.1/10** |

### 🎯 Action Plan

**Phase 1 (Today):**
1. Clean settings.local.json (5 min)
2. Add monitoring commands (5 min)
3. Install gh CLI (2 min)

**Phase 2 (This Week):**
4. Add filesystem MCP (10 min)
5. Add git MCP (10 min)
6. Configure user preferences (5 min)

**Phase 3 (Optional):**
7. Add web search MCP
8. Create project config.json
9. Set up automated permission backups
