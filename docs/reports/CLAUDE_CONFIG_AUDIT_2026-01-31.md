# Claude Configuration Audit Report
Date: 2026-01-31 12:20
Scope: All directories under ~/share

## Summary

Found 3 project-specific `.claude` directories:
1. slomix_discord (main bot project)
2. slomix_discord/website (web dashboard)
3. slomix_discord/proximity (proximity project)

IMPORTANT: This is BY DESIGN! Claude Code uses project-specific configs.

## Why Project-Specific Configs Are Good

Claude Code's design philosophy:
- Each project has its own permissions (security isolation)
- Different projects need different tools (website vs bot vs proximity)
- Prevents accidental cross-project contamination
- Allows per-project memories and settings

## Detailed Findings

### 1. Main Bot Project
Location: /home/samba/share/slomix_discord/.claude
Size: 32 KB
Files:
  - memories.md (20 KB) - Session notes and project context
  - settings.json (603 bytes) - Project permissions
  - settings.local.json (1.9 KB) - Extended permissions + MCP tools

Permissions:
  - Python/Git/Pip/Pytest operations
  - PostgreSQL database access
  - Screen session management
  - MCP database tools

Status: ✅ ACTIVE (current working directory)

### 2. Website Dashboard Project
Location: /home/samba/share/slomix_discord/website/.claude
Size: 8 KB
Files:
  - settings.local.json (280 bytes)

Permissions:
  - tree, python, grep, curl
  - screen sessions
  - PostgreSQL access (local database)

Status: ✅ Valid subproject config

### 3. Proximity Project
Location: /home/samba/share/slomix_discord/proximity/.claude
Size: 8 KB
Files:
  - settings.local.json (182 bytes)

Permissions:
  - nc (netcat) for proximity detection
  - PostgreSQL access to REMOTE database (192.168.64.116)

Status: ✅ Valid subproject config (note: remote DB)

### 4. Backup Directories (NOT active)
- /home/samba/klaudebackup/.claude (backup)
- /home/samba/backups/claude-config-20260131/.claude (backup)

Status: ℹ️ Archived backups, not active projects

## Global Configuration

Location: ~/.claude/
Size: 1.4 MB
Files:
  - mcp.json (252 bytes) - PostgreSQL MCP server
  - settings.json (98 bytes) - Global permissions (empty)
  - history.jsonl (3.7 KB) - Command history

Purpose: User-level defaults and MCP server configs

## Architecture Overview

```
Global Config (~/.claude/)
├── mcp.json ─────────────── Shared MCP servers (postgres)
├── settings.json ───────── User defaults
└── history.jsonl ──────── Command history

Project Configs
├── slomix_discord/.claude/
│   ├── memories.md ─────── Project-specific context
│   ├── settings.json ───── Bot project permissions
│   └── settings.local.json Bot + DB permissions
│
├── website/.claude/
│   └── settings.local.json Website permissions
│
└── proximity/.claude/
    └── settings.local.json Proximity + remote DB
```

## Centralization Analysis

What IS centralized:
✅ MCP server configs (~/.claude/mcp.json)
✅ User preferences (~/.claude/settings.json)
✅ Command history (~/.claude/history.jsonl)
✅ Authentication (~/.claude/.credentials.json)

What is NOT centralized (by design):
📁 Project permissions (.claude/settings.json per project)
📁 Project memories (.claude/memories.md per project)
📁 Project-specific MCP tools

## Recommendation: KEEP AS-IS

The current structure is correct and follows Claude Code best practices:

1. **Security**: Each project has isolated permissions
   - Bot can access PostgreSQL
   - Website has limited permissions
   - Proximity can access remote DB

2. **Flexibility**: Different tools per project
   - Bot: Full Python/Git/DB access
   - Website: Basic Python/Screen
   - Proximity: Network tools + remote DB

3. **Context**: Project memories stay with the project
   - slomix_discord has bot development notes
   - Website/proximity would have their own contexts

4. **No Bloat**: Each project config is tiny (8-32 KB)

## What You CAN Centralize

If you want to share permissions across projects:

Option 1: Symlink settings files
  cd ~/share/slomix_discord/website/.claude
  rm settings.local.json
  ln -s ../../.claude/settings.local.json .

Option 2: Use global defaults
  Add common permissions to ~/.claude/settings.json
  Projects inherit from global

Option 3: Shell script to sync
  Create a script to copy settings across projects

⚠️ WARNING: Centralizing permissions reduces security isolation!

## Total Storage Impact

All .claude directories combined:
- Main bot: 32 KB
- Website: 8 KB
- Proximity: 8 KB
- Global: 1.4 MB
- Total: ~1.45 MB

This is negligible - NOT a storage problem!

## Action Items

✅ Keep current structure (recommended)
❌ Do NOT centralize project configs
✅ Optionally: Add README.md to each .claude/ explaining purpose
✅ Optionally: Backup .claude/ dirs with project code

## Files to Monitor

Watch these for bloat (should stay small):
- ~/.claude/debug/ (clean monthly)
- ~/.claude/projects/ (archive old sessions)
- ~/.claude/history.jsonl (rotate when >100 KB)

Current status: All clean! ✅

## Conclusion

Your Claude configs are well-organized and follow best practices:
- Global configs: 1.4 MB (clean)
- Project configs: 48 KB total (minimal)
- No scattered debris
- Proper security isolation

No cleanup needed - system is healthy!
