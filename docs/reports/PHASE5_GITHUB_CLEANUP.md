# Phase 5: GitHub Repository Cleanup Plan

**Generated**: 2026-02-23
**Based on**: Phase 3 Architecture Map (`docs/reports/PHASE3_ARCHITECTURE_MAP.md`)
**Current tracked file count**: 502 files
**Target tracked file count**: ~420-440 files (remove ~60-80 files from tracking)

> **SAFETY RULE**: This document is a PLAN ONLY. No git rm commands should be run until
> the user reviews and approves. All local files remain untouched on disk.

---

## Part 1: Proposed .gitignore (Full Content — Ready to Copy-Paste)

This replaces the current `.gitignore`. It consolidates and extends the existing rules,
fixes gaps, and adds patterns for files that are currently tracked but should not be.

```gitignore
# ============================================
# ET:LEGACY DISCORD BOT - GITIGNORE v2.0
# ============================================
# Philosophy: Track source code, config templates, docs, CI.
# Never track: secrets, backups, logs, generated outputs, dev scratch files.
# Files already tracked need: git rm --cached <file>
# ============================================

# ============================================
# ENVIRONMENT & SECRETS (NEVER COMMIT)
# ============================================
.env
.prodenv
.envcopy
*.pem
*.key

# ============================================
# PYTHON
# ============================================
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
ENV/
env/
*.egg-info/
.pytest_cache/
.ruff_cache/
.coverage
coverage.xml
htmlcov/

# ============================================
# NODE / REACT
# ============================================
node_modules/
package.json
package-lock.json
gemini-website/dist/
gemini-website/.next/
build/

# ============================================
# DATABASE FILES (NEVER COMMIT)
# ============================================
*.db
*.db-shm
*.db-wal
*.sqlite
*.sqlite3
*.db.backup*
*.db.bak*
*.bak
*.backup
*BACKUP*
# SQL backups (runtime dumps — not schema files)
etlegacy_backup*.sql
postgresql_backup_*.sql
*_backup_*.sql
*_before_*.sql

# ============================================
# LOGS
# ============================================
*.log
nohup.out
logs/
!logs/.gitkeep
bot/logs/
website/logs/
!website/logs/.gitkeep

# ============================================
# IDE & OS
# ============================================
.vscode/settings.json
*.code-workspace
.idea/
.claude/
*.swp
*.swo
*~
.DS_Store
Thumbs.db
desktop.ini

# ============================================
# ARCHIVES & BINARIES (NEVER COMMIT)
# ============================================
*.zip
*.tar.gz
*.rar
*.7z

# ============================================
# IMAGES
# Root-level screenshots and debug images are never needed.
# Website assets (SVG) are kept; they live in website/assets/.
# Rule: ignore *.jpg/*.png at root and in dev scratch locations.
# ============================================
*.jpg
*.jpeg
*.png
*.gif
*.bmp
# Re-allow website SVG assets (not affected by above — different extension)
# website/assets/ uses .svg only, so no exceptions needed here.
# Re-allow specific test fixtures that use images (add per-path exceptions below if needed)

# ============================================
# DEMO / GAME FILES
# ============================================
*.dm_84
*.tv_84

# ============================================
# BROKEN PIP INSTALL ARTIFACTS
# ============================================
=*

# ============================================
# BACKUP / TEMP FILES
# ============================================
*.orig
*_before_fix_*.html
*_before_fix_*.js
*.BACKUP_[0-9]*
/temp/
/tmp/
/asdf/
/publish_temp/
/publish_clean/

# ============================================
# ROOT-LEVEL DEV/TEST SCRIPTS (NEVER COMMIT)
# Legitimate test scripts live in tests/
# Legitimate debug scripts live in scripts/
# ============================================
# Analysis & validation outputs
analysis_*.txt
*_analysis*.txt
*_validation*.txt
*_discrepancies*.json
*_log*.txt
*_log*.json
overnight_*.txt
nov2_*.txt

# Development HTML reports (not docs)
*.html
!docs/*.html
!website/*.html
!website/index.html

# Field mapping dev files
field_*.txt
field_*.json
field_*.html
FIELD_MAPPING.json

# Status/presentation files
*_PRESENTATION.html
*_EXPLAINED.html
*_EXPLAINED.txt
*_REPORT.html

# Git/deployment notes (use docs/ instead)
GIT_*.txt
GITHUB_*.txt
DEPLOYMENT_*.txt
DOCS_STATUS*.txt
CURRENT_DB_SCHEMA.txt
FLOW_DIAGRAM.txt

# Temp development files
cmon.txt
check.vps.*.txt
rebuild_inputs.txt
backup_table_schemas.txt
debug_fp.py
team_check_output.txt
test_out.txt
validation_*.txt
stats_validation_*.json
req2.txt

# Deprecated install docs at root
INSTALL_*.md

# ============================================
# ROOT-LEVEL SCRIPTS (use install.sh only)
# ============================================
*.bat
*.ps1
setup_linux_bot.sh
setup_linux_env.sh
vps_install.sh
vps_setup.sh
drop_tables.sh
check_before_commit.sh

# Personal automation scripts
run_claude_auto.sh

# ============================================
# PERSONAL / SCRATCH FILES AT ROOT
# ============================================
chatgptresearch.md
zac0rna.md
Complete
plan-*.md
*.prompt.md

# ============================================
# ROOT LUA FILES (game server experiments)
# Production Lua is in vps_scripts/ and proximity/lua/
# ============================================
/*.lua

# ============================================
# ROOT SQL FILES (schema superseded by tools/)
# ============================================
/schema.sql

# ============================================
# ROOT DEV MARKDOWN FILES (keep only named essentials)
# ============================================
*_IMPLEMENTATION*.md
*_VERIFICATION*.md
*_REFERENCE*.md
*_OVERVIEW*.md
*_SUMMARY*.md
*_DEPLOYMENT*.md
*_README*.md
!README.md
!proximity/**/*.md

# ============================================
# VS CODE WORKSPACE FILES
# ============================================
*.code-workspace

# ============================================
# OTHER ROOT DEV ARTIFACTS
# ============================================
corrupt_records_before_fix.txt
postgres_setup.md
.markdownlint.json
.markdownlintignore
DATA_ACCURACY_REPORT.md
TESTING_REQUIRED.md
WEBSITE_STAT_BUGS_FOUND.md

# ============================================
# DEV DIRECTORIES (NEVER COMMIT)
# ============================================
/analytics/
/archive/
/asdf/
/backups/
/bot_backup_*/
/database/
/database_backups/
/dev/
/dev_tools/
/fiveeyes/
/local_stats/
/local_gametimes/
/local_proximity/
/data/
/monitoring/
/node_modules/
/prompt_instructions/
/server/
/temp/
/test_files/
/test_suite/
/tmp/
/publish_temp/
/publish_clean/
/github/
/performance_updates/
/bin/
/opusreview/
/deployed_lua/

# ============================================
# KEEP ESSENTIAL ROOT SCRIPTS
# ============================================
!/scripts/
!/tools/
!/scripts/__init__.py
!/scripts/backfill_gametimes.py
!/tools/__init__.py
!/tools/simple_bulk_import.py
!/tools/verify_pipeline.py

# ============================================
# VPS SCRIPTS (keep only production webhook)
# ============================================
/vps_scripts/
!/vps_scripts/
!/vps_scripts/stats_discord_webhook.lua
!/vps_scripts/stats_webhook_notify.py
!/vps_scripts/__init__.py

# ============================================
# ROOT DIAGNOSTIC/DEV SCRIPTS
# ============================================
check_*.py
compare_*.py
investigate_*.py
show_*.py
pentest_*.py
test_*.py
!tests/test_*.py
!tests/**/test_*.py
trigger_timing_debug.py

# ============================================
# MIGRATIONS — KEEP ALL SQL MIGRATIONS
# ============================================
# NOTE: Current gitignore incorrectly ignores migrations/ directory.
# All *.sql migration files should be tracked.
# The negation rules below ensure they are included.
!migrations/
!migrations/*.sql
!migrations/__init__.py
!website/migrations/
!website/migrations/*.sql
!proximity/schema/migrations/
!proximity/schema/migrations/*.sql
!tools/migrations/
!tools/migrations/*.py
!tools/migrations/*.sql

# ============================================
# TOOLS DIRECTORY — ESSENTIALS ONLY
# ============================================
tools/*
!tools/__init__.py
!tools/simple_bulk_import.py
!tools/stopwatch_scoring.py
!tools/schema_postgresql.sql
!tools/pipeline_health_report.py
!tools/verify_pipeline.py
!tools/migrations/
!tools/migrations/*.py
!tools/migrations/*.sql
!tools/schema_sqlite.sql
!tools/vm_steps/
!tools/vm_steps/*.sh
!tools/harden_*.sh

# ============================================
# DOCS ARCHIVE (historical, not needed)
# ============================================
docs/archive/

# ============================================
# DOCS — INTERNAL DEV ARTIFACTS (gitignore)
# ============================================
docs/SESSION_*.md
docs/SESSION_INDEX.md
docs/SESSION_REPORT_*.md
docs/evidence/
docs/codexreport-*.md
docs/TODO_*.md
docs/TODO-*.md
docs/HANDOFF_*.md
docs/CRASH_PROOF_*.md
docs/MISSION_*.md
docs/LIVE_MONITORING_*.md
docs/WEEK_HANDOFF_*.md
docs/*_IMPLEMENTATION_PLAN_*.md
docs/IMPLEMENTATION_PROGRESS_*.md
docs/IMPLEMENTATION_COMPLETE_*.md
docs/REFACTORING_PROGRESS.md
docs/INTEGRATION_CONFLICTS_*.md
docs/LAN_PUBLIC_ACCESS_*.md
docs/reports/deep-research-report*.md
docs/reports/deep-research-report*.docx
docs/reports/deep-research-report*.pdf
docs/reports/CLAUDE_*.md
docs/reports/CODEBASE_FINDINGS_*.md
docs/time_audit_report_*.json
docs/TECHNICAL_DEBT_AUDIT_*.md
docs/AUDIT_*.md
docs/CRITICAL_DISCOVERY_REPORT.md
docs/TIMING_BUG_ANALYSIS.md
docs/PR30_REVIEW.md
docs/SCORING_NOTE_*.md
docs/DEEP_TIMING_*.md
docs/SECURITY_FIXES_*.md
docs/SECURITY_AUDIT_*.md
docs/PRODUCTION_AUDIT_*.md
docs/PRODUCTION_STATUS.md
docs/PARSER_FIX_COMPLETE.md
docs/slomix-refactor-*.md
docs/slomix_code_review_*.md
docs/*-RECOVERY*.md
docs/*-WEBSITE_FIXES*.md
docs/AI_AGENT_INSTRUCTIONS.md
docs/GEMINI_IMPLEMENTATION_GUIDE.md
docs/TESTING_IMPLEMENTATION_SUMMARY.md
docs/PERFORMANCE_IMPACT_ANALYSIS.md
docs/BACKLOG_*.md
docs/WEEK_*_RECONNAISSANCE_REPORT.md
docs/RUNTIME_CYCLE_COMPLETE.md
docs/IMPLEMENTATION_SUMMARY.md
docs/FIXES_APPLIED_*.md
docs/FIX_LAST_SESSION.md
docs/FIX_TEAM_TRACKING.md
docs/CHANGES_*.md
docs/DOCUMENTATION_ACCURACY_*.md
docs/BOT_AUDIT_REPORT_*.md
docs/CODE_AUDIT_*.md
docs/codacy-issues*.txt*
docs/LUA_ERROR_LOGS_*.txt
docs/POSTING_SYSTEMS_INVESTIGATION.md
docs/MISSING_R1_*.md
docs/PIPELINE_VALIDATION_*.md
docs/TIME_DEAD_*.md
docs/TIME_TRACKING_*.md
docs/LUA_TIME_BUG_*.md
docs/LUA_REF_SCRIPT_*.md
docs/LUA_WEBHOOK_HARDENING_*.md
docs/SECRETS_CENTRALIZATION_*.md
docs/PLAN_FASTDL_*.md
docs/COMPETITIVE_ANALYTICS_*.md
docs/PROXIMITY_ANALYTICS_BACKLOG_*.md
docs/PROXIMITY_MAP_OVERLAY_*.md
docs/PROXIMITY_RESEARCH_*.md
docs/GREATSHOT_CROSSREF_*.md
docs/ENHANCEMENT_IDEAS.md
docs/ANALYTICS_ROADMAP.md
docs/SL0MIX_SPA_*.md
docs/WEBSITE_APPJS_*.md
docs/WEBSITE_FIX_SESSION_*.md
docs/WEBSITE_INTEGRATION_NOTES.md
docs/WEBSITE_PROJECT_REVIEW.md
docs/WEBSITE_UI_UPGRADE_*.md
docs/WEBSITE_VISION_*.md
docs/WEBHOOK_SSH_SMART_*.md
docs/WEBHOOK_NOTIFICATION_SETUP.md
docs/STOPWATCH_TIME_*.md
docs/OMNIBOT_*.cfg
docs/omnibot_*.md
docs/INTEGRATION_*.md
docs/et_stopwatch_proximity_analytics_spec.md
docs/reference/TESTING_CHECKLIST_*.md
docs/reference/live_sync_backups/

# AI agent prompt/handoff docs (internal operations logs)
docs/AI_AGENT_EXEC_PROMPT_SYSTEM_LOG_AUDIT_*.md
docs/AI_AGENT_PROMPT_LAUNCH_CARD_*.md
docs/AI_AGENT_SYSTEM_AUDIT_*.md
docs/AI_AGENT_SYSTEM_AUDIT_RUN_LOG.md
docs/AI_HANDOFF_*.md
docs/PIPELINE_DEEP_DIVE_HANDOFF_*.md
docs/TIMING_SHADOW_HANDOFF_*.md
docs/SYSTEM_LOG_AUDIT_*.md
docs/R2_ENDSTATS_*.md
docs/LUA_R2_MISSING_ROOT_CAUSE_*.md
docs/WS1_R2_MISSING_INVESTIGATION_*.md
docs/SUPER_PROMPT_*.md

# Historical proximity docs that are redundant/superseded
docs/PROXIMITY_CLOSEOUT_*.md
docs/PROXIMITY_ETL_LUA_CAPABILITIES_*.md
docs/PROXIMITY_IMPROVEMENT_DIRECTION_*.md
docs/PROXIMITY_WEB_BENCHMARK_IDEAS_*.md

# Historical fix scripts and one-off directories
docs/2026-01-30-r2-parser-fix/
docs/scripts_2026-01-30_r2_fix/
docs/scripts/

# ============================================
# BOT — DEAD CODE & DEV ARTIFACTS
# ============================================
bot/*.db
bot/*.db.*
bot/*.bak
bot/*.backup
bot/etlegacy_production*
bot/BACKUP_*
bot/*.cleaned.py
bot/ultimate_bot.py.backup*
bot/ultimate_bot.py.bak
bot/local_stats/
bot/tools/
bot/backups/
bot/diagnostics/
bot/config.json
bot/fiveeyes_config.json
bot/BOT_CRITICAL_FIXES.py
bot/automation_architecture.py
bot/automation_enhancements.py
bot/check_db.py
bot/dotenv-example
bot/helper_methods_to_insert.txt
bot/hybrid_processing_helpers.py
bot/insert_helpers.py
bot/integrate_automation.py
bot/last_session_helpers.py
bot/last_session_redesigned_impl.py
bot/proximity_parser.py
bot/proximity_parser_v2.py
bot/proximity_parser_v3.py
bot/proximity_schema.sql
bot/proximity_schema_v2.sql
bot/proximity_schema_v3.sql
bot/remove_duplicates.py
bot/retro_text_stats.py
bot/retro_viz.py
bot/setup_automation.py
bot/image_generator.py
bot/website_design_prototype.pdf
bot/README_AUTOMATION.md

# ============================================
# WEBSITE DEV ARTIFACTS
# ============================================
website/backend/debug_*.py
website/fix_*.sql
website/grant_*.sql
website/index_before_fix_*.html
website/index_BEFORE_RESTORE_*.html
website/index_temp_builder.html
website/js/app.js.BACKUP*
website/js/records.js.BACKUP*
website/SESSION_NOTES_*.md
website/REVIEW_NOTES.md
website/websitemissing*.png
website/website.code-workspace
website/venv/

# ============================================
# TEST DEV SCRIPTS (keep real tests)
# ============================================
tests/check_*.py
tests/compile_all.py
tests/diag_*.py
tests/tmp_*.py

# ============================================
# SUB-PROJECT DEV FILES
# ============================================
proximity/.github/
website/.github/
proximity/map_rotation.txt

# ============================================
# KEEP ESSENTIAL FILES (explicit allowlist)
# ============================================
!README.md
!CLAUDE.md
!CONTRIBUTING.md
!CODE_OF_CONDUCT.md
!SECURITY.md
!LICENSE
!CHANGELOG.md
!requirements.txt
!requirements-dev.txt
!.env.example
!.gitignore
!.gitattributes
!.dockerignore
!.codacy.yaml
!.secrets.baseline
!.nvmrc
!.pre-commit-config.yaml
!.release-please-config.json
!.release-please-manifest.json
!postgresql_database_manager.py
!install.sh
!start_bot.sh
!update_bot.sh
!freshinstall.sh
!Makefile
!docker-compose.yml
!pyproject.toml
!pytest.ini
!bot_config.json

# ============================================
# COPILOT/AI INSTRUCTIONS (keep these)
# ============================================
!.github/copilot-instructions.md
!.github/instructions/
```

---

## Part 2: Files Currently Tracked That Should Be Untracked

The current repo has **502 tracked files**. The following files need `git rm --cached` to
stop tracking them (files remain on disk, only removed from git index).

### Group 1: Personal/Scratch Root Files (~4 files)

These are personal notes and empty marker files with no project value.

| File | Reason |
|------|--------|
| `chatgptresearch.md` | Personal research notes |
| `zac0rna.md` | Personal notes |
| `Complete` | Empty marker file |
| `schema.sql` | Superseded by `tools/schema_postgresql.sql` |

```bash
git rm --cached chatgptresearch.md zac0rna.md Complete schema.sql
```

### Group 2: Miscellaneous Root Scripts (~2 files)

| File | Reason |
|------|--------|
| `slomix_vm_setup.sh` | Superseded by `install.sh` and `tools/vm_steps/` |
| `freshinstall.sh` | Borderline — if not referenced in README, untrack |

```bash
git rm --cached slomix_vm_setup.sh
# Review freshinstall.sh before removing — may be referenced externally
```

### Group 3: deployed_lua/ Directory (~5 files)

This directory contains legacy Lua backups superseded by `vps_scripts/` and `proximity/lua/`.

| File | Reason |
|------|--------|
| `deployed_lua/README.md` | Superseded |
| `deployed_lua/legacy/c0rnp0rn7.lua` | Legacy, superseded |
| `deployed_lua/legacy/endstats.lua` | Legacy, superseded |
| `deployed_lua/legacy/luascripts/proximity_tracker.lua` | Superseded by `proximity/lua/` |
| `deployed_lua/legacy/luascripts/stats_discord_webhook.lua` | Superseded by `vps_scripts/` |

```bash
git rm --cached -r deployed_lua/
```

### Group 4: docs/ Files That Should Not Be Tracked (~35 files)

These are AI agent handoff docs, internal audit logs, and transient reports.

```bash
git rm --cached \
  docs/AI_AGENT_EXEC_PROMPT_SYSTEM_LOG_AUDIT_2026-02-18.md \
  docs/AI_AGENT_PROMPT_LAUNCH_CARD_v1.3.0.md \
  docs/AI_AGENT_SYSTEM_AUDIT_MASTER_PROMPT.md \
  docs/AI_AGENT_SYSTEM_AUDIT_PROMPT_V2_2026-02-18.md \
  docs/AI_AGENT_SYSTEM_AUDIT_RUN_LOG.md \
  docs/AI_HANDOFF_HOME_AVAILABILITY_RETROVIZ_2026-02-18.md \
  docs/DEEP_DIVE_AUDIT_2026-02-20.md \
  docs/GET_READY_SOUND.md \
  docs/LAPTOP_DEPLOYMENT_GUIDE.md \
  docs/LAPTOP_MIGRATION_GUIDE.md \
  docs/LUA_R2_MISSING_ROOT_CAUSE_2026-02-18.md \
  docs/PIPELINE_DEEP_DIVE_HANDOFF_2026-02-18.md \
  docs/PIPELINE_TIMETRACKING_GAP_ANALYSIS.md \
  docs/PIPELINE_TIMETRACKING_NEXT_STEPS_PLAN.md \
  docs/PIPELINE_TIMETRACKING_RESEARCH_SYNTHESIS.md \
  docs/PROXIMITY_CLOSEOUT_2026-02-19.md \
  docs/PROXIMITY_ETL_LUA_CAPABILITIES_2026-02-19.md \
  docs/PROXIMITY_IMPROVEMENT_DIRECTION_2026-02-19.md \
  docs/PROXIMITY_WEB_BENCHMARK_IDEAS_2026-02-19.md \
  docs/R2_ENDSTATS_ACHIEVEMENTS_INVESTIGATION_2026-02-18.md \
  docs/R2_ENDSTATS_DELEGATION_CHECKLIST_2026-02-18.md \
  docs/ROAD_AHEAD_EXECUTION_RUNBOOK_2026-02-12.md \
  docs/SUPER_PROMPT_2026-02-20.md \
  docs/SYSTEM_LOG_AUDIT_DELEGATION_CHECKLIST_2026-02-18.md \
  docs/SYSTEM_LOG_AUDIT_FINDINGS_2026-02-18.md \
  docs/TIMING_SHADOW_HANDOFF_2026-02-18.md \
  docs/TWO_WEEK_CLOSEOUT_PLAN_2026-02-11.md \
  docs/TWO_WEEK_CLOSEOUT_REPORT_2026-02-16.md \
  docs/TWO_WEEK_EXECUTION_TRACKER_2026-02-11.md \
  docs/TWO_WEEK_LIVE_MONITOR_MISSION_2026-02-18.md \
  docs/VM_MIGRATION_REPORT_2026-02-20.md \
  docs/WEBHOOK_TRIAGE_CHECKLIST_2026-02-11.md \
  docs/WS1_R2_MISSING_INVESTIGATION_2026-02-18.md \
  docs/workfile.md \
  docs/PROJECT_HISTORY_APPENDIX.md
```

### Group 5: docs/reference/ Live Sync Backups (~2 files)

| File | Reason |
|------|--------|
| `docs/reference/live_sync_backups/20260219_153221/proximity_tracker.local_before_sync.lua` | Transient backup |
| `docs/reference/live_sync_backups/20260219_153221/stats_discord_webhook.local_before_sync.lua` | Transient backup |

```bash
git rm --cached -r docs/reference/live_sync_backups/
```

### Group 6: docs/reports/ AI Agent Reports (~15 files)

| Pattern | Action |
|---------|--------|
| `docs/reports/AVAILABILITY_PROMPT_COMPLETION_REPORT_*.md` | Internal AI report |
| `docs/reports/AVAILABILITY_V2_CONTEXT_COMPACT_*.md` | Internal AI context |
| `docs/reports/C0RNP0RN7_DEVELOPER_REPORT_*.md` | Internal audit |
| `docs/reports/LINE_BY_LINE_AUDIT_*.md` | Internal audit |
| `docs/reports/LIVE_PIPELINE_AUDIT_*.md` | Internal audit |
| `docs/reports/MEGA_PROMPT_NEXT_STAGE_CHECKLIST_*.md` | Internal checklist |
| `docs/reports/NIGHTLY_FINDINGS_SNAPSHOT_*.md` | Internal snapshot |
| `docs/reports/PR37_STABILIZATION_FINDINGS_*.md` | Internal finding |
| `docs/reports/RESTART_HANDOVER_*.md` | Internal handoff |
| `docs/reports/SHOP_CLOSE_HANDOVER_*.md` | Internal handoff |
| `docs/reports/TIMING_SHADOW_INVESTIGATION_*.md` | Internal investigation |
| `docs/reports/stage4_live_verification.sh` | One-off script |

```bash
git rm --cached \
  docs/reports/AVAILABILITY_PROMPT_COMPLETION_REPORT_2026-02-19.md \
  docs/reports/AVAILABILITY_V2_CONTEXT_COMPACT_2026-02-19.md \
  docs/reports/C0RNP0RN7_DEVELOPER_REPORT_2026-02-19.md \
  docs/reports/LINE_BY_LINE_AUDIT_CLOSED_OPEN_MATRIX_2026-02-19.md \
  docs/reports/LINE_BY_LINE_AUDIT_PATCH_REPORT_2026-02-19.md \
  docs/reports/LIVE_PIPELINE_AUDIT_2026-02-18.md \
  docs/reports/MEGA_PROMPT_NEXT_STAGE_CHECKLIST_2026-02-19.md \
  docs/reports/NIGHTLY_FINDINGS_SNAPSHOT_2026-02-18.md \
  docs/reports/PR37_STABILIZATION_FINDINGS_2026-02-18.md \
  docs/reports/RESTART_HANDOVER_AVAILABILITY_2026-02-19.md \
  docs/reports/SHOP_CLOSE_HANDOVER_AVAILABILITY_2026-02-19.md \
  docs/reports/TIMING_SHADOW_INVESTIGATION_2026-02-18.md \
  docs/reports/stage4_live_verification.sh
```

### Group 7: docs/evidence/ and docs/research/ Transient Data (~4 files)

```bash
git rm --cached \
  docs/evidence/2026-02-16_ws1_live_session.md \
  docs/research/inbox/RESEARCH_INBOX_2026-02-19_chatgpt.md \
  docs/research/validated/RESEARCH_VALIDATED_2026-02-19_CHATGPT.md
# Keep .gitkeep placeholders
```

### Group 8: monitoring/ Directory (~1 file)

| File | Reason |
|------|--------|
| `monitoring/prometheus.yml` | Duplicate of `docker/prometheus.yml` — verify before removing |

```bash
# First verify: diff monitoring/prometheus.yml docker/prometheus.yml
# If duplicate: git rm --cached monitoring/prometheus.yml
```

### Summary of Untrack Operations

| Group | Files | Command Type |
|-------|-------|-------------|
| Personal/scratch root files | ~4 | Individual |
| Miscellaneous root scripts | ~1 | Individual |
| `deployed_lua/` directory | ~5 | `git rm --cached -r` |
| `docs/` internal/AI agent docs | ~35 | Batch |
| `docs/reference/live_sync_backups/` | ~2 | `git rm --cached -r` |
| `docs/reports/` AI agent reports | ~13 | Batch |
| `docs/evidence/` and `docs/research/` | ~3 | Batch |
| `monitoring/` (verify first) | ~1 | Individual |
| **TOTAL** | **~64 files** | |

---

## Part 3: Before/After File Count Estimates

| Category | Before | After | Notes |
|----------|--------|-------|-------|
| Total tracked files | 502 | ~438 | Remove ~64 files |
| Root-level files | ~40 | ~32 | Remove scratch/personal files |
| `docs/` tracked | 136 | ~95 | Remove AI handoff/audit docs |
| `docs/reports/` tracked | ~14 | 2 | Keep only Phase 3 + Phase 5 reports |
| `bot/` tracked | 93 | 93 | No changes needed |
| `website/` tracked | ~60 | ~60 | No changes needed |
| `tests/` tracked | 65 | 65 | No changes needed |
| `deployed_lua/` | 5 | 0 | Remove entirely |
| Files newly gitignored (future) | — | — | Patterns block future clutter |

---

## Part 4: Step-by-Step Execution Instructions

### Prerequisites

- You must be on a feature branch (not `main`)
- Verify the proposed `.gitignore` content is correct
- Run `git status` before starting to confirm baseline

### Step 1: Create a Cleanup Branch

```bash
git checkout main
git pull origin main
git checkout -b chore/github-cleanup-phase5
```

### Step 2: Replace .gitignore

Copy the full `.gitignore` content from Part 1 of this document into `.gitignore`.

```bash
# After editing the file:
git add .gitignore
```

### Step 3: Untrack Personal/Scratch Root Files

```bash
git rm --cached chatgptresearch.md zac0rna.md Complete schema.sql slomix_vm_setup.sh
```

### Step 4: Untrack deployed_lua/ Directory

```bash
git rm --cached -r deployed_lua/
```

### Step 5: Untrack Internal docs/ Files

Run the batch `git rm --cached` commands from Group 4 and Group 5 (Part 2 above).

### Step 6: Untrack docs/reports/ Internal Reports

Run the batch `git rm --cached` from Group 6 (Part 2 above).

### Step 7: Untrack docs/evidence/ and docs/research/ Transient Data

Run the batch `git rm --cached` from Group 7 (Part 2 above).

### Step 8: Handle monitoring/prometheus.yml (Optional)

```bash
diff monitoring/prometheus.yml docker/prometheus.yml
# If identical: git rm --cached monitoring/prometheus.yml
```

### Step 9: Verify Nothing Essential Was Untracked

```bash
# Check that all critical files are still tracked:
git ls-files | grep -E '^bot/ultimate_bot\.py$'
git ls-files | grep -E '^bot/cogs/'
git ls-files | grep -E '^tests/'
git ls-files | grep -E '^vps_scripts/'
git ls-files | grep -E '^tools/schema_postgresql\.sql$'
git ls-files | grep -E '^\.(gitignore|env\.example|pre-commit-config\.yaml)$'
```

### Step 10: Commit and Open PR

```bash
git add -A
git status  # Review the staged changes carefully
git commit -m "chore(repo): clean up gitignore and untrack non-essential files

Remove ~64 files from git tracking:
- Personal/scratch root files (chatgptresearch.md, zac0rna.md, Complete)
- Legacy deployed_lua/ directory (superseded by vps_scripts/)
- Internal AI agent handoff docs from docs/
- docs/reports/ internal audit reports
- docs/reference/live_sync_backups/ transient backups

Updated .gitignore v2.0:
- Add patterns for future clutter prevention
- Fix migrations/ directory tracking rules
- Add deployed_lua/ to ignored directories
- Add patterns for AI agent doc categories"

git push origin chore/github-cleanup-phase5
gh pr create --title "chore: Phase 5 GitHub cleanup - gitignore v2.0 + untrack non-essential files"
```

---

## Part 5: CONTRIBUTING.md Additions — Commit Policy

Add the following section to `/home/samba/share/slomix_discord/CONTRIBUTING.md`:

```markdown
## What to Commit vs. What Not to Commit

### Always Track (MUST commit)
- Python source files (`bot/`, `website/backend/`, `greatshot/`, `proximity/parser/`)
- JavaScript/TypeScript source files (`website/js/`, `gemini-website/src/`)
- SQL schema files (`tools/schema_postgresql.sql`, `migrations/*.sql`, `website/migrations/*.sql`)
- Tests (`tests/`)
- CI/CD configs (`.github/workflows/`, `.codacy.yaml`, `pyproject.toml`)
- Config templates (`.env.example`, `bot_config.json`, `docker-compose.yml`)
- Active documentation (`docs/*.md` — see below for exceptions)
- Lua production scripts (`vps_scripts/stats_discord_webhook.lua`, `proximity/lua/proximity_tracker.lua`)

### Never Commit (NEVER commit these categories)
| Category | Examples | Where it belongs |
|----------|----------|-----------------|
| Secrets / credentials | `.env`, SSH keys, tokens | Vault / secrets manager |
| Database files | `*.db`, `*.sqlite`, `*.sql` dumps | Backups / local only |
| Log files | `*.log`, `nohup.out`, `bot/logs/` | Runtime, local only |
| Screenshots / images | `*.jpg`, `*.png` at root | Discord / notes |
| Personal notes | `chatgptresearch.md`, `zac0rna.md` | Personal files |
| AI agent handoff docs | `docs/AI_AGENT_*.md`, `docs/TIMING_SHADOW_HANDOFF_*.md` | Internal ops only |
| Session logs from AI agents | `docs/SESSION_*.md`, `docs/workfile.md` | Internal ops only |
| Root-level debug scripts | `check_*.py`, `pentest_*.py`, `test_*.py` at root | `scripts/` if needed |
| Windows dev scripts | `*.bat`, `*.ps1` | Not part of project |
| Build artifacts | `node_modules/`, `dist/`, `__pycache__/`, `venv/` | Gitignored |
| Runtime data | `local_stats/`, `local_gametimes/`, `data/greatshot/` | Gitignored |
| Game demo recordings | `*.dm_84`, `*.tv_84` | Not project files |
| Zip archives | `*.zip` | Not project files |

### Borderline — Ask First
- New root-level `.md` files: place in `docs/` instead
- New scripts at root: place in `scripts/` instead
- Audit/investigation docs: place in `docs/reports/` with date suffix; these may be cleaned up periodically
- Reference files: place in `docs/reference/`

### The Rule of Thumb
> If it's not code, config, or documentation useful to a new developer setting up the project,
> it probably shouldn't be in git. When in doubt, ask in the PR.
```

---

## Part 6: Pre-Commit Hook Proposal

### Option A: Simple Shell Hook (`.git/hooks/pre-commit`)

This runs locally. Add to `.pre-commit-config.yaml` for team-wide enforcement:

```yaml
# In .pre-commit-config.yaml, add this hook:
- repo: local
  hooks:
    - id: no-clutter
      name: Prevent committing non-essential files
      language: script
      entry: scripts/check_commit_clutter.sh
      pass_filenames: true
```

Create `scripts/check_commit_clutter.sh`:

```bash
#!/usr/bin/env bash
# Warns when staging files that likely shouldn't be committed.
# Part of Phase 5 cleanup: prevents future repo clutter.

set -e

WARNED=0

for file in "$@"; do
  # Block root-level images
  if echo "$file" | grep -qE '^\.(jpg|jpeg|png|gif|bmp)$'; then
    echo "WARN: Root-level image file staged: $file (screenshots belong in Discord, not git)"
    WARNED=1
  fi

  # Block database files
  if echo "$file" | grep -qE '\.(db|sqlite|sqlite3|db-shm|db-wal)$'; then
    echo "ERROR: Database file staged: $file — never commit database files"
    exit 1
  fi

  # Block SQL backups (not schema migrations)
  if echo "$file" | grep -qE '(backup|_backup_).*\.sql$'; then
    echo "ERROR: SQL backup file staged: $file — never commit backup dumps"
    exit 1
  fi

  # Block log files
  if echo "$file" | grep -qE '\.(log)$|^nohup\.out$'; then
    echo "ERROR: Log file staged: $file — never commit logs"
    exit 1
  fi

  # Block .env (not .env.example)
  if echo "$file" | grep -qE '^\.env$|/\.env$'; then
    echo "ERROR: .env file staged: $file — NEVER commit .env files (use .env.example)"
    exit 1
  fi

  # Block root-level debug scripts
  if echo "$file" | grep -qE '^(check_|compare_|investigate_|pentest_|show_|debug_)[^/]+\.py$'; then
    echo "WARN: Root-level debug script staged: $file (consider moving to scripts/)"
    WARNED=1
  fi

  # Block zip archives
  if echo "$file" | grep -qE '\.(zip|tar\.gz|rar|7z)$'; then
    echo "ERROR: Archive file staged: $file — never commit archives"
    exit 1
  fi

  # Block game demo files
  if echo "$file" | grep -qE '\.(dm_84|tv_84)$'; then
    echo "ERROR: Game demo file staged: $file — never commit game recordings"
    exit 1
  fi

  # Block broken pip artifacts
  if echo "$file" | grep -qE '^='; then
    echo "ERROR: Broken pip artifact staged: $file — delete this file"
    exit 1
  fi
done

if [ "$WARNED" -eq 1 ]; then
  echo ""
  echo "Warnings found. Review the files above before committing."
  echo "See CONTRIBUTING.md for the full commit policy."
  # Warnings don't block the commit — errors do
fi

exit 0
```

### Option B: GitHub Actions CI Check (`.github/workflows/repo-hygiene.yml`)

The existing `repo-hygiene.yml` workflow can be extended with:

```yaml
- name: Check for non-essential files
  run: |
    FAILED=0

    # Check for database files
    if git diff --name-only HEAD | grep -qE '\.(db|sqlite|db-shm)$'; then
      echo "ERROR: Database files detected in PR"
      FAILED=1
    fi

    # Check for log files
    if git diff --name-only HEAD | grep -qE '\.log$|^nohup\.out$'; then
      echo "ERROR: Log files detected in PR"
      FAILED=1
    fi

    # Check for .env
    if git diff --name-only HEAD | grep -qE '^\.env$'; then
      echo "ERROR: .env file detected — never commit secrets"
      FAILED=1
    fi

    # Check for archives
    if git diff --name-only HEAD | grep -qE '\.(zip|tar\.gz)$'; then
      echo "ERROR: Archive files detected in PR"
      FAILED=1
    fi

    # Warn about root-level images
    if git diff --name-only HEAD | grep -qE '^\.(jpg|jpeg|png|gif)$'; then
      echo "WARN: Root-level image files in PR — screenshots don't belong in git"
    fi

    exit $FAILED
```

### Recommendation

Implement **both**:
- Option A (pre-commit hook) for fast local feedback during development
- Option B (CI check) as the enforcement gate that blocks PRs

---

## Part 7: Files Requiring Owner Decision Before Cleanup

These files need a human to decide before acting:

| File | Issue | Options |
|------|-------|---------|
| `freshinstall.sh` | Referenced externally? May be used in deployment docs | Keep if referenced; else untrack |
| `monitoring/prometheus.yml` | May differ from `docker/prometheus.yml` | Diff and decide; if duplicate, remove |
| `docs/AUDIT_*.md` (12 files tracked) | Audit docs — valuable history vs. clutter | Archive in `docs/archive/` or untrack |
| `docs/PROJECT_HISTORY_APPENDIX.md` | Extension of PROJECT_HISTORY.md | Merge or archive |
| `docs/workfile.md` | Empty? AI scratchpad? | Delete if empty |
| `bot/services/automation/INTEGRATION_GUIDE.md` | Tracked but not in Phase 3 essential list | Review — keep if useful |
| `bot/schema.sql` | Both tracked and gitignored (conflict!) | Resolve: keep `tools/schema_postgresql.sql` as canonical |

---

## Part 8: What the Repo Will Look Like After Cleanup

### File Count After Cleanup

| Directory | Before | After |
|-----------|--------|-------|
| `bot/` | 93 | 93 (no change) |
| `website/` | ~60 | ~60 (no change) |
| `tests/` | 65 | 65 (no change) |
| `docs/` | 136 | ~95 |
| `docs/reports/` | ~14 | 2 (Phase 3 + Phase 5) |
| Root-level files | ~40 | ~34 |
| `deployed_lua/` | 5 | 0 |
| `monitoring/` | 1 | 0 (moved to docker/) |
| **TOTAL** | **502** | **~438** |

### What Gets Cleaner

1. **Root level**: No personal notes (`chatgptresearch.md`, `zac0rna.md`), no empty markers (`Complete`), no duplicate schemas (`schema.sql`)
2. **docs/**: Focused on actual documentation; AI handoff/operations logs removed
3. **docs/reports/**: Only Phase 3 + Phase 5 cleanup plans; removes ~12 internal AI reports
4. **deployed_lua/**: Gone entirely — superseded by `vps_scripts/` and `proximity/lua/`
5. **Future-proofed**: `.gitignore` v2.0 patterns prevent the same clutter categories from returning

### What Stays Clean (No Change Needed)

- All `bot/` source code (93 files) — already clean
- All `tests/` (65 files) — already clean
- All `website/` source (60 files) — already clean
- All `greatshot/`, `proximity/`, `vps_scripts/` — already minimal and correct
- CI/CD (`.github/`, `pyproject.toml`, `.pre-commit-config.yaml`) — already correct

---

*Report generated for Phase 5: GitHub Repository Cleanup. Review all sections before executing.
Execute the git rm commands manually after reading the CONTRIBUTING.md section and pre-commit hook.*
