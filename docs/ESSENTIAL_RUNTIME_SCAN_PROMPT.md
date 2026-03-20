# Essential Runtime Scan Prompt

Use this with any future agent/model that should map Slomix without wandering into repo trash.

Findings source:
- [ESSENTIAL_RUNTIME_MAP.md](/home/samba/share/slomix_discord/docs/ESSENTIAL_RUNTIME_MAP.md)

## Copy-Paste Prompt

```text
You are working inside /home/samba/share/slomix_discord.

Your task is NOT to scan the whole repo.
Your task is to analyze only the files required to understand and operate the real runtime architecture.

Hard rules:
- Read-only unless explicitly told otherwise.
- Do not delete, move, rename, clean up, or rewrite anything.
- Do not recursively scan the whole repository.
- Assume this repo contains backups, experiments, dead files, scratch files, and misleading history.
- Only scan the allowlist below.
- Only expand into SCAN_IF_REFERENCED when a file in SCAN directly imports, executes, mounts, reads, or depends on it.
- Everything in DO_NOT_SCAN is blocked by default unless a SCAN file proves it is a live runtime dependency.
- Focus on runtime architecture, not bug hunting.
- Do not summarize docs unless they directly explain runtime behavior, deploy behavior, data flow, or production wiring.

Goal:
Map what is actually required to run Slomix successfully in production:
- Discord bot
- stats ingestion
- website/API
- PostgreSQL/Redis/runtime infra
- Greatshot
- optional proximity subsystem

Important runtime truth:
- scripts/prod_up.sh is the repo-managed full runtime entrypoint.
- docker-compose.yml is only the web/db/cache/observability stack and does NOT run the Discord bot.

SCAN

README.md
Makefile
.env.example
website/.env.example
bot_config.json
config.json
requirements.txt
website/requirements.txt
pyproject.toml
docker-compose.yml
tools/check_production_health.py
start_bot.sh
scripts/dev_up.sh
scripts/prod_up.sh

bot/ultimate_bot.py
bot/config.py
bot/community_stats_parser.py
postgresql_database_manager.py
bot/logging_config.py
bot/core/database_adapter.py
bot/core/round_contract.py
bot/core/round_linker.py
bot/core/team_manager.py
bot/core/stats_cache.py
bot/core/season_manager.py
bot/core/achievement_system.py
bot/core/utils.py
bot/automation/ssh_handler.py
bot/automation/file_tracker.py
bot/repositories/file_repository.py
bot/services/round_publisher_service.py
bot/services/webhook_round_metadata_service.py
bot/services/voice_session_service.py
bot/services/monitoring_service.py
bot/services/timing_debug_service.py
bot/services/timing_comparison_service.py
bot/services/round_correlation_service.py

bot/cogs/admin_cog.py
bot/cogs/permission_management_cog.py
bot/cogs/link_cog.py
bot/cogs/stats_cog.py
bot/cogs/leaderboard_cog.py
bot/cogs/session_cog.py
bot/cogs/last_session_cog.py
bot/cogs/achievements_cog.py
bot/cogs/sync_cog.py
bot/cogs/session_management_cog.py
bot/cogs/team_management_cog.py
bot/cogs/team_cog.py
bot/cogs/matchup_cog.py
bot/cogs/analytics_cog.py
bot/cogs/availability_poll_cog.py
bot/cogs/automation_commands.py
bot/cogs/predictions_cog.py
bot/cogs/admin_predictions_cog.py
bot/cogs/server_control.py
bot/cogs/synergy_analytics.py
bot/cogs/proximity_cog.py

vps_scripts/stats_discord_webhook.lua
vps_scripts/stats_webhook_notify.py

website/backend/main.py
website/backend/dependencies.py
website/backend/logging_config.py
website/backend/env_utils.py
website/backend/metrics.py
website/backend/middleware/
website/backend/routers/api.py
website/backend/routers/auth.py
website/backend/routers/predictions.py
website/backend/routers/greatshot.py
website/backend/routers/greatshot_topshots.py
website/backend/routers/uploads.py
website/backend/routers/availability.py
website/backend/routers/planning.py
website/backend/services/http_cache_backend.py
website/backend/services/website_session_data_service.py
website/backend/services/game_server_query.py
website/backend/services/voice_channel_tracker.py
website/backend/services/planning_discord_bridge.py
website/backend/services/contact_handle_crypto.py
website/backend/services/upload_store.py
website/backend/services/upload_validators.py
website/etlegacy-website.service
website/index.html
website/js/app.js
website/js/utils.js
website/js/auth.js
website/js/live-status.js
website/js/greatshot.js
website/js/proximity.js
website/js/admin-panel.js

greatshot/config.py
greatshot/scanner/
greatshot/highlights/
greatshot/worker/runner.py
greatshot/cutter/api.py
greatshot/renderer/api.py
website/backend/services/greatshot_store.py
website/backend/services/greatshot_jobs.py
website/backend/services/greatshot_crossref.py

docker/Dockerfile.api
docker/Dockerfile.website
docker/nginx/default.conf
migrations/

SCAN_IF_REFERENCED

website/js/*.js not already listed above but imported by website/js/app.js
website/assets/
bot/services/session_*.py
bot/services/player_*.py
bot/services/prediction_*.py
bot/services/matchup_analytics_service.py
bot/services/session_graph_generator.py
bot/services/stopwatch_scoring_service.py
bot/services/automation/
bot/core/advanced_team_detector.py
bot/core/team_detector_integration.py
bot/core/substitution_detector.py
bot/core/team_history.py
bot/core/frag_potential.py
greatshot/contracts/
bin/UDT_* if tracing external Greatshot runtime dependencies
scripts/check_ws*.sh if tracing runtime validation gates
website/backend/local_database_adapter.py for sqlite/dev mode only
docs/ only when directly needed for live runtime or deploy explanation
proximity/
monitoring/prometheus.yml

DO_NOT_SCAN

archive/
backups/
dev/
tests/
test_suite/
test_files/
tmp/
logs/
htmlcov/
node_modules/
gemini-website/
.venv/
venv/
__pycache__/
.pytest_cache/
.ruff_cache/
.mypy_cache/
prompt_instructions/
asdf/
analytics/
database_backups/
local scratch top-level files
c0rnp0rn*.lua copies at repo root
stats_validation_*.json
field_analysis_log.json
one-off debug scripts
one-off pentest scripts
requirements-dev.txt
package-lock.json
package.json

Required workflow:
1. Read SCAN only.
2. Identify the real runtime entrypoints and long-running processes.
3. Map the actual production data flows:
   - ET server -> webhook/SSH -> bot -> DB -> Discord
   - browser -> website/nginx -> FastAPI -> DB/Redis
   - upload -> Greatshot worker -> artifacts -> API/UI
   - proximity only if directly confirmed as enabled/relevant
4. Only then expand into SCAN_IF_REFERENCED.
5. Keep a parallel exclusion list of what you intentionally did not scan.
6. If you need a blocked path, state exactly why.

Required output:
- Essential files actually used by runtime
- Optional but real subsystems
- Excluded non-essential areas
- Unknowns that code alone cannot prove

Do not drift outside this scope.
```
