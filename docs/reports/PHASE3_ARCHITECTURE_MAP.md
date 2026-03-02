# Phase 3: Architecture Map & Essential Files Inventory

**Generated**: 2026-02-23
**Purpose**: Definitive manifest for Phase 5 GitHub cleanup
**Scope**: All files in `/home/samba/share/slomix_discord`

---

## Summary Count

| Category | Count |
|----------|-------|
| Essential files (production code) | ~410 |
| Essential files (docs, config, CI) | ~220 |
| Non-essential files | ~800+ (plus entire dirs: backups, venv, node_modules, pycache) |

---

## Part 1: Essential Files Manifest

### 1. Bot Core (bot/)

**Entry point & config**
- `bot/ultimate_bot.py` — Main bot (4990 lines), loads all 21 cogs
- `bot/community_stats_parser.py` — R1/R2 differential parser (1036 lines)
- `bot/endstats_parser.py` — Secondary parser
- `bot/config.py` — Config loader (reads .env / bot_config.json)
- `bot/logging_config.py` — Logging setup
- `bot/__init__.py`

**21 Cogs (bot/cogs/)**
- `bot/cogs/__init__.py`
- `bot/cogs/achievements_cog.py`
- `bot/cogs/admin_cog.py`
- `bot/cogs/admin_predictions_cog.py`
- `bot/cogs/analytics_cog.py`
- `bot/cogs/automation_commands.py`
- `bot/cogs/availability_poll_cog.py`
- `bot/cogs/last_session_cog.py`
- `bot/cogs/leaderboard_cog.py`
- `bot/cogs/link_cog.py`
- `bot/cogs/matchup_cog.py`
- `bot/cogs/permission_management_cog.py`
- `bot/cogs/predictions_cog.py`
- `bot/cogs/proximity_cog.py`
- `bot/cogs/server_control.py`
- `bot/cogs/session_cog.py`
- `bot/cogs/session_management_cog.py`
- `bot/cogs/stats_cog.py`
- `bot/cogs/sync_cog.py`
- `bot/cogs/synergy_analytics.py`
- `bot/cogs/team_cog.py`
- `bot/cogs/team_management_cog.py`

**18 Core Modules (bot/core/)**
- `bot/core/__init__.py`
- `bot/core/achievement_system.py`
- `bot/core/advanced_team_detector.py`
- `bot/core/checks.py`
- `bot/core/database_adapter.py` — Async PostgreSQL abstraction
- `bot/core/endstats_pagination_view.py`
- `bot/core/frag_potential.py`
- `bot/core/lazy_pagination_view.py`
- `bot/core/match_tracker.py`
- `bot/core/pagination_view.py`
- `bot/core/round_contract.py`
- `bot/core/round_linker.py`
- `bot/core/season_manager.py`
- `bot/core/stats_cache.py`
- `bot/core/substitution_detector.py`
- `bot/core/team_detector_integration.py`
- `bot/core/team_history.py`
- `bot/core/team_manager.py`
- `bot/core/utils.py`

**Services (bot/services/)**
- `bot/services/__init__.py`
- `bot/services/availability_notifier_service.py`
- `bot/services/endstats_aggregator.py`
- `bot/services/matchup_analytics_service.py`
- `bot/services/monitoring_service.py`
- `bot/services/player_analytics_service.py`
- `bot/services/player_badge_service.py`
- `bot/services/player_display_name_service.py`
- `bot/services/player_formatter.py`
- `bot/services/prediction_embed_builder.py`
- `bot/services/prediction_engine.py`
- `bot/services/round_correlation_service.py`
- `bot/services/round_publisher_service.py`
- `bot/services/session_data_service.py`
- `bot/services/session_embed_builder.py`
- `bot/services/session_graph_generator.py`
- `bot/services/session_stats_aggregator.py`
- `bot/services/session_timing_shadow_service.py`
- `bot/services/session_view_handlers.py`
- `bot/services/signal_connector.py`
- `bot/services/stopwatch_scoring_service.py`
- `bot/services/telegram_connector.py`
- `bot/services/timing_comparison_service.py`
- `bot/services/timing_debug_service.py`
- `bot/services/voice_session_service.py`

**Automation Services (bot/services/automation/)**
- `bot/services/automation/__init__.py`
- `bot/services/automation/database_maintenance.py`
- `bot/services/automation/health_monitor.py`
- `bot/services/automation/metrics_logger.py`
- `bot/services/automation/ssh_monitor.py` — (disabled but imported)
- `bot/services/automation/ws_client.py`

**Automation (bot/automation/)**
- `bot/automation/__init__.py`
- `bot/automation/file_tracker.py`
- `bot/automation/ssh_handler.py`

**Repositories (bot/repositories/)**
- `bot/repositories/__init__.py`
- `bot/repositories/file_repository.py`

**Stats (bot/stats/)**
- `bot/stats/__init__.py`
- `bot/stats/calculator.py`

**Session Views (bot/session_views/)**
- `bot/session_views/__init__.py`

**Bot Schema/Config files**
- `bot/schema.json`
- `bot/schema.sql`
- `bot/config.json`

**CLAUDE.md files in bot/ (AI context, keep)**
- `bot/CLAUDE.md`
- `bot/cogs/CLAUDE.md`
- `bot/core/CLAUDE.md`
- `bot/services/CLAUDE.md`
- `bot/automation/CLAUDE.md`

---

### 2. Website (website/)

**Backend API (website/backend/)**
- `website/backend/__init__.py`
- `website/backend/main.py` — FastAPI entry point
- `website/backend/dependencies.py`
- `website/backend/env_utils.py`
- `website/backend/init_db.py`
- `website/backend/local_database_adapter.py`
- `website/backend/logging_config.py`
- `website/backend/metrics.py`
- `website/backend/routers/__init__.py`
- `website/backend/routers/api.py`
- `website/backend/routers/auth.py`
- `website/backend/routers/availability.py`
- `website/backend/routers/greatshot.py`
- `website/backend/routers/greatshot_topshots.py`
- `website/backend/routers/planning.py`
- `website/backend/routers/predictions.py`
- `website/backend/routers/uploads.py`
- `website/backend/middleware/__init__.py`
- `website/backend/middleware/http_cache_middleware.py`
- `website/backend/middleware/logging_middleware.py`
- `website/backend/middleware/rate_limit_middleware.py`
- `website/backend/services/__init__.py`
- `website/backend/services/contact_handle_crypto.py`
- `website/backend/services/game_server_query.py`
- `website/backend/services/greatshot_crossref.py`
- `website/backend/services/greatshot_jobs.py`
- `website/backend/services/greatshot_store.py`
- `website/backend/services/http_cache_backend.py`
- `website/backend/services/planning_discord_bridge.py`
- `website/backend/services/upload_store.py`
- `website/backend/services/upload_validators.py`
- `website/backend/services/voice_channel_tracker.py`
- `website/backend/services/website_session_data_service.py`

**Frontend (website/)**
- `website/index.html` — Main page
- `website/js/admin-panel.js`
- `website/js/app.js`
- `website/js/auth.js`
- `website/js/availability.js`
- `website/js/awards.js`
- `website/js/badges.js`
- `website/js/community.js`
- `website/js/compare.js`
- `website/js/components.js`
- `website/js/diagnostics.js`
- `website/js/filters.js`
- `website/js/greatshot.js`
- `website/js/hall-of-fame.js`
- `website/js/inline-actions.js`
- `website/js/leaderboard.js`
- `website/js/live-status.js`
- `website/js/lucide-init.js`
- `website/js/matches.js`
- `website/js/player-profile.js`
- `website/js/proximity.js`
- `website/js/records.js`
- `website/js/retro-viz.js`
- `website/js/season-stats.js`
- `website/js/sessions.js`
- `website/js/tailwind-config.js`
- `website/js/uploads.js`
- `website/js/utils.js`

**Website Assets (website/assets/)**
- `website/assets/icons/allies.svg`
- `website/assets/icons/axis.svg`
- `website/assets/maps/etl_adlernest.svg`
- `website/assets/maps/etl_battery.svg`
- `website/assets/maps/etl_bradendorf.svg`
- `website/assets/maps/etl_brewdog.svg`
- `website/assets/maps/etl_erdenberg.svg`
- `website/assets/maps/etl_escape2.svg`
- `website/assets/maps/etl_frostbite.svg`
- `website/assets/maps/etl_goldrush.svg`
- `website/assets/maps/etl_oasis.svg`
- `website/assets/maps/etl_sp_delivery.svg`
- `website/assets/maps/map_generic.svg`
- `website/assets/maps/supply.svg`

**Website Migrations (website/migrations/)**
- `website/migrations/001_server_status_history.sql`
- `website/migrations/002_voice_activity_tracking.sql`
- `website/migrations/003_upload_library.sql`
- `website/migrations/004_daily_availability_poll.sql`
- `website/migrations/005_date_based_availability.sql`
- `website/migrations/006_discord_linking_and_promotions.sql`
- `website/migrations/006_discord_linking_and_promotions_down.sql`
- `website/migrations/007_planning_room_mvp.sql`
- `website/migrations/007_planning_room_mvp_down.sql`
- `website/migrations/008_website_app_availability_grants.sql`
- `website/migrations/008_website_app_availability_grants_down.sql`

**Website Config/Infra**
- `website/requirements.txt`
- `website/.env.example`
- `website/etlegacy-website.service` — systemd unit
- `website/setup_readonly_user.sql`
- `website/start_website.sh`
- `website/.gitignore`
- `website/README.md`
- `website/CLAUDE.md` (if present)
- `website/backend/CLAUDE.md`
- `website/.github/instructions/codacy.instructions.md`

**Website Data (runtime, gitignored)**
- `website/logs/.gitkeep` — placeholder only; logs themselves are non-essential
- `website/data/retro-viz/*.png` — generated images (gitignored in practice)
- `website/data/uploads/` — user-uploaded content (gitignored)

---

### 3. Greatshot (greatshot/)

- `greatshot/__init__.py`
- `greatshot/config.py`
- `greatshot/README.md`
- `greatshot/contracts/__init__.py`
- `greatshot/contracts/types.py`
- `greatshot/contracts/profiles/__init__.py`
- `greatshot/contracts/profiles/etlegacy_main.py`
- `greatshot/contracts/profiles/profile_detector.py`
- `greatshot/contracts/schema/analysis.schema.json`
- `greatshot/cutter/__init__.py`
- `greatshot/cutter/api.py`
- `greatshot/highlights/__init__.py`
- `greatshot/highlights/detectors.py`
- `greatshot/renderer/__init__.py`
- `greatshot/renderer/api.py`
- `greatshot/scanner/__init__.py`
- `greatshot/scanner/__main__.py`
- `greatshot/scanner/adapters.py`
- `greatshot/scanner/api.py`
- `greatshot/scanner/errors.py`
- `greatshot/scanner/report.py`
- `greatshot/scanner/etl_demo_scan` — demo script
- `greatshot/worker/__init__.py`
- `greatshot/worker/runner.py`
- `greatshot/tests/__init__.py`
- `greatshot/tests/test_highlights.py`
- `greatshot/tests/fixtures/golden_analysis_v1.json`
- `greatshot/tests/fixtures/sample_udt_output.json`

---

### 4. Proximity (proximity/)

- `proximity/__init__.py`
- `proximity/README.md`
- `proximity/SLOMIX_PROJECT_BRIEF.md`
- `proximity/objective_coords_template.json`
- `proximity/sample_engagements.txt`
- `proximity/test_standalone.py`
- `proximity/lua/proximity_tracker.lua` — The deployed Lua script
- `proximity/parser/__init__.py`
- `proximity/parser/parser.py`
- `proximity/schema/schema.sql`
- `proximity/schema/migrations/2026-02-04_round_start_unix.sql`
- `proximity/schema/migrations/2026-02-12_ws1c_constraint_cleanup.sql`
- `proximity/schema/migrations/2026-02-19_reaction_metrics.sql`
- `proximity/docs/DESIGN_v4.md`
- `proximity/docs/FREEZE_RUNBOOK_2026-02-19.md`
- `proximity/docs/GAP_ANALYSIS.md`
- `proximity/docs/GAPS_AND_ROADMAP.md`
- `proximity/docs/IMPLEMENTATION_v4.md`
- `proximity/docs/INTEGRATION_STATUS.md`
- `proximity/docs/OUTPUT_FORMAT.md`
- `proximity/docs/PROXIMITY_BEHAVIOR_AUDIT_HANDOFF_2026-02-18.md`
- `proximity/docs/README.md`
- `proximity/docs/TRACKER_REFERENCE.md`
- `proximity/docs/session-notes/SESSION_NOTES_2026-01-06.md`
- `proximity/docs/session-notes/SESSION_NOTES_2026-01-08.md`
- `proximity/docs/session-notes/SESSION_NOTES_2026-01-18.md`
- `proximity/.gitignore`
- `proximity/.claude/settings.local.json`

---

### 5. Automation / VPS Scripts (vps_scripts/)

- `vps_scripts/__init__.py`
- `vps_scripts/stats_discord_webhook.lua` — Lua webhook (v1.6.2, production)
- `vps_scripts/stats_webhook_notify.py`

---

### 6. Database Schema & Migrations

**Primary schema**
- `tools/schema_postgresql.sql` — 68 tables, authoritative schema (KEEP)
- `tools/schema_sqlite.sql` — SQLite reference (keep for dev/fallback docs)

**Top-level migrations (migrations/)**
- `migrations/__init__.py`
- `migrations/005_add_surrender_and_score.sql`
- `migrations/006_add_full_selfkills.sql`
- `migrations/007_add_round_id_to_lua_round_teams.sql`
- `migrations/008_add_bot_round_flags.sql`
- `migrations/008_add_lua_spawn_stats.sql`
- `migrations/009_add_proximity_trade_events.sql`
- `migrations/010_add_proximity_support_summary.sql`
- `migrations/011_add_greatshot_pipeline_tables.sql`
- `migrations/012_add_round_contract_columns.sql`
- `migrations/add_display_name_to_player_links.sql`
- `migrations/add_match_predictions.sql`
- `migrations/add_round_status.sql`
- `migrations/add_session_results.sql`
- `migrations/add_team_tracking.sql`
- `migrations/add_user_permissions.sql`

**Tools migrations (tools/migrations/)**
- `tools/migrations/001_create_player_synergies.py`
- `tools/migrations/002_add_winner_defender_teams.py`
- `tools/migrations/003_add_warmup_columns.sql`
- `tools/migrations/004_add_pause_events.sql`
- `tools/migrations/005_add_matchup_history.sql`

**PostgreSQL DB manager**
- `postgresql_database_manager.py` — Root-level, the ONLY approved DB tool

---

### 7. Config / Infra

**Root-level config (ESSENTIAL)**
- `.env.example` — Template for secrets
- `requirements.txt` — Python deps
- `requirements-dev.txt` — Dev Python deps
- `install.sh` — Full VPS install script
- `bot_config.json` — Bot config (non-secret settings)
- `pyproject.toml` — Python project config (pytest, ruff, etc.)
- `pytest.ini` — Test config
- `.pre-commit-config.yaml` — Pre-commit hooks
- `.gitignore` — Git ignore rules
- `.gitattributes`
- `.dockerignore`
- `.codacy.yaml`
- `.secrets.baseline` — detect-secrets baseline
- `.nvmrc` — Node version pin
- `Makefile` — Build targets
- `docker-compose.yml` — Docker compose config
- `CLAUDE.md` — AI instructions
- `README.md` — Project readme
- `LICENSE`
- `SECURITY.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `CHANGELOG.md` — Tracked user-visible changes
- `.release-please-config.json`
- `.release-please-manifest.json`

**Docker (docker/)**
- `docker/Dockerfile.api`
- `docker/Dockerfile.website`
- `docker/nginx/` (nginx config files)
- `docker/prometheus.yml`

**VM/Server setup scripts (tools/vm_steps/) — KEEP**
- `tools/vm_steps/01_service_users.sh`
- `tools/vm_steps/02a_fix_kex.sh`
- `tools/vm_steps/02b_ssh_key_only.sh`
- `tools/vm_steps/02_ssh_hardening.sh`
- `tools/vm_steps/03_kernel_hardening.sh`
- `tools/vm_steps/04_postgresql_hardened.sh`
- `tools/vm_steps/05_redis_hardened.sh`
- `tools/vm_steps/06b_create_env_files.sh`
- `tools/vm_steps/06_python_venvs_env.sh`
- `tools/vm_steps/07_systemd_services.sh`
- `tools/vm_steps/08a_cloudflare_install.sh`
- `tools/vm_steps/08b_cloudflare_configure.sh`
- `tools/vm_steps/09_apply_schema.sh`

**Hardening scripts (tools/) — KEEP**
- `tools/harden_kernel.sh`
- `tools/harden_postgresql.sh`
- `tools/harden_redis.sh`
- `tools/harden_systemd.sh`

---

### 8. Tests (tests/)

All files in `tests/` are essential:
- `tests/CLAUDE.md`
- `tests/conftest.py`
- `tests/__init__.py`
- `tests/e2e/__init__.py`
- `tests/e2e/test_config_loading.py`
- `tests/fixtures/__init__.py`
- `tests/fixtures/sample_stats_files/2025-12-17-120000-goldrush-round-1.txt`
- `tests/fixtures/sample_stats_files/2025-12-17-120000-goldrush-round-2.txt`
- `tests/fixtures/sample_stats_files/2025-12-17-130000-badmap-round-1.txt`
- `tests/integration/__init__.py`
- `tests/integration/test_stats_parser_integration.py`
- `tests/performance/__init__.py`
- `tests/performance/test_parser_performance.py`
- `tests/security/__init__.py`
- `tests/security/test_security_validation.py`
- `tests/unit/__init__.py`
- `tests/unit/auth_router_security_test.py`
- `tests/unit/greatshot_schema_guard_test.py`
- `tests/unit/proximity_sprint_pipeline_test.py`
- `tests/unit/proximity_stats_guard_test.py`
- `tests/unit/test_api_middleware.py`
- `tests/unit/test_auth_linking_flow.py`
- `tests/unit/test_availability_notifier_promotion_idempotency.py`
- `tests/unit/test_availability_poll_external_commands.py`
- `tests/unit/test_availability_poll_promotion_runtime.py`
- `tests/unit/test_availability_promotions_router.py`
- `tests/unit/test_availability_router.py`
- `tests/unit/test_backfill_gametimes_contract.py`
- `tests/unit/test_database_adapter.py`
- `tests/unit/test_data_integrity.py`
- `tests/unit/test_endstats_retry_pipeline.py`
- `tests/unit/test_env_parsing.py`
- `tests/unit/test_gametime_synthetic_round.py`
- `tests/unit/test_greatshot_crossref.py`
- `tests/unit/test_greatshot_player_stats_enrichment.py`
- `tests/unit/test_greatshot_router_crossref.py`
- `tests/unit/test_kill_assists_visibility.py`
- `tests/unit/test_logging_middleware.py`
- `tests/unit/test_lua_round_teams_param_packing.py`
- `tests/unit/test_lua_webhook_diagnostics.py`
- `tests/unit/test_planning_router.py`
- `tests/unit/test_proximity_parser_objective_conflict.py`
- `tests/unit/test_proximity_reaction_metrics_parser.py`
- `tests/unit/test_proximity_round_number_normalization.py`
- `tests/unit/test_restart_detection_map_replays.py`
- `tests/unit/test_retro_viz_round_filtering.py`
- `tests/unit/test_round_contract.py`
- `tests/unit/test_round_linker_reasons.py`
- `tests/unit/test_round_publisher_map_scope.py`
- `tests/unit/test_round_publisher_team_grouping.py`
- `tests/unit/test_session_embed_builder_timing_dual.py`
- `tests/unit/test_session_graph_generator_timing_dual.py`
- `tests/unit/test_session_timing_shadow_service.py`
- `tests/unit/test_stats_parser.py`
- `tests/unit/test_stats_trends_map_distribution.py`
- `tests/unit/test_timing_comparison_service_side_markers.py`
- `tests/unit/test_timing_debug_service_session_join.py`
- `tests/unit/test_weapon_stats_routes.py`
- `tests/test_alias_fallback.py`
- `tests/test_community_stats_parser.py`
- `tests/test_greatshot_api_integration.py`
- `tests/test_greatshot_highlights.py`
- `tests/test_greatshot_scanner_golden.py`
- `tests/test_greatshot_upload_validation.py`
- `tests/test_simple_bulk_import.py`

---

### 9. CI/CD (.github/)

- `.github/workflows/codeql.yml`
- `.github/workflows/publish-images.yml`
- `.github/workflows/release.yml`
- `.github/workflows/repo-hygiene.yml`
- `.github/workflows/tests.yml`
- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `.github/pull_request_template.md`
- `.github/copilot-instructions.md`
- `.github/instructions/codacy.instructions.md`

---

### 10. Gemini Website (gemini-website/) — React Redesign

**Source (keep, gitignore dist/ and node_modules/)**
- `gemini-website/package.json`
- `gemini-website/package-lock.json`
- `gemini-website/tsconfig.json`
- `gemini-website/tsconfig.node.json`
- `gemini-website/vite.config.ts`
- `gemini-website/index.html`
- `gemini-website/README.md`
- `gemini-website/src/App.tsx`
- `gemini-website/src/main.tsx`
- `gemini-website/src/index.css`
- `gemini-website/src/vite-env.d.ts`
- `gemini-website/src/api/client.ts`
- `gemini-website/src/components/Layout.tsx`
- `gemini-website/src/pages/Activity.tsx`
- `gemini-website/src/pages/Awards.tsx`
- `gemini-website/src/pages/Dashboard.tsx`
- `gemini-website/src/pages/Leaderboards.tsx`
- `gemini-website/src/pages/Maps.tsx`
- `gemini-website/src/pages/Matches.tsx`
- `gemini-website/src/pages/PlayerProfile.tsx`
- `gemini-website/src/pages/Records.tsx`
- `gemini-website/src/pages/Sessions.tsx`
- `gemini-website/src/pages/System.tsx`

**Non-essential (gitignore)**
- `gemini-website/dist/` — build output
- `gemini-website/node_modules/` — npm packages

---

### 11. Scripts (scripts/) — Operational scripts, KEEP

- `scripts/__init__.py`
- `scripts/audit_round_pairs.py`
- `scripts/audit_time_vs_lua.py`
- `scripts/backfill_endstats.py`
- `scripts/backfill_full_selfkills.py`
- `scripts/backfill_gametimes.py`
- `scripts/backfill_lua_round_ids.py`
- `scripts/bot_scrim_mode.py`
- `scripts/check_ws1_ws1c_gates.sh`
- `scripts/debug_import.py`
- `scripts/dev_up.sh`
- `scripts/generate_omnibot_botnames.py`
- `scripts/generate_retro.py`
- `scripts/generate_retro_text.py`
- `scripts/lint-js.sh`
- `scripts/objective_coords_to_lua.py`
- `scripts/omnibot_toggle.py`
- `scripts/pipeline_health_report.py`
- `scripts/prod_up.sh`
- `scripts/publish_clean_repo.ps1`
- `scripts/rcon_command.py`
- `scripts/run_retro_test.py`
- `scripts/smoke_pipeline.py`
- `scripts/smoke_team_consistency.py`
- `scripts/sync_objective_placeholders.py`
- `scripts/system_smoke_tests.sh`
- `scripts/update_proximity_objectives_from_json.py`
- `scripts/verify_proximity_schema.py`

---

### 12. Active Documentation (docs/)

**Core system docs — KEEP**
- `docs/ACHIEVEMENT_SYSTEM.md`
- `docs/ADVANCED_TEAM_DETECTION.md`
- `docs/AI_COMPREHENSIVE_SYSTEM_GUIDE.md`
- `docs/ARCHITECTURE_ONBOARDING.md`
- `docs/AUTOMATION_CHECKLIST.md`
- `docs/AUTOMATION_SETUP_GUIDE.md`
- `docs/AVAILABILITY_SYSTEM.md`
- `docs/AVAILABILITY_UI.md`
- `docs/CHANGELOG.md`
- `docs/CLAUDE.md`
- `docs/COMMAND_CHEAT_SHEET.md`
- `docs/COMMANDS.md`
- `docs/COMPLETE_SYSTEM_RUNDOWN.md`
- `docs/CONFIGURATION_REFERENCE.md`
- `docs/CONTRIBUTING.md`
- `docs/DATA_INTEGRITY_VERIFICATION_POINTS.md`
- `docs/DATA_PIPELINE.md`
- `docs/DEPLOYMENT_CHECKLIST.md`
- `docs/DEPLOYMENT_GUIDE.md`
- `docs/DEPLOYMENT_RUNBOOK.md`
- `docs/DEVELOPMENT_WORKFLOW.md`
- `docs/DISASTER_RECOVERY.md`
- `docs/DISCORD_LINKING_SETUP.md`
- `docs/EDGE_CASES.md`
- `docs/ET_LEGACY_SERVER_RESEARCH.md`
- `docs/EXTERNAL_ACCESS_PLAN.md`
- `docs/FEATURE_ROADMAP_2026.md`
- `docs/FIELD_MAPPING.md`
- `docs/FRESH_INSTALL_GUIDE.md`
- `docs/FUTURE_SCALING_GUIDE.md`
- `docs/GAMESERVER_CLAUDE.md`
- `docs/GRAPH_DESIGN_GUIDE.md`
- `docs/INFRA_HANDOFF_2026-02-18.md`
- `docs/KNOWN_ISSUES.md`
- `docs/LINKING_ACCOUNTS.md`
- `docs/LINUX_DEPLOYMENT_GUIDE.md`
- `docs/LINUX_SETUP_README.md`
- `docs/LIVE_MONITORING_GUIDE.md`
- `docs/LUA_WEBHOOK_SETUP.md`
- `docs/NOTIFICATIONS_DISCORD.md`
- `docs/NOTIFICATIONS_LINKING.md`
- `docs/NOTIFICATIONS_SIGNAL.md`
- `docs/NOTIFICATIONS_TELEGRAM.md`
- `docs/OMNIBOT_PROJECT.md`
- `docs/PLANNING_ROOM.md`
- `docs/PLANNING_ROOM_MVP.md`
- `docs/POSTGRESQL_MIGRATION_GUIDE.md`
- `docs/POSTGRESQL_MIGRATION_IMPLEMENTATION_GUIDE.md`
- `docs/POSTGRESQL_MIGRATION_INDEX.md`
- `docs/POSTGRESQL_SQL_COMPATIBILITY_REFERENCE.md`
- `docs/PRODUCTION_AUTOMATION_GUIDE.md`
- `docs/PROJECT_HISTORY.md`
- `docs/PROJECT_OVERVIEW.md`
- `docs/PROMOTE_CAMPAIGNS.md`
- `docs/PROMOTIONS_SYSTEM.md`
- `docs/PROXIMITY_CLAUDE.md`
- `docs/QUICK_FIX_GUIDE.md`
- `docs/RUNBOOK.md`
- `docs/RUNBOOK_LOCAL_LINUX.md`
- `docs/SAFETY_VALIDATION_SYSTEMS.md`
- `docs/SEASON_SYSTEM.md`
- `docs/SECRETS_MANAGEMENT.md`
- `docs/SERVER_CONTROL_INSTALL.md`
- `docs/SERVER_CONTROL_QUICK_REF.md`
- `docs/SERVER_CONTROL_SETUP.md`
- `docs/STATS_FORMULA_RESEARCH.md`
- `docs/STATS_GROUPING_GUIDE.md`
- `docs/STOPWATCH_IMPLEMENTATION.md`
- `docs/SUBSTITUTION_DETECTION.md`
- `docs/SYSTEM_ARCHITECTURE.md`
- `docs/SYSTEM_UNDERSTANDING.md`
- `docs/TEAM_AND_SCORING.md`
- `docs/TECHNICAL_OVERVIEW.md`
- `docs/TESTING_GUIDE.md`
- `docs/UPLOAD_SECURITY.md`
- `docs/VM_ACCESS.md`
- `docs/VPS_DEPLOYMENT_GUIDE.md`
- `docs/WEBSITE_CLAUDE.md`
- `docs/reference/TIMING_DATA_SOURCES.md`
- `docs/reference/CLAUDE_CODE_QUICK_REFERENCE.md`
- `docs/reference/oksii-game-stats-web.lua` — Reference Lua from external dev

**Audit/investigation docs — borderline, recommend archiving**
- `docs/AUDIT_2026-02-15_DOCS_AND_DEBT.md`
- `docs/AUDIT_2026-02-15_REPO_CLEANUP.md`
- `docs/AUDIT_BASELINE_SNAPSHOT_2026-02-19.md`
- `docs/AUDIT_DRIFT_MATRIX_2026-02-19.md`
- `docs/AUDIT_FINDINGS_CODE_QUALITY_2026-02-19.md`
- `docs/AUDIT_FINDINGS_SECURITY_2026-02-19.md`
- `docs/AUDIT_IMPLEMENTATION_PLAN_2026-02-19.md`
- `docs/AUDIT_PIPELINE_HEALTH_CHECKLIST_2026-02-19.md`
- `docs/AUDIT_REPRO_RELEASE_CHECKLIST_2026-02-19.md`
- `docs/AUDIT_SYSTEM_MAP_2026-02-19.md`
- `docs/DEEP_DIVE_AUDIT_2026-02-20.md`
- `docs/SYSTEM_AUDIT_2026-02-21.md`

---

## Part 2: Non-Essential Files — Categorized

### Category A: Screenshots & Images (ROOT LEVEL) — DELETE

These are debugging screenshots committed directly to root. No code value.

```
banned.jpg
bigbug.jpg
brokenhomepage.jpg
claudekilled.jpg
claudekilled2.jpg
clicks.jpg
Clipboard_02-02-2026_01.jpg
codexreview.jpg
demo.jpg
didwefinish.jpg
engagementtracker.jpg
error1.jpg
error2.jpg
errorindevchannel.jpg
fullstack.jpg
githubsuggestions.jpg
githubsuggestions2.jpg
githubsuggestions3.jpg
matchdetails.jpg
monitorbug.jpg
nodata1.jpg
nodata2.jpg
oldfullstackflow.jpg
permissionmodeissue.jpg
problem.jpg
recentmatches.jpg
restarted.jpg
revisitthis.jpg
revisitthisexpand.jpg
roundbyround.png
scaning.jpg
scatteredplayers.jpg
session_2026-01-22_playstyle.png
somemorestats.png
stats1.png
stats2.png
superboyystats-colourcodedteams.png
superboyytimealivetimedead.png
systemdiagram.jpg
timecomparision.png
timeroundbungsuperboyy.png
tokens.jpg
untrue.jpg
website0.jpg
website1.jpg
websitefail2load.jpg
websitenotloading.jpg
wefixedthisright.jpg
whatsthiserror.jpg
wrongscore.jpg
```

**Recommendation**: DELETE from git history / gitignore `*.jpg *.png` in root.

### Category B: SQLite Database Files — DELETE / GITIGNORE

These are legacy SQLite databases; production uses PostgreSQL.

```
BACKUP_BEFORE_DEPLOYMENT_20251104_121158.db
backup.db
etlegacy_production.db
etlegacy_production.db.backup_20251010_143948
etlegacy_production.db.backup_20251127_133224
etlegacy_production.db.backup_GOOD_20251005
etlegacy_production.db.backup_team_scoring_20251005_134308
etlegacy_stats.db
game_stats.db
slomix_stats.db
stats.db
test_import.db
bot/BACKUP_BEFORE_PHASE2_20251104_114941.db
bot/BACKUP_ROLLBACK.db
bot/etlegacy_production.db.bak_20251031_154004
```

**Recommendation**: GITIGNORE `*.db` and all `.db.backup_*`

### Category C: SQL Dump Backups — DELETE / GITIGNORE

```
etlegacy_backup_before_time_dead_fix_20251215_225322.sql
etlegacy_backup.sql
postgresql_backup_20251216_121715.sql
postgresql_backup_20251220_230835.sql
schema.sql  (superseded by tools/schema_postgresql.sql)
```

**Recommendation**: GITIGNORE `*_backup_*.sql` and timestamped SQL dumps.

### Category D: Log Files — GITIGNORE

```
analysis_2025-10-30.txt
analysis_output.txt
claude-auto-20260221-1854.log
database_manager.log
etconsole.log
firebase-debug.log
import_log.txt
nohup.out
nuclear_rebuild.log
nuclear_rebuild_final.log
nuclear_rebuild_full.log
nuclear_rebuild.log
overnight_test_log_20251004_015211.txt
postgresql_manager.log
rebuild_30days.log
rebuild_output.log
bot/logs/*
website/logs/access.log
website/logs/app.log
website/logs/app.log.1
website/logs/debug.log
website/logs/error.log
website/logs/security.log
website/logs/security.log.1
logs/timing_shadow/*
```

**Recommendation**: GITIGNORE `*.log`, `logs/` directories (except `.gitkeep` placeholders).

### Category E: Old Lua Experiments (ROOT LEVEL) — DELETE

These are superseded development experiments. Production Lua is in `vps_scripts/` and `proximity/lua/`.

```
c0rnp0rn.lua
c0rnp0rn.lua.BACKUP_ORIGINAL
c0rnp0rn7.lua
c0rnp0rn7new.lua.lua
c0rnp0rn7real.lua
c0rnp0rn8.lua
c0rnp0rnMAYBEITSTHISONE.lua
c0rnp0rn-testluawithtimetracking.lua
endstats.lua
proximity_tracker.lua
proximity_tracker_v2.lua
proximity_tracker_v3.lua
```

**Recommendation**: DELETE. Superseded by `vps_scripts/stats_discord_webhook.lua` and `proximity/lua/proximity_tracker.lua`.

### Category F: One-Off Analysis Scripts (ROOT LEVEL) — DELETE

Scripts created during debugging, never part of the system:

```
check_production_health.py
check_qmr_death_time.py
check_te_escape2_files.py
check_time_fields.py
compare_lua_vs_db.py
debug_fp.py
investigate_round_numbers.py
pentest_filename_injection.py
pentest_rate_limit.py
show_death_time_fix.py
test_death_time_fix.py
test_parser_robustness.py
test_rate_limiting.py
test_webhook_id_validation.py
test_webhook_security.py
trigger_timing_debug.py
```

**Recommendation**: DELETE or move to `archive/diagnostics/`.

### Category G: Validation Output Files (ROOT LEVEL) — DELETE

Timestamped output files from past validation runs:

```
stats_validation_discrepancies_20251103_*.json  (7 files)
stats_validation_issues_20251103_*.json  (7 files)
stats_validation_raw_20251103_*.txt  (7 files)
stats_validation_report_20251103_*.html  (7 files)
nov2_validation_results.txt
validation_complete.txt
validation_corrected_results.txt
validation_full_results.txt
validation_results.txt
corrupt_records_before_fix.txt
backup_table_schemas.txt
check.vps.rounds.txt
cmon.txt
CURRENT_DB_SCHEMA.txt
DATA_PIPELINE_EXPLAINED.txt
DEPLOYMENT_READY.txt
DOCS_STATUS_CHECK.txt
field_analysis_log.json
field_analysis_log.txt
FIELD_MAPPING.json
GIT_COMMIT_MESSAGE.txt
GITHUB_COMMIT_INSTRUCTIONS.txt
GITHUB_VERIFICATION.txt
import_log.txt
rebuild_inputs.txt
req2.txt
team_check_output.txt
test_out.txt
```

**Recommendation**: DELETE.

### Category H: HTML Reports (ROOT LEVEL) — DELETE

One-off HTML presentations from debugging:

```
COMPLETE_DATA_PIPELINE.html
complete_field_mapping_presentation.html
COMPREHENSIVE_VALIDATION_REPORT.html
field_mapping_report.html
FIELD_MAPPING_VALIDATION_REPORT.html
HEADSHOT_BUG_PRESENTATION.html
interactive_field_mapping.html
stats_validation_report_20251103_*.html  (7 files)
TECHNICAL_MISMATCH_DETAILS.html
```

**Recommendation**: DELETE.

### Category I: Windows/Dev Scripts (ROOT LEVEL) — DELETE

These are local dev scripts for Windows users, not production:

```
check_bot_errors.ps1
cleanup_github.ps1
cleanup_simple.ps1
deploy.bat
import_stats.ps1
migrate_to_laptop.ps1
nuclear_reset.bat
rebuild_database.ps1
restart_bot.bat
rollback_phase2.ps1
setup_env.ps1
setup_local_db.ps1
setup_postgres_simple.ps1
start.bat
start_bot.ps1
validate.ps1
```

**Recommendation**: DELETE or move to `dev_tools/windows/` and gitignore.

### Category J: Misplaced Root Markdown — MOVE or DELETE

```
chatgptresearch.md                    — DELETE (personal research notes)
zac0rna.md                           — DELETE (personal notes)
plan-teamSuggestionSystem.prompt.md  — DELETE or archive
DATA_ACCURACY_VERIFICATION_2025-12-17.md  — ARCHIVE
COMPLETE_IMPLEMENTATION.md            — ARCHIVE
DEVELOPER_REFERENCE.md               — MOVE to docs/
IMPLEMENTATION_SUMMARY.md            — ARCHIVE
INSTALL_CONSOLIDATION_SUMMARY.md     — ARCHIVE
INSTALL_SCRIPTS_DEPRECATED.md        — ARCHIVE
LAST_SESSION_VERIFICATION_REPORT.md  — ARCHIVE
PRODUCTION_AUDIT_SUMMARY.md          — ARCHIVE
PROJECT_OVERVIEW.md                  — DUPLICATE of docs/PROJECT_OVERVIEW.md
PROXIMITY_DEPLOYMENT_GUIDE.md        — MOVE to docs/
PROXIMITY_TRACKER_README.md          — MOVE to proximity/
PROXIMITY_V2_README.md               — MOVE to proximity/ or DELETE
```

### Category K: Build Artifacts & Cache — GITIGNORE

```
gemini-website/dist/            — Build output
gemini-website/node_modules/    — npm packages
node_modules/                   — npm packages (root)
.venv/                          — Python virtualenv
venv/                           — Python virtualenv (website)
website/venv/                   — Python virtualenv
__pycache__/                    — Python bytecode (everywhere)
.pytest_cache/                  — pytest cache
.ruff_cache/                    — ruff cache
htmlcov/                        — Coverage HTML reports
.coverage                       — Coverage data file
coverage.xml                    — Coverage XML
```

### Category L: Entire Non-Essential Directories — DELETE or GITIGNORE

```
archive/                         — OLD: use docs/archive/ instead; superseded
archive/diagnostics/             — 200+ one-off check scripts from Oct 2025
backups/                         — Local backup copies (not for git)
database_backups/                — Old SQLite backup folder
database/                        — Old database module (superseded)
dev/                             — Old development workspace with many scripts
dev/backups/                     — Dev backup files
dev/test_bots/                   — Dev bot copies
asdf/                            — Scratch directory (unknown purpose)
test_suite/                      — Old manual test file collection
test_files/                      — Empty
tmp/                             — Temp files
opusreview/                      — Old security review (small, keep files in docs/)
local_stats/                     — Downloaded stats files (gitignore, runtime data)
local_gametimes/                 — Runtime data
local_proximity/                 — Runtime proximity data
fiveeyes/                        — Old fiveeyes feature (partially superseded)
analytics/                       — Old analytics module (moved into bot/cogs/)
prompt_instructions/             — Personal AI prompt notes
deployed_lua/                    — Lua backup copies (superseded by vps_scripts/)
data/greatshot/                  — Greatshot processed data (runtime, gitignore)
tools/tmp/                       — Temporary PNG renders
tools/archive/                   — Single file: simple_bulk_import_clean.py (archive)
docs/scripts_2026-01-30_r2_fix/ — Old fix scripts
docs/2026-01-30-r2-parser-fix/  — Old fix scripts
monitoring/                      — Appears empty
server/omnibot/                  — Omnibot server files
bin/                             — (check if empty)
```

### Category M: Zip Archives — DELETE

```
slomix-review.zip
website.zip
website (2).zip
test_suite/2910claudeFIXES.zip
test_suite/secrets.zip           — CRITICAL: may contain secrets, verify before deleting
```

**Recommendation**: DELETE. If `secrets.zip` contains real credentials, ensure they are rotated and then delete.

### Category N: Misplaced Game Demo Files (ROOT LEVEL) — DELETE

```
2026-02-03-220741-etl_adlernest.dm_84   — Game demo file
2026-02-03-221813-etl_sp_delivery.dm_84 — Game demo file
```

### Category O: Broken pip install artifacts (ROOT LEVEL) — DELETE

```
=0.21.0
=0.29.0
=2.2.0
=3.12.0
=4.1.0
=7.4.0
```

These appear to be failed `pip install` output files (e.g., `pip install package==version` redirected to files).

### Category P: Miscellaneous Root Files — REVIEW

```
Complete                         — Empty file or marker?
FLOW_DIAGRAM.txt                 — Archive in docs/
bot/proximity_schema.sql         — Superseded by proximity/schema/schema.sql
bot/proximity_schema_v2.sql      — Superseded
bot/proximity_schema_v3.sql      — Superseded
bot/README_AUTOMATION.md         — Merge content into bot/automation/CLAUDE.md
bot/fiveeyes_config.json         — Fiveeyes config (archive if unused)
bot/diagnostics/                 — check_duplicates.py, remove_duplicates.py (archive)
bot/tools/                       — Debug utility scripts (archive or gitignore)
fiveeyes_config.json             — Duplicate config (root level)
config.json                      — Unclear purpose (check vs bot_config.json)
etlegacy-discord-bot.code-workspace — VSCode workspace (gitignore)
stats.code-workspace             — VSCode workspace (gitignore)
package.json                     — Root package.json (check if needed vs gemini-website/package.json)
package-lock.json                — Root lock file
run_claude_auto.sh               — Personal automation script (gitignore)
```

### Category Q: docs/reference Backup Lua Files

```
docs/reference/c0rnp0rn7_prepatch_from_git_history.lua  — Archive ref, keep
docs/reference/c0rnp0rn7_prepatch_vs_current.diff       — Archive ref, keep
docs/reference/live_sync_backups/                        — Transient backups, gitignore
```

### Category R: Website Backup Files

```
website/index_before_fix_20251129_185929.html        — DELETE
website/index_BEFORE_RESTORE_20251130_144038.html    — DELETE
website/index_temp_builder.html                      — DELETE
website/js/app.js.BACKUP_20251130_152924             — DELETE
website/js/app.js.BACKUP_20251130_153453             — DELETE
website/js/records.js.BACKUP_20251130_152924         — DELETE
website/SESSION_NOTES_*.md                           — MOVE to docs/archive/ or DELETE
website/REVIEW_NOTES.md                              — MOVE to docs/archive/ or DELETE
website/websitemissing*.png                          — DELETE (screenshots)
website/website.code-workspace                       — GITIGNORE
```

---

## Part 3: Proposed .gitignore Rules

Add or confirm the following rules in `/.gitignore`:

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyo
.pytest_cache/
.ruff_cache/
.coverage
coverage.xml
htmlcov/

# Virtual environments
.venv/
venv/
env/
*.egg-info/

# Node / React
node_modules/
dist/
.next/
build/

# Database files
*.db
*.db.backup*
*.db.bak*
*.sql.gz

# Log files
*.log
nohup.out
logs/
!logs/.gitkeep

# Environment secrets
.env
!.env.example

# OS / Editor
.DS_Store
Thumbs.db
*.code-workspace
*.code-workspace
.vscode/settings.json

# Runtime / local data
local_stats/
local_gametimes/
local_proximity/
data/greatshot/
website/data/uploads/
website/data/retro-viz/
tools/tmp/

# Backup files
*.bak
*.BAK
*.BACKUP*
*.backup_*
*.orig
*_before_fix_*.html
*_before_fix_*.js
*.BACKUP_[0-9]*

# Images (screenshots in root — these should never be committed)
# NOTE: Do not add *.jpg or *.png globally — website/assets/ needs SVGs kept
# Instead, use directory-specific rules or clean up manually

# Zip archives
*.zip

# SQL backups (runtime)
postgresql_backup_*.sql
etlegacy_backup*.sql
*_backup_*.sql

# Broken pip artifacts
=*

# Demo files
*.dm_84

# Personal scripts
run_claude_auto.sh

# Temp files
/tmp/
/temp/
```

---

## Part 4: Summary Table

| Area | Essential Files | Non-Essential |
|------|----------------|--------------|
| Bot (cogs, core, services, automation) | ~110 files | Backup .db files, pycache |
| Website (backend, frontend, assets) | ~80 files | Backup .html/.js files, logs, venv |
| Greatshot | ~28 files | — |
| Proximity | ~29 files | local_proximity/ data |
| VPS Scripts | 3 files | deployed_lua/ (superseded) |
| Database schema + migrations | ~25 files | *.db, *.sql backup dumps |
| Config/Infra (root) | ~25 files | .env, venv, node_modules |
| Tests | 65 files | test_suite/, test_files/ (old) |
| CI/CD | 10 files | — |
| Gemini Website | ~24 files | node_modules/, dist/ |
| Scripts | 28 files | — |
| Docs (active) | ~90 files | — |
| Docs (archive) | ~130 files | docs/archive/ (historical) |
| **TOTAL ESSENTIAL** | **~647 files** | |
| Root screenshots/images | — | ~50 .jpg/.png files |
| Root debug scripts | — | ~20 .py files |
| Root log/output files | — | ~60 files |
| Root Lua experiments | — | ~12 files |
| Root Windows scripts | — | ~16 .ps1/.bat files |
| Root HTML reports | — | ~16 files |
| Root DB/SQL backups | — | ~15 files |
| Root zip files | — | ~3 files |
| Entire non-essential dirs | — | archive/, backups/, dev/, asdf/, test_suite/, fiveeyes/, analytics/, prompt_instructions/ |
| **TOTAL NON-ESSENTIAL** | — | **~800+ files + entire dirs** |

---

## Part 5: Files Requiring Special Attention

### Potential Secrets
- `test_suite/secrets.zip` — VERIFY CONTENTS before deleting; may contain credentials
- `.env` (root, website/) — already gitignored; confirm they are not committed
- `dev/server/etlegacy_bot`, `dev/server/etlegacy_bot.pub` — SSH keys in dev dir; verify not committed to git history

### Ambiguous Files (Needs Owner Decision)
- `fiveeyes/` directory — Was this feature abandoned? If yes, move to archive or delete
- `analytics/` directory — Is this superseded by `bot/cogs/analytics_cog.py`? If yes, delete
- `bot/diagnostics/` — Two scripts: check_duplicates.py, remove_duplicates.py; move to scripts/ or archive
- `bot/tools/` — 5 debug utility scripts; archive or gitignore
- `config.json` (root) — Unknown purpose; check if `bot_config.json` supersedes it
- `CHANGELOG.md` (root) vs `docs/CHANGELOG.md` — There are two changelogs; consolidate to docs/

### Reference Lua Files (docs/reference/)
- `docs/reference/c0rnp0rn7_prepatch_from_git_history.lua` — Historical reference, keep archived
- `docs/reference/oksii-game-stats-web.lua` — External dev reference, keep

---

*This report was generated for Phase 5: GitHub Repository Cleanup. Use the Essential Files Manifest to verify nothing critical is removed. Use the Non-Essential list as the deletion/gitignore target list.*
