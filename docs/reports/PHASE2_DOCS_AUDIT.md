# Phase 2: Documentation Audit Report

**Date**: 2026-02-23
**Auditor**: Documentation Auditor Agent
**Scope**: All 324 files in `docs/` tree (including subdirectories and archive)
**Method**: Parallel reads of all docs, README link analysis, content classification

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Full Doc Inventory with Status](#2-full-doc-inventory-with-status)
3. [AI/Claude Instruction Files — Move to docs/instructions/](#3-aiclaude-instruction-files--move-to-docsinstructions)
4. [Forgotten TODOs and Unimplemented Features](#4-forgotten-todos-and-unimplemented-features)
5. [Outdated, Redundant, or Contradictory Docs](#5-outdated-redundant-or-contradictory-docs)
6. [Docs Needed for README Links](#6-docs-needed-for-readme-links)
7. [Useful Patterns Extracted from Instruction Files](#7-useful-patterns-extracted-from-instruction-files)
8. [CHANGELOG and KNOWN_ISSUES Completeness Check](#8-changelog-and-known_issues-completeness-check)
9. [Recommendations Summary](#9-recommendations-summary)

---

## 1. Executive Summary

- **Total files counted**: 324 (including subdirs, archive, scripts, binary/docx files)
- **Unique Markdown/text docs**: ~260
- **Archive docs**: ~155 (all historical, no active value)
- **AI/Claude instruction files identified**: 11 (in `docs/` root) + 1 in archive
- **Forgotten TODOs / unimplemented features**: 7 significant items found
- **Stale/contradictory docs**: 15 identified
- **Docs required by README links**: 9

The docs folder has grown organically and contains a large volume of historical session logs, audit reports, handoff notes, and AI prompt files that are not project documentation. The `archive/` is enormous (~155 files) and mostly dead weight. The active `docs/` root has ~80 files of varying currency.

---

## 2. Full Doc Inventory with Status

Legend:
- **current** — actively used, accurate
- **reference** — accurate but low-traffic (design specs, tech refs)
- **stale** — content is outdated or superseded
- **redundant** — duplicates another doc
- **session-log** — one-time session summary, historical only
- **instruction-file** — AI/Claude/Codex prompt or launch card
- **archive-worthy** — should be in `docs/archive/` if not already

### docs/ Root (Active)

| File | Status | Notes |
|------|--------|-------|
| `ACHIEVEMENT_SYSTEM.md` | stale | Dated Oct 2025, refers to old architecture (v2.3+ bot, SQLite era). Superseded by CLAUDE.md and actual cog. |
| `ADVANCED_TEAM_DETECTION.md` | reference | Still relevant architecture doc |
| `AI_AGENT_EXEC_PROMPT_SYSTEM_LOG_AUDIT_2026-02-18.md` | instruction-file | AI agent execution prompt |
| `AI_AGENT_PROMPT_LAUNCH_CARD_v1.3.0.md` | instruction-file | AI agent launch card |
| `AI_AGENT_SYSTEM_AUDIT_MASTER_PROMPT.md` | instruction-file | Master audit prompt (active v1.3.0) |
| `AI_AGENT_SYSTEM_AUDIT_PROMPT_V2_2026-02-18.md` | instruction-file | Older version of audit prompt |
| `AI_AGENT_SYSTEM_AUDIT_RUN_LOG.md` | instruction-file | AI audit run log (3 runs logged) |
| `AI_COMPREHENSIVE_SYSTEM_GUIDE.md` | stale | Still referenced in CLAUDE.md but content is outdated — mentions "30s polling", "41 tables", "14 cogs", "63 commands". Reality is 60s, 68 tables, 21 cogs, 80+ commands. Needs update. |
| `AI_HANDOFF_HOME_AVAILABILITY_RETROVIZ_2026-02-18.md` | session-log | One-time handoff for availability/retroviz feature. Completed. |
| `ARCHITECTURE_ONBOARDING.md` | reference | Good onboarding doc, appears current |
| `AUDIT_2026-02-15_DOCS_AND_DEBT.md` | session-log | Point-in-time audit, historical |
| `AUDIT_2026-02-15_REPO_CLEANUP.md` | session-log | Point-in-time audit, historical |
| `AUDIT_BASELINE_SNAPSHOT_2026-02-19.md` | session-log | Audit artifact from RUN-001 |
| `AUDIT_DRIFT_MATRIX_2026-02-19.md` | session-log | Audit artifact from RUN-001 |
| `AUDIT_FINDINGS_CODE_QUALITY_2026-02-19.md` | session-log | Audit artifact from RUN-001 |
| `AUDIT_FINDINGS_SECURITY_2026-02-19.md` | session-log | Audit artifact from RUN-001 |
| `AUDIT_IMPLEMENTATION_PLAN_2026-02-19.md` | session-log | Audit artifact from RUN-001 |
| `AUDIT_PIPELINE_HEALTH_CHECKLIST_2026-02-19.md` | session-log | Audit artifact from RUN-001 |
| `AUDIT_REPRO_RELEASE_CHECKLIST_2026-02-19.md` | session-log | Audit artifact from RUN-001 |
| `AUDIT_SYSTEM_MAP_2026-02-19.md` | session-log | Audit artifact from RUN-001 |
| `AUTOMATION_CHECKLIST.md` | stale | Oct 2025 era, pre-PostgreSQL migration references |
| `AUTOMATION_SETUP_GUIDE.md` | stale | Oct 2025, "6+ players trigger", pre-VM era |
| `AVAILABILITY_SYSTEM.md` | reference | Current design doc for availability feature |
| `AVAILABILITY_UI.md` | reference | Current UI spec |
| `BRAINSTORM_SESSION_2026-02-21.md` | session-log | Brainstorm summary, see DATA_INGEST_QUEUE_DESIGN.md |
| `CHANGELOG.md` | current | Active, well-maintained |
| `CLAUDE.md` | current | Authoritative AI instructions (slightly stale — says v1.0.6, actual is v1.0.8) |
| `COMMAND_CHEAT_SHEET.md` | stale | Likely outdated (not read fully, check against COMMANDS.md) |
| `COMMANDS.md` | current | Active command reference |
| `COMPLETE_SYSTEM_RUNDOWN.md` | reference | Comprehensive; accuracy unknown without full read |
| `CONFIGURATION_REFERENCE.md` | reference | Config reference, appears current |
| `CONTRIBUTING.md` | current | Standard contribution guide |
| `DATA_INGEST_QUEUE_DESIGN.md` | reference | Design doc for queue system — NOT YET IMPLEMENTED |
| `DATA_INTEGRITY_VERIFICATION_POINTS.md` | reference | Safety verification points |
| `DATA_PIPELINE.md` | current | Linked from README, appears accurate |
| `DEEP_DIVE_AUDIT_2026-02-20.md` | session-log | Deep audit results; useful historical record |
| `DEPLOYMENT_CHECKLIST.md` | reference | Linked from README |
| `DEPLOYMENT_GUIDE.md` | stale | Dated 2025-11-17, specific branch name in title, outdated |
| `DEPLOYMENT_RUNBOOK.md` | reference | Appears current |
| `DEVELOPMENT_WORKFLOW.md` | reference | Dev workflow guide |
| `DISASTER_RECOVERY.md` | reference | DR plan |
| `DISCORD_LINKING_SETUP.md` | reference | Linking setup guide |
| `EDGE_CASES.md` | reference | Edge case documentation |
| `ET_LEGACY_SERVER_RESEARCH.md` | current | Added 2026-02-22, comprehensive game server research |
| `EXTERNAL_ACCESS_PLAN.md` | session-log | Plan was executed (Cloudflare tunnel live). Doc is now historical. |
| `FAIL2BAN_SETUP_2026-02-21.md` | reference | Still a plan/guide (PLAN status in doc) — may or may not be applied |
| `FEATURE_ROADMAP_2026.md` | reference | Active roadmap — contains unimplemented items (see Section 4) |
| `FIELD_MAPPING.md` | current | Field mapping reference |
| `FRESH_INSTALL_GUIDE.md` | reference | Linked from README |
| `FUTURE_SCALING_GUIDE.md` | reference | Forward-looking scalability notes |
| `GAMESERVER_CLAUDE.md` | current | Game server AI context file |
| `GET_READY_SOUND.md` | reference | Feature doc for sound trigger |
| `GRAPH_DESIGN_GUIDE.md` | stale | Nov 2025, pre-Chart.js SPA era. Matplotlib-era. |
| `INFRA_HANDOFF_2026-02-18.md` | reference | Referenced from CLAUDE.md. Historical but still read by agents. |
| `KILL_ASSISTS_VISIBILITY_IMPLEMENTATION_PLAN_2026-02-12.md` | session-log | Plan doc; marked as executed |
| `KNOWN_ISSUES.md` | current | Active issues tracker — well maintained |
| `LAPTOP_DEPLOYMENT_GUIDE.md` | stale | Pre-VM era, laptop-specific |
| `LAPTOP_MIGRATION_GUIDE.md` | stale | Pre-VM era |
| `LINKING_ACCOUNTS.md` | reference | Account linking user guide |
| `LINUX_DEPLOYMENT_GUIDE.md` | reference | Linux deployment steps |
| `LINUX_SETUP_README.md` | stale | Older setup guide, likely superseded |
| `LIVE_MONITORING_GUIDE.md` | reference | Live monitoring protocol |
| `LUA_R2_MISSING_ROOT_CAUSE_2026-02-18.md` | session-log | Root cause doc, issue resolved |
| `LUA_TIMING_AND_TEAM_DISPLAY_IMPLEMENTATION_PLAN.md` | session-log | Superseded notice at top. Historical. |
| `LUA_WEBHOOK_SETUP.md` | reference | Lua webhook setup guide |
| `MEGA_CLEANUP_AND_HARDENING_PROMPT.md` | instruction-file | AI execution prompt for this mega cleanup |
| `NOTIFICATIONS_DISCORD.md` | reference | Notification system docs |
| `NOTIFICATIONS_LINKING.md` | reference | Notification linking docs |
| `NOTIFICATIONS_SIGNAL.md` | reference | Signal notification docs |
| `NOTIFICATIONS_TELEGRAM.md` | reference | Telegram notification docs |
| `OMNIBOT_PROJECT.md` | reference | DRY RUN PLAN — not implemented |
| `PIPELINE_DEEP_DIVE_HANDOFF_2026-02-18.md` | session-log | Handoff doc, investigation complete |
| `PIPELINE_TIMETRACKING_GAP_ANALYSIS.md` | reference | Time-tracking gap analysis, feeds into KNOWN_ISSUES plan |
| `PIPELINE_TIMETRACKING_NEXT_STEPS_PLAN.md` | reference | Plan for time-tracking improvement |
| `PIPELINE_TIMETRACKING_RESEARCH_SYNTHESIS.md` | reference | Research synthesis for time-tracking |
| `PLANNING_ROOM.md` | reference | Planning room feature spec (duplicate of PLANNING_ROOM_MVP.md) |
| `PLANNING_ROOM_MVP.md` | reference | Same content as PLANNING_ROOM.md — exact duplicate |
| `POSTGRESQL_MIGRATION_GUIDE.md` | stale | Migration is done; guide is historical |
| `POSTGRESQL_MIGRATION_IMPLEMENTATION_GUIDE.md` | stale | Same — migration complete |
| `POSTGRESQL_MIGRATION_INDEX.md` | reference | Referenced in CLAUDE.md |
| `POSTGRESQL_SQL_COMPATIBILITY_REFERENCE.md` | reference | Still useful SQLite-vs-PostgreSQL reference |
| `PRODUCTION_AUTOMATION_GUIDE.md` | reference | Production automation reference |
| `PROJECT_HISTORY.md` | reference | Historical project narrative |
| `PROJECT_HISTORY_APPENDIX.md` | reference | Appendix to project history |
| `PROJECT_OVERVIEW.md` | reference | High-level overview |
| `PROMOTE_CAMPAIGNS.md` | reference | Promote campaigns feature spec |
| `PROMOTIONS_SYSTEM.md` | reference | Promotions system spec |
| `PROXIMITY_CLAUDE.md` | current | Pointer doc to proximity/docs/ — current |
| `PROXIMITY_CLOSEOUT_2026-02-19.md` | session-log | Proximity sprint closeout |
| `PROXIMITY_ETL_LUA_CAPABILITIES_2026-02-19.md` | reference | Proximity ETL capabilities doc |
| `PROXIMITY_IMPROVEMENT_DIRECTION_2026-02-19.md` | reference | Improvement direction doc |
| `PROXIMITY_WEB_BENCHMARK_IDEAS_2026-02-19.md` | reference | Benchmark ideas |
| `QUEUE_SYSTEM_BRAINSTORM_README.md` | reference | Index to queue system docs — NOT YET IMPLEMENTED |
| `QUICK_FIX_GUIDE.md` | reference | Quick fix reference |
| `R2_ENDSTATS_ACHIEVEMENTS_INVESTIGATION_2026-02-18.md` | session-log | Investigation complete |
| `R2_ENDSTATS_DELEGATION_CHECKLIST_2026-02-18.md` | session-log | Delegation checklist, historical |
| `ROAD_AHEAD_EXECUTION_RUNBOOK_2026-02-12.md` | session-log | Sprint runbook, sprint complete |
| `ROUND_2_PIPELINE_EXPLAINED.txt` | current | Linked from README |
| `RUNBOOK.md` | reference | Ops runbook |
| `RUNBOOK_LOCAL_LINUX.md` | reference | Local Linux runbook |
| `SAFETY_VALIDATION_SYSTEMS.md` | current | Linked from README (garbled encoding — file appears binary-corrupted) |
| `SEASON_SYSTEM.md` | stale | Oct 2025, pre-PostgreSQL era references |
| `SECRETS_MANAGEMENT.md` | reference | Secrets management guide |
| `SERVER_CONTROL_INSTALL.md` | reference | Server control installation |
| `SERVER_CONTROL_QUICK_REF.md` | reference | Server control quick reference |
| `SERVER_CONTROL_SETUP.md` | reference | Server control setup |
| `SESSION_2026-02-05_SEASON_SUMMARY_LEADERS_POLISH.md` | session-log | Session log, changes complete |
| `SESSION_LOG_2026-02-22.md` | session-log | Session log for Feb 22 work |
| `STATS_FORMULA_RESEARCH.md` | reference | Research findings, feeds DEEP_DIVE_AUDIT |
| `STATS_GROUPING_GUIDE.md` | reference | Stats grouping reference |
| `STOPWATCH_IMPLEMENTATION.md` | session-log | Implementation complete, marked done |
| `SUBSTITUTION_DETECTION.md` | reference | Substitution detection doc |
| `SUPER_PROMPT_2026-02-20.md` | instruction-file | 970-line master fix-it AI prompt |
| `SYSTEM_ARCHITECTURE.md` | reference | Architecture reference |
| `SYSTEM_AUDIT_2026-02-21.md` | reference | Data coordination audit — issues partially addressed (round_correlations now exists) |
| `SYSTEM_LOG_AUDIT_DELEGATION_CHECKLIST_2026-02-18.md` | session-log | Delegation checklist, complete |
| `SYSTEM_LOG_AUDIT_FINDINGS_2026-02-18.md` | session-log | Findings doc, issues resolved |
| `SYSTEM_UNDERSTANDING.md` | stale | Appears older/redundant with AI_COMPREHENSIVE_SYSTEM_GUIDE |
| `TEAM_AND_SCORING.md` | reference | Team and scoring design |
| `TECHNICAL_OVERVIEW.md` | reference | Technical overview |
| `TESTING_GUIDE.md` | reference | Testing guide |
| `TIMING_SHADOW_HANDOFF_2026-02-18.md` | session-log | Timing shadow investigation handoff |
| `TWO_WEEK_CLOSEOUT_PLAN_2026-02-11.md` | session-log | Sprint plan, sprint complete |
| `TWO_WEEK_CLOSEOUT_REPORT_2026-02-16.md` | session-log | Sprint closeout report, complete |
| `TWO_WEEK_EXECUTION_TRACKER_2026-02-11.md` | session-log | Sprint tracker, all 43 tasks done |
| `TWO_WEEK_LIVE_MONITOR_MISSION_2026-02-18.md` | session-log | 14-day monitor mission (ends 2026-03-03) — still active window |
| `UPLOAD_SECURITY.md` | reference | Upload security documentation |
| `VM_ACCESS.md` | reference | VM access guide |
| `VM_AUDIT_REPORT_2026-02-20.md` | reference | VM audit report |
| `VM_FIREWALL_RULES_2026-02-20.md` | reference | Firewall rules doc (PLAN status — not applied yet) |
| `VM_MIGRATION_REPORT_2026-02-20.md` | reference | VM migration report |
| `VPS_DEPLOYMENT_GUIDE.md` | reference | VPS deployment guide |
| `WEBHOOK_TRIAGE_CHECKLIST_2026-02-11.md` | session-log | Triage checklist, sprint complete |
| `WEBSITE_CLAUDE.md` | current | Website AI context — note says "Move to website/CLAUDE.md after permissions restart" (TODO) |
| `WS1_R2_MISSING_INVESTIGATION_2026-02-18.md` | session-log | Investigation complete (R2 rejection fix applied) |
| `workfile.md` | instruction-file | Paste-ready Codex/Claude prompt for availability + promote system |

### docs/archive/ (~155 files)

All archive files are historical session logs, completion summaries, and early-era design docs (Oct–Nov 2025). None are actively referenced from README or CLAUDE.md. They document the project's evolution from SQLite → PostgreSQL, early bot versions, and pre-production work. All can remain in archive indefinitely. Notable ones:

| File | Notes |
|------|-------|
| `COPILOT_INSTRUCTIONS_OLD.md` | Oct 2025 GitHub Copilot instructions — replaced by CLAUDE.md |
| `VPS_MIGRATION_PROMPT.md` | AI prompt for old SQLite→PostgreSQL migration — historical |
| `lol.md` | Empty/joke file |
| `TODO_SPRINT.md` | Old sprint TODO, historical |
| `IMPLEMENTATION_ROADMAP.md` | Old roadmap, superseded |
| `PERFORMANCE_UPGRADES_ROADMAP.md` | Old roadmap, superseded |

### docs/reports/

| File | Status | Notes |
|------|--------|-------|
| `AVAILABILITY_PROMPT_COMPLETION_REPORT_2026-02-19.md` | session-log | Completion report |
| `AVAILABILITY_V2_CONTEXT_COMPACT_2026-02-19.md` | session-log | Context handoff |
| `C0RNP0RN7_DEVELOPER_REPORT_2026-02-19.md` | reference | Lua developer research |
| `CLAUDE_RESTORATION_SUMMARY_2026-01-31.md` | session-log | Claude config restoration |
| `deep-research-report.md` / `.docx` / `.pdf` | reference | Industry baseline research (referenced from FEATURE_ROADMAP_2026) |
| `deep-research-report2.md` / `.docx` | reference | Follow-up research |
| `LINE_BY_LINE_AUDIT_CLOSED_OPEN_MATRIX_2026-02-19.md` | session-log | Audit complete |
| `LINE_BY_LINE_AUDIT_PATCH_REPORT_2026-02-19.md` | session-log | Patch report |
| `LIVE_PIPELINE_AUDIT_2026-02-18.md` | session-log | Pipeline audit |
| `MEGA_PROMPT_NEXT_STAGE_CHECKLIST_2026-02-19.md` | session-log | All stages complete |
| `NIGHTLY_FINDINGS_SNAPSHOT_2026-02-18.md` | session-log | Nightly snapshot |
| `PR37_STABILIZATION_FINDINGS_2026-02-18.md` | session-log | PR stabilization |
| `RESTART_HANDOVER_AVAILABILITY_2026-02-19.md` | session-log | Handover |
| `SHOP_CLOSE_HANDOVER_AVAILABILITY_2026-02-19.md` | session-log | Handover |
| `TIMING_SHADOW_INVESTIGATION_2026-02-18.md` | session-log | Investigation |
| `stage4_live_verification.sh` | reference | Shell script for live verification |

### docs/reference/

| File | Status | Notes |
|------|--------|-------|
| `CLAUDE_CODE_QUICK_REFERENCE.md` | stale | Jan 2026, mentions "14 cogs", old model names, outdated settings paths |
| `TIMING_DATA_SOURCES.md` | current | Linked from README |
| `c0rnp0rn7_prepatch_from_git_history.lua` | reference | Lua source reference |
| `c0rnp0rn7_prepatch_vs_current.diff` | reference | Diff file |
| `live_sync_backups/` | reference | Pre-sync Lua backups |
| `oksii-game-stats-web.lua` | reference | External reference Lua script |

### docs/evidence/

| File | Status |
|------|--------|
| `2026-02-16_ws1_live_session.md` | session-log — live session evidence |

### docs/research/

| File | Status |
|------|--------|
| `README.md` | reference — research intake process |
| `inbox/RESEARCH_INBOX_2026-02-19_chatgpt.md` | session-log — validated and promoted |
| `validated/RESEARCH_VALIDATED_2026-02-19_CHATGPT.md` | session-log — incorporated into master prompt |

### docs/2026-01-30-r2-parser-fix/ and docs/scripts_2026-01-30_r2_fix/

Both contain duplicate copies of the same scripts from a historical R2 parser fix session. These are redundant with each other.

| File | Status |
|------|--------|
| `reports/*.md` | session-log — historical R2 fix session reports |
| `scripts/` | reference — fix scripts, historical |

---

## 3. AI/Claude Instruction Files — Move to docs/instructions/

The following files are **operational AI/Claude/Codex prompts**, not project documentation. They should be moved to `docs/instructions/` to separate them from the project docs.

### Files to Move (docs/ root)

| File | Description |
|------|-------------|
| `AI_AGENT_EXEC_PROMPT_SYSTEM_LOG_AUDIT_2026-02-18.md` | Execution agent prompt for system log audit follow-up |
| `AI_AGENT_PROMPT_LAUNCH_CARD_v1.3.0.md` | Launch card for mega audit prompt |
| `AI_AGENT_SYSTEM_AUDIT_MASTER_PROMPT.md` | Master audit prompt (versioned, active) |
| `AI_AGENT_SYSTEM_AUDIT_PROMPT_V2_2026-02-18.md` | Version 2 of audit prompt (superseded by master) |
| `AI_AGENT_SYSTEM_AUDIT_RUN_LOG.md` | Run log for audit prompt executions |
| `MEGA_CLEANUP_AND_HARDENING_PROMPT.md` | Mega cleanup execution prompt (this phase) |
| `SUPER_PROMPT_2026-02-20.md` | 970-line master fix-it prompt synthesized from 51 docs |
| `workfile.md` | Paste-ready Codex/Claude prompt for availability system |

### Files to Move (docs/archive/)

| File | Description |
|------|-------------|
| `COPILOT_INSTRUCTIONS_OLD.md` | Old GitHub Copilot instructions |
| `VPS_MIGRATION_PROMPT.md` | AI prompt for old VPS migration |

### Files with AI Instruction Content — Keep in Place (They Double as Project Docs)

| File | Reason to Keep |
|------|----------------|
| `AI_COMPREHENSIVE_SYSTEM_GUIDE.md` | Also serves as system reference for humans. Keep, but update. |
| `AI_HANDOFF_HOME_AVAILABILITY_RETROVIZ_2026-02-18.md` | More handoff doc than prompt |
| `PROXIMITY_CLAUDE.md` | Active CLAUDE.md pointer for proximity subproject |
| `WEBSITE_CLAUDE.md` | Active CLAUDE.md pointer for website subproject |
| `GAMESERVER_CLAUDE.md` | Active CLAUDE.md for game server |
| `CLAUDE.md` | This IS the primary AI instruction file — keep in docs/ |

---

## 4. Forgotten TODOs and Unimplemented Features

### 4.1 CRITICAL — Lua Time Stats Overhaul (KNOWN_ISSUES.md)

**Status**: Not started — planning phase
**Doc**: `docs/KNOWN_ISSUES.md` (top section, very detailed)
**Scope**: 10-step plan spanning Lua, database, bot parser, bot commands, website backend, website frontend
**Impact**: Per-player time tracking (time_alive_ms, time_dead_ms, denied_playtime_ms, spawn_count, etc.) — currently lost or inaccurate
**What's needed**: New Lua tracking hooks, new `-timestats.txt` file format, 8 new DB columns, new parser class, 10+ file modifications

### 4.2 HIGH — VM Firewall Rules Not Applied

**Status**: Plan documented, NOT applied
**Doc**: `docs/VM_FIREWALL_RULES_2026-02-20.md`
**Issue**: UFW is installed but INACTIVE on production VM. All ports accessible from LAN. SSH (port 22) open to everything. Only protection is app services binding to 127.0.0.1.

### 4.3 HIGH — Fail2Ban Setup Not Applied

**Status**: Plan documented (PLAN status in doc), not applied
**Doc**: `docs/FAIL2BAN_SETUP_2026-02-21.md`
**Issue**: No SSH brute-force protection on production VM.

### 4.4 MEDIUM — Data Ingest Queue System (Not Implemented)

**Status**: Design phase only
**Docs**: `docs/DATA_INGEST_QUEUE_DESIGN.md`, `docs/QUEUE_SYSTEM_BRAINSTORM_README.md`, `docs/SYSTEM_AUDIT_2026-02-21.md`
**Issue**: System has 4 data sources (gamestats, endstats, gametimes, proximity) with no coordination. The round_correlations table was added (2026-02-22) as first step, but the full queue-based ingest system is still not built. Brainstorm docs identify 5 critical data coordination failures.

### 4.5 MEDIUM — Stats Formula Inconsistencies (Open Items)

**Status**: Research done, fixes not applied
**Docs**: `docs/STATS_FORMULA_RESEARCH.md`, `docs/DEEP_DIVE_AUDIT_2026-02-20.md`
**Issues confirmed**:
- Website uses completely wrong formulas for FragPotential, Survival Rate, and Damage Efficiency (different from bot)
- Headshot % uses mixed formulas across codebase
- `time_played_seconds` uses round duration for all players (wrong for partial players)

### 4.6 MEDIUM — Availability Page UI/UX Overhaul (KNOWN_ISSUES.md)

**Status**: Open — design rethink needed
**Doc**: `docs/KNOWN_ISSUES.md` (Website UI Bugs section)
**Issue**: Availability page feels empty and uninviting. 6 specific UX problems documented. No implementation started.

### 4.7 MEDIUM — Upload Library Issues (3 bugs, KNOWN_ISSUES.md)

**Status**: Open (root causes identified for 2 of 3)
**Doc**: `docs/KNOWN_ISSUES.md`
- **"Watch" button broken**: No fix attempted yet
- **"Download" streams instead of downloading**: Root cause identified (`Content-Disposition: inline` in `uploads.py:376`). Fix not applied.
- **"Share" opens video player**: Design decision needed

### 4.8 LOW — Prometheus Monitoring Not Functional

**Status**: Open
**Doc**: `docs/KNOWN_ISSUES.md` (VM Migration Remaining Items)
**Issue**: Code scaffolding exists but `prometheus_client` not installed. Uses noop counters.

### 4.9 LOW — matplotlib Config Issue

**Status**: Open
**Doc**: `docs/KNOWN_ISSUES.md` (VM Migration Remaining Items)
**Issue**: `/opt/slomix/.config` is read-only due to systemd sandboxing. Add `MPLCONFIGDIR=/tmp/matplotlib_cache` to `.env`.

### 4.10 LOW — HTTP→HTTPS Redirect Missing

**Status**: Open
**Doc**: `docs/KNOWN_ISSUES.md`
**Issue**: `http://www.slomix.fyi` bypasses Cloudflare. `slomix.fyi` apex domain has no A record.

### 4.11 PLANNED — Proximity Reaction Time Intel (FEATURE_ROADMAP_2026.md)

**Status**: Planned, not started (requires Lua changes)
**Doc**: `docs/FEATURE_ROADMAP_2026.md`
**Issue**: New metrics (`time_to_return_fire_ms`, `dodge_reaction_ms`, `teammate_support_reaction_ms`) need Lua hooks and DB columns.

### 4.12 PLANNED — Proximity UX Improvements (FEATURE_ROADMAP_2026.md)

**Status**: Planned, partially started
**Doc**: `docs/FEATURE_ROADMAP_2026.md`
**Issues**: Rename "Fastest Reaction" label, add ELI5 explanations, add engagement inspector legend, pagination for engagements table.

### 4.13 PLANNED — Infrastructure (FEATURE_ROADMAP_2026.md)

**Status**: Partially done (CI exists, but no dependency lockfile, no pre-commit hooks, no Dependabot)
**Doc**: `docs/FEATURE_ROADMAP_2026.md`
- CI/CD pipeline: partial (GitHub Actions exists, tests added)
- Dependency lockfile (`pip-compile`): NOT done
- Pre-commit hooks: NOT done
- Dependabot: NOT done
- Systemd hardening: NOT done
- Bot core decomposition (`ultimate_bot.py` ~5000 lines): NOT done

### 4.14 PLANNED — OmniBot (OMNIBOT_PROJECT.md)

**Status**: DRY RUN PLAN — no server changes made, not implemented
**Doc**: `docs/OMNIBOT_PROJECT.md`
**Purpose**: AI-controlled players for pipeline testing

### 4.15 NOTE — Round Correlation Service (CHANGELOG.md)

**Status**: Implemented (2026-02-22) but starts in DRY-RUN mode
**Doc**: `docs/CHANGELOG.md`
**Action needed**: Flip `dry_run=False` in `round_correlation_service.py` after verification week. This is an open TODO hidden in CHANGELOG.

### 4.16 NOTE — WEBSITE_CLAUDE.md

**Status**: File says "Move to `website/CLAUDE.md` after permissions restart"
**Action needed**: Move this file to `website/CLAUDE.md` — has not been done.

---

## 5. Outdated, Redundant, or Contradictory Docs

### 5.1 Stale Stats in CLAUDE.md

`CLAUDE.md` (root) says version 1.0.6, but README and CHANGELOG say 1.0.8. Schema says "68 tables, 56 columns" but VM audit found 67 tables; README says 37 tables; SUPER_PROMPT says 41 tables. The actual table count should be verified from DB.

### 5.2 AI_COMPREHENSIVE_SYSTEM_GUIDE.md — Significantly Stale

This file is referenced in CLAUDE.md as "DO read before claiming bugs" but contains major inaccuracies:
- "14 cogs" (reality: 21)
- "41 tables, 53+ columns" (reality: 67-68 tables, 56 columns)
- "63 commands across 6 categories" (reality: 80-99 commands across 21 cogs)
- "30-second polling" (reality: 60-second)
- "30-second polling" SSH Monitor description

**Recommendation**: Update or replace with current data, or add a deprecation notice pointing to CLAUDE.md.

### 5.3 PLANNING_ROOM.md = PLANNING_ROOM_MVP.md (Exact Duplicate)

Both files contain identical content. One should be deleted.

### 5.4 DEPLOYMENT_GUIDE.md — Branch-Specific, Stale

Title includes a specific feature branch name from Nov 2025. Content is specific to a single deployment event. Should be in archive.

### 5.5 AUTOMATION_SETUP_GUIDE.md and AUTOMATION_CHECKLIST.md — Pre-PostgreSQL Era

Both date from Oct 2025. Reference old architecture, old command thresholds ("6+ players"), pre-VM setup. Should be archived.

### 5.6 GRAPH_DESIGN_GUIDE.md — Matplotlib Era

Nov 2025, references matplotlib graph generation. Website now uses Chart.js. Content is historical.

### 5.7 SEASON_SYSTEM.md and ACHIEVEMENT_SYSTEM.md — Oct 2025, Pre-PostgreSQL

Both reference very old architecture. Content may still be partially valid but unverified.

### 5.8 Duplicate R2-fix Scripts

`docs/2026-01-30-r2-parser-fix/` and `docs/scripts_2026-01-30_r2_fix/` appear to contain duplicate or near-duplicate historical scripts from the same fix session. The `docs/` root already has `scripts_2026-01-30_r2_fix/` — the nested `2026-01-30-r2-parser-fix/` is a redundant copy.

### 5.9 SAFETY_VALIDATION_SYSTEMS.md — File Encoding Corrupted

The file reads as garbled wide-character encoding (appears to have been saved in UTF-16 or similar). Content is unreadable. This file is linked from README — needs to be fixed.

### 5.10 CLAUDE_CODE_QUICK_REFERENCE.md — Stale

In `docs/reference/`. Dated Jan 2026, mentions "14 cogs", old model names (`claude-opus-4-5-20251101`), outdated settings paths, old `!ping`/`!health` command syntax.

### 5.11 Table Count Discrepancy

README says 37 tables, CLAUDE.md says 68 tables, SUPER_PROMPT says 41 tables, VM audit found 67 tables. This reflects different snapshots in time. The actual number should be queried from DB and all docs synced.

### 5.12 SSH Polling Interval Discrepancy

`AI_COMPREHENSIVE_SYSTEM_GUIDE.md` says 30-second SSH polling. CLAUDE.md architecture diagram says 60s poll. The actual value in code should be verified (CLAUDE.md says 60s, which appears correct).

### 5.13 LAPTOP_DEPLOYMENT_GUIDE.md, LAPTOP_MIGRATION_GUIDE.md

Pre-VM era laptop-specific guides. No longer relevant to production setup.

### 5.14 POSTGRESQL_MIGRATION_GUIDE.md, POSTGRESQL_MIGRATION_IMPLEMENTATION_GUIDE.md

Migration is long complete (production runs PostgreSQL). These are historical records. They could be archived.

---

## 6. Docs Needed for README Links

README.md links to the following doc files that **must remain Git-tracked**:

| README Link | File | Status |
|-------------|------|--------|
| `docs/DATA_PIPELINE.md` | `docs/DATA_PIPELINE.md` | current — keep |
| `docs/SAFETY_VALIDATION_SYSTEMS.md` | `docs/SAFETY_VALIDATION_SYSTEMS.md` | CORRUPTED — fix encoding urgently |
| `docs/ROUND_2_PIPELINE_EXPLAINED.txt` | `docs/ROUND_2_PIPELINE_EXPLAINED.txt` | current — keep |
| `docs/reference/TIMING_DATA_SOURCES.md` | `docs/reference/TIMING_DATA_SOURCES.md` | current — keep |
| `docs/COMMANDS.md` | `docs/COMMANDS.md` | current — keep |
| `CHANGELOG.md` (root, not docs/) | `CHANGELOG.md` | current — keep |
| `docs/CLAUDE.md` | `docs/CLAUDE.md` | current — keep |
| `docs/DEPLOYMENT_CHECKLIST.md` | `docs/DEPLOYMENT_CHECKLIST.md` | reference — keep |
| `docs/FRESH_INSTALL_GUIDE.md` | `docs/FRESH_INSTALL_GUIDE.md` | reference — keep |

**All other docs** can potentially be gitignored if desired (Phase 5 task). The following are referenced from CLAUDE.md (not README) and should also stay tracked:

| CLAUDE.md Reference | File |
|--------------------|------|
| `docs/AI_COMPREHENSIVE_SYSTEM_GUIDE.md` | Needs update before relying on |
| `docs/KNOWN_ISSUES.md` | current |
| `docs/POSTGRESQL_MIGRATION_INDEX.md` | keep |
| `docs/INFRA_HANDOFF_2026-02-18.md` | keep |
| `docs/reference/TIMING_DATA_SOURCES.md` | keep |

---

## 7. Useful Patterns Extracted from Instruction Files

### From `AI_AGENT_SYSTEM_AUDIT_MASTER_PROMPT.md` (v1.3.0)

**Source Precedence Rule** (critical for avoiding stale doc errors):
> When docs/code/runtime disagree, use: Runtime evidence > Code behavior > Tier 1 docs > Tier 2 docs > Archive docs

**External Research Intake Protocol**: Before merging any ChatGPT/external AI research, split into atomic claims, classify by type, validate each with 2-3 independent local sources, mark as verified/partially-verified/unverified/false. Only promote verified claims.

**Run Log Pattern**: Every audit run should update `Last Run UTC`, `Last Run Outcome`, `Last Run Branch`, `Last Run Commit SHA` and increment `Run Counter` in the master prompt file.

**Discovery Carry-Forward**: Useful pattern — maintain a living section in audit docs with dated discoveries and their evidence locations.

### From `SUPER_PROMPT_2026-02-20.md`

**Verification Notes Pattern**: "Line numbers, formulas, and file paths have been verified against the actual codebase by 5 parallel verification agents." This meta-verification step prevents phantom bugs.

**Issue Registry Format**: The master issue registry with priority, file, line, status, and evidence fields is a valuable pattern for tracking technical debt.

### From `workfile.md` (Availability Codex prompt)

**Operating Principles** worth adding to CLAUDE.md:
- "Assume everything is broken first. First job is to get the project running locally with zero errors."
- "Idempotent + rate-limited: Every scheduled/notification action must be safe to retry and never double-send."
- "Opt-in only: Do not message users unless they explicitly opted in."

### From `AI_AGENT_SYSTEM_AUDIT_RUN_LOG.md`

**Audit Run Pattern**: Gate A (audit only, no code changes) → Gate B (approved P0/P1 subset implementation). This two-gate approach prevents scope creep.

### From `AI_COMPREHENSIVE_SYSTEM_GUIDE.md`

**Critical Rules** (already in CLAUDE.md but worth confirming):
- Always use `gaming_session_id` for sessions (not dates)
- Always group by `player_guid` (not `player_name`)
- Always use 60-minute gap threshold (not 30!)
- Never recalculate R2 differential

### From `MEGA_CLEANUP_AND_HARDENING_PROMPT.md`

**Folder CLAUDE.md Rule**: "Every meaningful folder should have one" — this suggests adding CLAUDE.md files to `bot/`, `website/`, `greatshot/`, `proximity/` subdirectories that don't already have them.

---

## 8. CHANGELOG and KNOWN_ISSUES Completeness Check

### CHANGELOG.md

**Verdict: Well-maintained and current.**

- Last entry: 2026-02-22 (Round Correlation System, ET:Legacy Server Research, match_id fix)
- Covers all major versions (v1.0.3 through v1.0.8) with detail
- Fixed items properly noted
- One hidden TODO: `dry_run=False` flip for round_correlation_service (noted in [Unreleased] section)
- Minor inconsistency: README badge says v1.0.8 but CLAUDE.md says v1.0.6

### KNOWN_ISSUES.md

**Verdict: Well-structured and current. Could add a few items.**

**Strengths**:
- Clear severity labels and dates
- Resolved items properly marked with RESOLVED/FIXED labels
- Links to investigation docs

**Missing / not yet tracked**:
1. Stats formula inconsistencies (from DEEP_DIVE_AUDIT and STATS_FORMULA_RESEARCH) — not in KNOWN_ISSUES
2. Dependency lockfile / pre-commit hooks / Dependabot missing — not tracked
3. `SAFETY_VALIDATION_SYSTEMS.md` file encoding corruption
4. `PLANNING_ROOM.md` duplicate of `PLANNING_ROOM_MVP.md`
5. Round Correlation Service still in dry-run mode (needs flip)

---

## 9. Recommendations Summary

### Immediate Actions

| Priority | Action | Effort |
|----------|--------|--------|
| CRITICAL | Fix `SAFETY_VALIDATION_SYSTEMS.md` encoding corruption (linked from README) | Low |
| HIGH | Move 8 instruction files to `docs/instructions/` subfolder | Low |
| HIGH | Update `CLAUDE.md` version from 1.0.6 to 1.0.8 | Low |
| HIGH | Update `AI_COMPREHENSIVE_SYSTEM_GUIDE.md` or add deprecation notice (wrong cog/table/command counts) | Medium |
| HIGH | Apply firewall rules (`VM_FIREWALL_RULES_2026-02-20.md`) | Medium |
| HIGH | Apply fail2ban setup (`FAIL2BAN_SETUP_2026-02-21.md`) | Medium |
| MEDIUM | Delete `PLANNING_ROOM.md` (exact duplicate of `PLANNING_ROOM_MVP.md`) | Low |
| MEDIUM | Move `WEBSITE_CLAUDE.md` to `website/CLAUDE.md` (file itself says to do this) | Low |
| MEDIUM | Archive `DEPLOYMENT_GUIDE.md`, `AUTOMATION_SETUP_GUIDE.md`, `AUTOMATION_CHECKLIST.md`, `GRAPH_DESIGN_GUIDE.md`, `LAPTOP_DEPLOYMENT_GUIDE.md`, `LAPTOP_MIGRATION_GUIDE.md` | Low |
| MEDIUM | Flip `dry_run=False` in `round_correlation_service.py` after verification | Low |
| LOW | Fix Upload Library "Download" bug (`Content-Disposition: inline` → `attachment`) | Low |
| LOW | Add `MPLCONFIGDIR=/tmp/matplotlib_cache` to VM `.env` | Low |
| LOW | Consolidate duplicate R2-fix script dirs (keep `scripts_2026-01-30_r2_fix/`, remove nested `2026-01-30-r2-parser-fix/`) | Low |
| LOW | Update `reference/CLAUDE_CODE_QUICK_REFERENCE.md` cog/table counts | Low |

### For .gitignore (Phase 5)

Candidates to gitignore (can live on Samba but not in Git):
- `docs/archive/` (155 historical files, no README links)
- `docs/reports/` (session-log reports, no README links — except keep `PHASE2_DOCS_AUDIT.md` and similar mega-cleanup reports)
- `docs/evidence/` (one file, session log)
- `docs/research/` (validated research, no README links)
- `docs/2026-01-30-r2-parser-fix/` (redundant with scripts_2026-01-30_r2_fix/)
- Individual session-log files in docs/ root (see table above)

### For CLAUDE.md Updates

Suggested additions:
```md
## Source Precedence Rule
When docs, code, and runtime disagree:
Runtime evidence > Code behavior > Tier 1 docs > Tier 2 docs > Archive docs

## External Research Protocol
Before acting on ChatGPT/external AI research:
1. Split into atomic claims
2. Validate each with 2-3 independent local sources
3. Only promote verified claims to CLAUDE.md

## Data Ingest Queue (Planned)
System has 4 data sources with no coordination (see docs/DATA_INGEST_QUEUE_DESIGN.md).
round_correlations table exists (2026-02-22) but full queue system not yet built.
```

### For .claude/memories.md Updates

Suggested additions:
- Round Correlation Service is in dry-run mode — flip after verification week
- `WEBSITE_CLAUDE.md` needs to move to `website/CLAUDE.md`
- `SAFETY_VALIDATION_SYSTEMS.md` has encoding corruption — needs fix before README link works
- Stats formula inconsistencies: website uses wrong formulas for FragPotential, Survival Rate, Damage Efficiency vs bot
- VM firewall and fail2ban are planned but not yet applied

---

*Report generated: 2026-02-23 | Files reviewed: 324 | Time: Full parallel audit*
