# Essential Runtime Map

Purpose: keep future architecture work inside the files that matter for running Slomix, and out of backups, scratch files, and dead history.

This is a read-scope document, not a cleanup plan. Nothing here implies deletion.

## Runtime Modes

Full repo-managed runtime:
- [scripts/prod_up.sh](/home/samba/share/slomix_discord/scripts/prod_up.sh)
- Starts:
  - website backend via `uvicorn website.backend.main:app`
  - Discord bot via `python bot/ultimate_bot.py`

Compose web stack only:
- [docker-compose.yml](/home/samba/share/slomix_discord/docker-compose.yml)
- Starts:
  - PostgreSQL
  - Redis
  - API container
  - static website container
  - optional Prometheus/Grafana
- Does not start the Discord bot.

Single-process helpers:
- [start_bot.sh](/home/samba/share/slomix_discord/start_bot.sh)
- [website/start_website.sh](/home/samba/share/slomix_discord/website/start_website.sh)
- [website/etlegacy-website.service](/home/samba/share/slomix_discord/website/etlegacy-website.service)

## Core Architecture

Bot ingestion and Discord publishing:
1. ET server writes stats files.
2. Preferred trigger is Lua `STATS_READY` via [vps_scripts/stats_discord_webhook.lua](/home/samba/share/slomix_discord/vps_scripts/stats_discord_webhook.lua).
3. [bot/ultimate_bot.py](/home/samba/share/slomix_discord/bot/ultimate_bot.py) validates the webhook and fetches the real stats file over SSH.
4. Import path runs through [postgresql_database_manager.py](/home/samba/share/slomix_discord/postgresql_database_manager.py) and [bot/community_stats_parser.py](/home/samba/share/slomix_discord/bot/community_stats_parser.py).
5. [bot/services/round_publisher_service.py](/home/samba/share/slomix_discord/bot/services/round_publisher_service.py) posts the result to Discord.

Website/API:
1. [website/backend/main.py](/home/samba/share/slomix_discord/website/backend/main.py) builds the FastAPI app.
2. Routers under [website/backend/routers](/home/samba/share/slomix_discord/website/backend/routers) expose stats, auth, uploads, availability, planning, and Greatshot APIs.
3. [website/index.html](/home/samba/share/slomix_discord/website/index.html) + [website/js/app.js](/home/samba/share/slomix_discord/website/js/app.js) drive the SPA.

Greatshot:
1. Upload enters through [website/backend/routers/greatshot.py](/home/samba/share/slomix_discord/website/backend/routers/greatshot.py).
2. [website/backend/services/greatshot_store.py](/home/samba/share/slomix_discord/website/backend/services/greatshot_store.py) saves and validates the demo.
3. [website/backend/services/greatshot_jobs.py](/home/samba/share/slomix_discord/website/backend/services/greatshot_jobs.py) queues analysis/render work.
4. [greatshot/worker/runner.py](/home/samba/share/slomix_discord/greatshot/worker/runner.py) calls scanner/highlight/cutter/renderer code under [greatshot](/home/samba/share/slomix_discord/greatshot).

Proximity:
1. Lua tracker [proximity/lua/proximity_tracker.lua](/home/samba/share/slomix_discord/proximity/lua/proximity_tracker.lua) writes `_engagements.txt`.
2. [proximity/parser/parser.py](/home/samba/share/slomix_discord/proximity/parser/parser.py) imports into PostgreSQL proximity tables.
3. Website proximity endpoints live in [website/backend/routers/api.py](/home/samba/share/slomix_discord/website/backend/routers/api.py).
4. Frontend view lives in [website/js/proximity.js](/home/samba/share/slomix_discord/website/js/proximity.js).

## essential_now

These are the files and paths that define the current runtime architecture.

Root/runtime control:
```text
README.md
Makefile
.env.example
website/.env.example
requirements.txt
website/requirements.txt
pyproject.toml
docker-compose.yml
tools/check_production_health.py
start_bot.sh
scripts/dev_up.sh
scripts/prod_up.sh
```

Machine-local runtime config:
```text
.env
config.json
bot_config.json
fiveeyes_config.json
```

Track only sanitized templates for these. Treat live values as local secrets/runtime state.

Bot baseline:
```text
bot/ultimate_bot.py
bot/config.py
bot/community_stats_parser.py
postgresql_database_manager.py
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
bot/logging_config.py
```

Bot runtime sidecars:
```text
analytics/__init__.py
analytics/config.py
analytics/synergy_detector.py
```

Bot startup-loaded command/runtime surface:
```text
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
```

VPS / trigger side:
```text
vps_scripts/stats_discord_webhook.lua
vps_scripts/stats_webhook_notify.py
```

Website/API baseline:
```text
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
```

Greatshot core:
```text
greatshot/config.py
greatshot/scanner/
greatshot/highlights/
greatshot/worker/runner.py
greatshot/cutter/api.py
greatshot/renderer/api.py
website/backend/services/greatshot_store.py
website/backend/services/greatshot_jobs.py
website/backend/services/greatshot_crossref.py
```

Infra / deploy / schema:
```text
docker/Dockerfile.api
docker/Dockerfile.website
docker/nginx/default.conf
migrations/
```

## essential_if_referenced

Read these only when an essential file directly imports, executes, mounts, or depends on them.

```text
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
bin/UDT_* if tracing external Greatshot dependencies
scripts/check_ws*.sh if tracing runtime validation gates
website/backend/local_database_adapter.py for local sqlite/dev mode only
docs/ only when explaining live runtime/deploy/data-flow behavior
analytics/ when tracing `bot/cogs/synergy_analytics.py`
```

## optional_subsystems

These are real runtime components, but not required for the absolute minimum baseline.

Optional or feature-gated:
```text
proximity/
monitoring/prometheus.yml
docker-compose observability profile
vps_scripts/stats_webhook_notify.py legacy filename-trigger path
planning Discord thread creation in website/backend/routers/planning.py
Greatshot rendering when external binaries/commands are configured
```

Important note:
- Proximity is integrated and deployable, but current repo signals still treat it as optional rather than a hard startup dependency.

## excluded_nonessential

Do not read these for architecture mapping unless an essential file proves they are active runtime dependencies.

```text
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
database_backups/
local scratch top-level files
c0rnp0rn*.lua copies at repo root
stats_validation_*.json
field_analysis_log.json
one-off debug or pentest scripts not referenced by runtime entrypoints
requirements-dev.txt
package-lock.json
package.json
```

## unknown_needs_decision

These are the remaining gaps before this becomes a strict permanent allowlist.

```text
How the Discord bot is deployed in live production outside repo scripts
Whether vps_scripts/stats_webhook_notify.py is still used anywhere live
Exact production-required subset of startup-loaded cogs versus “nice-to-have” command surfaces
Whether proximity is enabled in live production or only ready-to-run
External Greatshot binary locations and provisioning:
  - UDT_json
  - UDT_cutter
  - ffmpeg
  - render command
Database state questions that code alone cannot prove:
  - root migrations applied
  - Greatshot tables present
  - lua_round_teams and related webhook tables present
  - proximity schema/migrations applied when subsystem is enabled
```

## Working Rule For Future Scans

Start with `essential_now`.

Only expand into `essential_if_referenced` when a direct runtime dependency forces it.

Treat `excluded_nonessential` as blocked by default.
